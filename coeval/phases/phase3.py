"""Phase 3 — Data Generation (REQ-7.1, REQ-7.4, §4, §5.3.4, §6.2.4)."""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from ..config import CoEvalConfig, TaskConfig, ModelConfig, SamplingConfig
from ..interfaces import ModelPool
from ..logger import RunLogger
from ..prompts import get_prompt
from ..storage import ExperimentStorage
from .utils import call_llm_json, QuotaTracker


def run_phase3(
    cfg: CoEvalConfig,
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None:
    """Execute Phase 3 for all (task, teacher) pairs according to phase_mode."""
    teachers = cfg.get_models_by_role('teacher')
    errors: list[str] = []

    for task in cfg.tasks:
        for teacher in teachers:
            try:
                _generate_datapoints(task, teacher, storage, logger, pool, quota, phase_mode)
            except Exception as exc:
                msg = (
                    f"Phase 3: data generation failed for "
                    f"(task='{task.name}', teacher='{teacher.name}'): {exc}"
                )
                logger.error(msg)
                errors.append(msg)

    if errors:
        raise RuntimeError(
            f"Phase 3 completed with {len(errors)} error(s):\n" + "\n".join(errors)
        )


def _generate_datapoints(
    task: TaskConfig,
    teacher: ModelConfig,
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None:
    task_id = task.name
    teacher_id = teacher.name
    total = task.sampling.total
    label = f"(task='{task_id}', teacher='{teacher_id}')"

    # Keep mode: skip entirely
    if phase_mode == 'Keep':
        logger.info(f"Phase 3: {label} — Keep mode, skipping")
        return

    # Model mode: skip if this teacher already has a datapoints file
    if phase_mode == 'Model' and storage.datapoints_path(task_id, teacher_id).exists():
        logger.info(f"Phase 3: {label} — Model mode, file exists, skipping")
        return

    # Extend mode: count existing items and only generate the gap
    existing_count = storage.count_datapoints(task_id, teacher_id)
    if phase_mode == 'Extend':
        if existing_count >= total:
            logger.info(
                f"Phase 3: {label} — Extend mode, already have {existing_count}/{total} items, skipping"
            )
            return
        to_generate = total - existing_count
        seq_start = existing_count + 1
        logger.info(
            f"Phase 3: {label} — Extend mode, generating {to_generate} more items (have {existing_count})"
        )
    else:
        # New mode
        to_generate = total
        seq_start = 1

    if quota.is_exhausted(teacher_id):
        logger.warning(
            f"Quota exhausted for model {teacher_id} in phase data_generation; "
            f"skipping {label}"
        )
        return

    # Load attribute maps from Phase 1
    target_attrs = storage.read_target_attrs(task_id)
    nuanced_attrs = storage.read_nuanced_attrs(task_id)

    iface = pool.get(teacher)
    params = teacher.get_parameters_for_role('teacher')

    logger.info(f"Phase 3: {label} — generating {to_generate} datapoints")

    for i in range(to_generate):
        if quota.is_exhausted(teacher_id):
            logger.warning(
                f"Quota exhausted for model {teacher_id} after {i} items in phase data_generation"
            )
            break

        seq = seq_start + i
        sampled_target = _sample_attrs(target_attrs, task.sampling.target)
        sampled_nuanced = _sample_attrs(nuanced_attrs, task.sampling.nuance)

        prompt = get_prompt(
            'sample',
            task.prompt_library,
            teacher_id,
            {
                'task_description': task.description,
                'output_description': task.output_description,
                'target_attributes': json.dumps(sampled_target),
                'nuanced_attributes': json.dumps(sampled_nuanced),
            },
        )

        result = call_llm_json(iface, prompt, params)
        quota.consume(teacher_id)

        dp_id = f"{task_id}__{teacher_id}__{seq:05d}"
        record: dict = {
            'id': dp_id,
            'task_id': task_id,
            'teacher_model_id': teacher_id,
            'sampled_target_attributes': sampled_target,
            'prompt': result['prompt'],
            'reference_response': result['response'],
            'generated_at': _now_iso(),
        }
        if task.store_nuanced:
            record['sampled_nuanced_attributes'] = sampled_nuanced

        storage.append_datapoint(task_id, teacher_id, record)

    logger.info(
        f"Phase 3: {label} — done, "
        f"{storage.count_datapoints(task_id, teacher_id)} total datapoints in file"
    )


# ---------------------------------------------------------------------------
# Sampling algorithm (REQ-5.3.4)
# ---------------------------------------------------------------------------


def _sample_attrs(attr_map: dict[str, list], target_spec) -> dict[str, str]:
    """Sample a subset of attribute key-value pairs per the spec algorithm."""
    if not attr_map:
        return {}

    attr_names = list(attr_map.keys())

    if target_spec == 'all':
        selected_names = attr_names
    else:
        lo, hi = int(target_spec[0]), int(target_spec[1])
        n = random.randint(lo, min(hi, len(attr_names)))
        selected_names = random.sample(attr_names, n)

    return {
        name: random.choice(attr_map[name])
        for name in selected_names
        if attr_map[name]
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
