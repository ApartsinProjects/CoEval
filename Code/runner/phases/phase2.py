"""Phase 2 — Rubric Mapping (REQ-7.1, §4, §5.3.5)."""
from __future__ import annotations

from ..config import CoEvalConfig, TaskConfig, ModelConfig
from ..interfaces import ModelPool
from ..logger import RunLogger
from ..prompts import get_prompt
from ..storage import ExperimentStorage
from .utils import call_llm_json, merge_rubrics, QuotaTracker


def run_phase2(
    cfg: CoEvalConfig,
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
    only_models: set[str] | None = None,
) -> None:
    """Execute Phase 2 for all tasks according to phase_mode.

    Parameters
    ----------
    only_models:
        Accepted but not used — Phase 2 builds task-level rubric maps from
        teacher models and is not filtered by model.  Present for API
        compatibility with the runner's phase-dispatch loop.
    """
    teachers = cfg.get_models_by_role('teacher')
    errors: list[str] = []

    for task in cfg.tasks:
        try:
            _resolve_rubric(task, teachers, storage, logger, pool, quota, phase_mode)
        except Exception as exc:
            msg = f"Phase 2: rubric failed for task '{task.name}': {exc}"
            logger.error(msg)
            errors.append(msg)

    if errors:
        raise RuntimeError(
            f"Phase 2 completed with {len(errors)} error(s):\n" + "\n".join(errors)
        )


def _resolve_rubric(
    task: TaskConfig,
    teachers: list[ModelConfig],
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None:
    label = f"task '{task.name}' rubric"

    # Keep mode: reuse existing artifact
    if phase_mode == 'Keep' and storage.rubric_exists(task.name):
        logger.info(f"Phase 2: {label} — Keep mode, reusing existing artifact")
        return

    # Static map: write directly
    if isinstance(task.rubric, dict):
        logger.info(f"Phase 2: {label} — static map, writing directly")
        storage.write_rubric(task.name, task.rubric)
        return

    # "extend" mode: load existing rubric to seed the merge
    existing_rubric: dict[str, str] = {}
    if task.rubric == 'extend' and storage.rubric_exists(task.name):
        existing_rubric = storage.read_rubric(task.name)
        logger.info(
            f"Phase 2: {label} — extend mode, loaded {len(existing_rubric)} existing factor(s)"
        )

    # auto / extend: call all teachers
    mode_label = task.rubric
    logger.info(f"Phase 2: {label} — mode={mode_label}, calling {len(teachers)} teacher(s)")

    results: list[dict] = []
    for teacher in teachers:
        model_id = teacher.name
        if quota.is_exhausted(model_id):
            logger.warning(
                f"Quota exhausted for model {model_id} in phase rubric_mapping"
            )
            continue
        iface = pool.get(teacher)
        params = teacher.get_parameters_for_role('teacher')
        prompt = get_prompt(
            'autorubric',
            task.prompt_library,
            model_id,
            {
                'task_description': task.description,
                'output_description': task.output_description,
            },
        )
        logger.info(f"Phase 2: calling teacher '{model_id}' for {label}")
        result = call_llm_json(iface, prompt, params)
        quota.consume(model_id)
        results.append(result)

    # Existing rubric takes precedence (its factors are listed first in merge)
    merged = merge_rubrics(existing_rubric, *results)
    logger.info(f"Phase 2: {label} merged — {len(merged)} factor(s)")
    storage.write_rubric(task.name, merged)
