"""EER — Evaluation Experiment Runner: orchestrates the 5-phase pipeline."""
from __future__ import annotations

import sys

from .config import CoEvalConfig, PHASE_IDS
from .exceptions import PartialPhaseFailure
from .interfaces import ModelPool
from .logger import RunLogger
from .phases.phase1 import run_phase1
from .phases.phase2 import run_phase2
from .phases.phase3 import run_phase3
from .phases.phase4 import run_phase4
from .phases.phase5 import run_phase5
from .phases.utils import QuotaTracker
from .storage import ExperimentStorage

_PHASE_RUNNERS = {
    'attribute_mapping': run_phase1,
    'rubric_mapping': run_phase2,
    'data_generation': run_phase3,
    'response_collection': run_phase4,
    'evaluation': run_phase5,
}

# Phases 1-2 use Keep so per-task files that already exist are skipped.
# Phases 3-5 use Extend so already-written JSONL records are skipped at
# the individual item level (datapoint / response / evaluation).
_CONTINUE_MODE = {
    'attribute_mapping': 'Keep',
    'rubric_mapping': 'Keep',
    'data_generation': 'Extend',
    'response_collection': 'Extend',
    'evaluation': 'Extend',
}


def print_execution_plan(cfg: CoEvalConfig) -> None:
    """Print the execution plan to stdout (REQ-8.1.2)."""
    exp = cfg.experiment
    print(f"\n{'='*60}")
    print(f"CoEval Experiment: {exp.id}")
    print(f"Storage:           {exp.storage_folder}/{exp.id}")
    if exp.resume_from:
        print(f"Resume from:       {exp.resume_from}")
    print(f"{'='*60}")

    teachers = cfg.get_models_by_role('teacher')
    students = cfg.get_models_by_role('student')
    judges = cfg.get_models_by_role('judge')

    print(f"\nModels:")
    for m in cfg.models:
        print(f"  {m.name:30s}  roles={m.roles}  interface={m.interface}")

    print(f"\nTasks:")
    for t in cfg.tasks:
        print(f"  {t.name:30s}  sampling.total={t.sampling.total}  eval={t.evaluation_mode}")

    print(f"\nPhase plan:")
    for phase_id in PHASE_IDS:
        mode = cfg.get_phase_mode(phase_id)
        print(f"  {phase_id:25s}  mode={mode}")

    print(f"\nEstimated LLM calls (upper bound):")
    total_calls = 0
    for task in cfg.tasks:
        n_teacher = len(teachers)
        n_student = len(students)
        n_judge = len(judges)
        total_per_task = task.sampling.total
        phase3_calls = n_teacher * total_per_task
        phase4_calls = n_teacher * n_student * total_per_task
        if task.evaluation_mode == 'single':
            phase5_calls = n_teacher * n_judge * n_student * total_per_task
        else:
            phase5_calls = n_teacher * n_judge * n_student * total_per_task * len(
                task.rubric if isinstance(task.rubric, dict) else {}
            )
        task_calls = phase3_calls + phase4_calls + phase5_calls
        total_calls += task_calls
        print(
            f"  {task.name}: ~{task_calls} calls "
            f"(phase3={phase3_calls}, phase4={phase4_calls}, phase5={phase5_calls})"
        )
    print(f"  Total: ~{total_calls} LLM calls\n")


