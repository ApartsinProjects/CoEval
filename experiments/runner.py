"""EER — Evaluation Experiment Runner: orchestrates the 5-phase pipeline."""
from __future__ import annotations

import sys

from .config import CoEvalConfig, PHASE_IDS
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
) -> int:
    """Execute the full 5-phase pipeline.

    If continue_in_place is True the existing experiment folder is re-opened,
    already-completed phases are skipped, and in-progress phases resume at the
    finest available granularity (per item for phases 3-5, per task for phases 1-2).

    Returns exit code: 0 on success, 1 on failure.
    """
    exp = cfg.experiment

    # Initialize storage
    storage = ExperimentStorage(exp.storage_folder, exp.id)
    storage.initialize(
        config_raw=cfg._raw,
        resume_from_id=exp.resume_from,
        source_storage_folder=exp.storage_folder if exp.resume_from else None,
        continue_in_place=continue_in_place,
    )

    # Set up logger (appends to run.log in EES)
    logger = RunLogger(storage.log_path, min_level=exp.log_level)
    logger.info(f"Experiment {exp.id} {'continued' if continue_in_place else 'started'}")

    if dry_run:
        logger.info("Dry-run mode — no LLM calls will be made")
        print_execution_plan(cfg)
        logger.info("Dry-run complete")
        return 0

    # Read already-completed phases when continuing an existing experiment
    completed_phases: set[str] = set()
    if continue_in_place:
        meta = storage.read_meta()
        completed_phases = set(meta.get('phases_completed', []))
        logger.info(
            f"Continue mode — phases already completed: "
            f"{sorted(completed_phases) if completed_phases else 'none'}"
        )

    # Create model pool and quota tracker
    pool = ModelPool()
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
        storage.update_meta(phase_started=phase_id)

        try:
            runner(cfg, storage, logger, pool, quota, mode)
            storage.update_meta(phase_completed=phase_id)
            logger.info(f"Phase '{phase_id}' completed")
        except Exception as exc:
            logger.error(f"Phase '{phase_id}' failed: {exc}")
            storage.update_meta(phase_completed=phase_id, status='failed')
            exit_code = 1
            # Stop pipeline on phase failure (partial output preserved for resume)
            break

    if exit_code == 0:
        storage.update_meta(status='completed')
        logger.info(f"Experiment {exp.id} completed successfully")
    else:
        storage.update_meta(status='failed')
        logger.error(f"Experiment {exp.id} failed — artifacts preserved for --continue")

    return exit_code
