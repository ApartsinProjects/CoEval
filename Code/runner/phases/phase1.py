"""Phase 1 — Attribute Mapping (REQ-7.1, §4, §5.3.2, §5.3.3)."""
from __future__ import annotations

from ..config import CoEvalConfig, TaskConfig, ModelConfig
from ..interfaces import ModelPool
from ..logger import RunLogger
from ..prompts import get_prompt
from ..storage import ExperimentStorage
from .utils import call_llm_json, merge_attr_maps, QuotaTracker

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_phase1(
    cfg: CoEvalConfig,
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None:
    """Execute Phase 1 for all tasks according to phase_mode."""
    teachers = cfg.get_models_by_role('teacher')
    errors: list[str] = []

    for task in cfg.tasks:
        try:
            _resolve_attrs(
                task, 'target', teachers, storage, logger, pool, quota, phase_mode
            )
        except Exception as exc:
            msg = f"Phase 1: target_attrs failed for task '{task.name}': {exc}"
            logger.error(msg)
            errors.append(msg)

        try:
            _resolve_attrs(
                task, 'nuanced', teachers, storage, logger, pool, quota, phase_mode
            )
        except Exception as exc:
            msg = f"Phase 1: nuanced_attrs failed for task '{task.name}': {exc}"
            logger.error(msg)
            errors.append(msg)

    if errors:
        raise RuntimeError(
            f"Phase 1 completed with {len(errors)} error(s):\n" + "\n".join(errors)
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_attrs(
    task: TaskConfig,
    kind: str,   # 'target' or 'nuanced'
    teachers: list[ModelConfig],
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None:
    """Resolve and write one attribute file (target or nuanced) for a task."""
    attr_value = (
        task.target_attributes if kind == 'target' else task.nuanced_attributes
    )
    exists_fn = storage.target_attrs_exist if kind == 'target' else storage.nuanced_attrs_exist
    write_fn = storage.write_target_attrs if kind == 'target' else storage.write_nuanced_attrs
    prompt_id = 'map_target_attrs' if kind == 'target' else 'map_nuanced_attrs'
    seed = (
        (task.target_attributes_seed or {}) if kind == 'target'
        else (task.nuanced_attributes_seed or {})
    )
    label = f"task '{task.name}' {kind}_attributes"

    # Keep mode: reuse existing artifact
    if phase_mode == 'Keep' and exists_fn(task.name):
        logger.info(f"Phase 1: {label} — Keep mode, reusing existing artifact")
        return

    # Static map: write directly without LLM calls
    if isinstance(attr_value, dict):
        logger.info(f"Phase 1: {label} — static map, writing directly")
        write_fn(task.name, attr_value)
        return

    # auto / complete: call all teachers and merge
    mode_label = attr_value  # "auto" or "complete"
    logger.info(f"Phase 1: {label} — mode={mode_label}, calling {len(teachers)} teacher(s)")

    results: list[dict] = []
    for teacher in teachers:
        model_id = teacher.name
        if quota.is_exhausted(model_id):
            logger.warning(
                f"Quota exhausted for model {model_id} in phase attribute_mapping"
            )
            continue
        iface = pool.get(teacher)
        params = teacher.get_parameters_for_role('teacher')
        prompt = get_prompt(
            prompt_id,
            task.prompt_library,
            model_id,
            {'task_description': task.description},
        )
        logger.info(f"Phase 1: calling teacher '{model_id}' for {label}")
        result = call_llm_json(iface, prompt, params)
        quota.consume(model_id)
        results.append(result)

    # For "complete" mode, merge with seed first (seed values are preserved)
    sources = ([seed] if seed else []) + results
    merged = merge_attr_maps(*sources)
    logger.info(f"Phase 1: {label} merged — {len(merged)} attribute(s)")
    write_fn(task.name, merged)