def run_experiment(
    cfg: CoEvalConfig,
    dry_run: bool = False,
    continue_in_place: bool = False,
    only_models: set[str] | None = None,
    skip_probe: bool = False,
    probe_mode: str | None = None,
    probe_on_fail: str | None = None,
    estimate_only: bool = False,
    estimate_samples: int | None = None,
) -> int:
    """Execute the full 5-phase pipeline.

    Parameters
    ----------
    cfg:
        Loaded and validated experiment configuration.
    dry_run:
        Validate config and print execution plan only; no LLM calls made.
    continue_in_place:
        Re-open an existing experiment folder; skip completed phases and resume
        in-progress phases at the finest available granularity.
    only_models:
        Set of model IDs to activate; others are skipped.  Phase-completion
        markers are NOT written to meta.json in this mode.
    skip_probe:
        Deprecated shortcut for ``probe_mode='disable'``.  When True overrides
        *probe_mode* to ``'disable'``.
    probe_mode:
        ``'full'`` (default), ``'resume'``, or ``'disable'``.  Overrides the
        value in ``cfg.experiment.probe_mode``.
    probe_on_fail:
        ``'abort'`` (default) or ``'warn'``.  Overrides
        ``cfg.experiment.probe_on_fail``.
    estimate_only:
        Run the cost/time estimator and exit without starting any pipeline
        phases.  Writes ``cost_estimate.json`` to the experiment folder.
    estimate_samples:
        Number of real API sample calls per model for cost calibration.
        Overrides ``cfg.experiment.estimate_samples``.

    Returns
    -------
    int
        Exit code: 0 on success, 1 on failure.
    """
    exp = cfg.experiment

    # Resolve probe settings (CLI overrides > config file)
    effective_probe_mode   = (
        'disable' if skip_probe
        else (probe_mode or exp.probe_mode or 'full')
    )
    effective_probe_fail   = probe_on_fail or exp.probe_on_fail or 'abort'
    effective_est_samples  = (
        estimate_samples if estimate_samples is not None
        else exp.estimate_samples
    )
    run_cost_estimate = estimate_only or exp.estimate_cost

    # Initialize storage
    storage = ExperimentStorage(exp.storage_folder, exp.id)
    storage.initialize(
        config_raw=cfg._raw,
        resume_from_id=exp.resume_from,
        source_storage_folder=exp.storage_folder if exp.resume_from else None,
        continue_in_place=continue_in_place,
    )

    # Set up logger — parallel model-filter runs get their own log file so
    # entries don't interleave with the main process's run.log.
    if only_models:
        model_tag = '_'.join(sorted(only_models))[:40]
        log_path = storage.log_path.parent / f'run_{model_tag}.log'
    else:
        log_path = storage.log_path
    logger = RunLogger(log_path, min_level=exp.log_level)
    logger.info(f"Experiment {exp.id} {'continued' if continue_in_place else 'started'}")

    if dry_run:
        logger.info("Dry-run mode — no LLM calls will be made")
        print_execution_plan(cfg)
        logger.info("Dry-run complete")
        return 0

    # Read already-completed phases (needed for resume probe mode even before
    # the main continue_in_place block below)
    phases_completed_early: set[str] = set()
    if continue_in_place:
        try:
            meta = storage.read_meta()
            phases_completed_early = set(meta.get('phases_completed', []))
        except Exception:
            pass

    # --- Cost & time estimator -------------------------------------------
    if run_cost_estimate:
        from .interfaces.cost_estimator import estimate_experiment_cost
        logger.info(
            f"Running cost/time estimator "
            f"(estimate_samples={effective_est_samples}) …"
        )
        estimate_experiment_cost(
            cfg,
            storage,
            logger,
            n_samples=effective_est_samples,
            run_sample_calls=(effective_est_samples > 0),
            continue_in_place=continue_in_place,
            completed_phases=phases_completed_early,
        )
        if estimate_only:
            logger.info("--estimate-only: exiting after cost estimate")
            return 0

    # --- Model availability probe ----------------------------------------
    if effective_probe_mode != 'disable':
        from .interfaces.probe import run_probe
        logger.info(
            f"Running model availability probe "
            f"(mode='{effective_probe_mode}', on_fail='{effective_probe_fail}') …"
        )
        probe_results, _ = run_probe(
            cfg,
            logger,
            mode=effective_probe_mode,
            on_fail=effective_probe_fail,
            phases_completed=phases_completed_early,
            only_models=only_models,
            probe_results_path=storage.run_path / 'probe_results.json',
        )
        unavailable = {
            name: err for name, err in probe_results.items() if err != 'ok'
        }
        if unavailable and effective_probe_fail == 'abort':
            logger.error(
                f"Probe failed for {len(unavailable)} model(s): "
                f"{sorted(unavailable.keys())} — aborting. "
                "Fix the issues above, use --probe disable, or "
                "set probe_on_fail: warn in your config to continue anyway."
            )
            return 1
        elif unavailable:
            logger.warning(
                f"Probe: {len(unavailable)} model(s) unavailable "
                f"({sorted(unavailable.keys())}) — continuing as probe_on_fail=warn"
            )
    else:
        logger.info("Probe: disabled — skipping model availability check")

    # Read already-completed phases when continuing an existing experiment
    # (phases_completed_early is already populated above for the probe; reuse it)
    completed_phases: set[str] = phases_completed_early
    if only_models:
        logger.info(f"Parallel model filter active — only_models={sorted(only_models)}")

    if continue_in_place and not phases_completed_early:
        # Re-read meta in case something changed between probe and now
        try:
            meta = storage.read_meta()
            completed_phases = set(meta.get('phases_completed', []))
        except Exception:
            completed_phases = set()

    if continue_in_place:
        logger.info(
            f"Continue mode — phases already completed: "
            f"{sorted(completed_phases) if completed_phases else 'none'}"
        )

    # Create model pool and quota tracker (pass provider keys for credential resolution)
    pool = ModelPool(provider_keys=getattr(cfg, '_provider_keys', None))
    quota = QuotaTracker(exp.quota)

    exit_code = 0

    for phase_id in PHASE_IDS:
        # Skip phases that finished in a previous run
        if phase_id in completed_phases:
            logger.info(f"Phase '{phase_id}' already completed, skipping")
            continue

        # In continue mode override the configured mode with the safe resume mode
        if continue_in_place:
            mode = _CONTINUE_MODE[phase_id]
        else:
            mode = cfg.get_phase_mode(phase_id)

        runner = _PHASE_RUNNERS[phase_id]

        logger.info(f"Phase '{phase_id}' starting (mode={mode})")
        if only_models is None:
            storage.update_meta(phase_started=phase_id)

        try:
            runner(cfg, storage, logger, pool, quota, mode, only_models=only_models)
            # When running with a model filter, do NOT write phase_completed so
            # the main process continues to manage meta.json independently.
            if only_models is None:
                storage.update_meta(phase_completed=phase_id)
            logger.info(f"Phase '{phase_id}' completed")
        except PartialPhaseFailure as exc:
            # Some items failed but the phase produced usable output — log prominently,
            # set exit_code=1 for the user's awareness, but CONTINUE the pipeline so
            # downstream phases can process the available data.  Users can re-run
            # with --continue to fill gaps.
            logger.error(
                f"Phase '{phase_id}' completed with partial failures "
                f"({exc.n_failures} failed, {exc.n_successes} succeeded): {exc}"
            )
            if only_models is None:
                storage.update_meta(phase_completed=phase_id)
            exit_code = 1
        except Exception as exc:
            logger.error(f"Phase '{phase_id}' failed: {exc}")
            if only_models is None:
                storage.update_meta(phase_completed=phase_id, status='failed')
            exit_code = 1
            # Stop pipeline on total phase failure (partial output preserved for resume)
            break

    if only_models is None:
        if exit_code == 0:
            storage.update_meta(status='completed')
            logger.info(f"Experiment {exp.id} completed successfully")
        else:
            storage.update_meta(status='failed')
            logger.error(f"Experiment {exp.id} failed — artifacts preserved for --continue")
    else:
        if exit_code == 0:
            logger.info(
                f"Parallel run for {sorted(only_models)} finished successfully"
            )
        else:
            logger.error(
                f"Parallel run for {sorted(only_models)} finished with errors"
            )

    return exit_code
