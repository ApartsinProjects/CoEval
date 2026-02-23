"""Phase 5 — Evaluation (REQ-7.1, REQ-7.5, REQ-7.6, §4, §6.2.6, §9)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..config import CoEvalConfig, TaskConfig, ModelConfig
from ..interfaces import ModelPool
from ..logger import RunLogger
from ..prompts import get_prompt
from ..storage import ExperimentStorage
from .utils import call_llm_json, call_llm_word, QuotaTracker


def run_phase5(
    cfg: CoEvalConfig,
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None:
    """Execute Phase 5 for all (task, teacher, judge) triples."""
    teachers = cfg.get_models_by_role('teacher')
    judges = cfg.get_models_by_role('judge')
    errors: list[str] = []

    for task in cfg.tasks:
        for teacher in teachers:
            for judge in judges:
                try:
                    _evaluate(task, teacher, judge, storage, logger, pool, quota, phase_mode)
                except Exception as exc:
                    msg = (
                        f"Phase 5: evaluation failed for "
                        f"(task='{task.name}', teacher='{teacher.name}', "
                        f"judge='{judge.name}'): {exc}"
                    )
                    logger.error(msg)
                    errors.append(msg)

    if errors:
        raise RuntimeError(
            f"Phase 5 completed with {len(errors)} error(s):\n" + "\n".join(errors)
        )


def _evaluate(
    task: TaskConfig,
    teacher: ModelConfig,
    judge: ModelConfig,
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None:
    task_id = task.name
    teacher_id = teacher.name
    judge_id = judge.name
    label = f"(task='{task_id}', teacher='{teacher_id}', judge='{judge_id}')"

    # Keep mode: skip entirely
    if phase_mode == 'Keep':
        logger.info(f"Phase 5: {label} — Keep mode, skipping")
        return

    # Model mode: skip if evaluation file already exists for this judge
    if phase_mode == 'Model' and storage.evaluation_file_exists(task_id, teacher_id, judge_id):
        logger.info(f"Phase 5: {label} — Model mode, file exists, skipping")
        return

    # Load rubric and datapoints index (REQ-7.5)
    rubric = storage.read_rubric(task_id)
    datapoints_index = storage.index_datapoints(task_id, teacher_id)

    # Extend mode: determine new rubric factors only
    if phase_mode == 'Extend':
        existing_evals = storage.read_evaluations(task_id, teacher_id, judge_id)
        evaluated_factors: set[str] = set()
        for ev in existing_evals:
            evaluated_factors.update(ev.get('scores', {}).keys())
        new_factors = {k: v for k, v in rubric.items() if k not in evaluated_factors}
        if not new_factors:
            logger.info(f"Phase 5: {label} — Extend mode, no new rubric factors, skipping")
            return
        rubric_to_use = new_factors
        logger.info(
            f"Phase 5: {label} — Extend mode, evaluating {len(new_factors)} new factor(s)"
        )
    else:
        rubric_to_use = rubric

    # Collect all response files for this (task, teacher) pair
    all_responses: list[dict] = []
    for resp_path in storage.iter_response_files(task_id, teacher_id):
        for line in resp_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line:
                all_responses.append(json.loads(line))

    if not all_responses:
        logger.warning(f"Phase 5: {label} — no responses found, skipping")
        return

    # Already-evaluated response IDs (for Extend mode)
    evaluated_resp_ids = (
        storage.get_evaluated_response_ids(task_id, teacher_id, judge_id)
        if phase_mode == 'Extend' else set()
    )

    if quota.is_exhausted(judge_id):
        logger.warning(
            f"Quota exhausted for model {judge_id} in phase evaluation; skipping {label}"
        )
        return

    iface = pool.get(judge)
    params = judge.get_parameters_for_role('judge')

    logger.info(
        f"Phase 5: {label} — evaluating {len(all_responses)} responses "
        f"with {len(rubric_to_use)} factor(s) in '{task.evaluation_mode}' mode"
    )

    for resp in all_responses:
        if phase_mode == 'Extend' and resp['id'] in evaluated_resp_ids:
            continue  # already fully evaluated in a prior run
        if quota.is_exhausted(judge_id):
            logger.warning(
                f"Quota exhausted for model {judge_id} in phase evaluation"
            )
            break

        # Resolve reference_response from datapoints index (REQ-7.5)
        dp_id = resp['datapoint_id']
        if dp_id not in datapoints_index:
            logger.error(
                f"Phase 5: datapoint_id '{dp_id}' not found in datapoints index; "
                f"skipping response '{resp['id']}'"
            )
            continue

        dp = datapoints_index[dp_id]
        reference_response = dp['reference_response']
        target_attrs_str = json.dumps(dp.get('sampled_target_attributes', {}))

        scores = _score_response(
            task=task,
            rubric=rubric_to_use,
            response=resp,
            reference_response=reference_response,
            target_attrs_str=target_attrs_str,
            judge_id=judge_id,
            iface=iface,
            params=params,
            pool=pool,
            quota=quota,
        )

        eval_id = f"{resp['id']}__{judge_id}"
        record = {
            'id': eval_id,
            'response_id': resp['id'],
            'datapoint_id': dp_id,
            'task_id': task_id,
            'teacher_model_id': teacher_id,
            'judge_model_id': judge_id,
            'scores': scores,
            'evaluated_at': _now_iso(),
        }
        storage.append_evaluation(task_id, teacher_id, judge_id, record)

    logger.info(f"Phase 5: {label} — done")


def _score_response(
    task: TaskConfig,
    rubric: dict[str, str],
    response: dict,
    reference_response: str,
    target_attrs_str: str,
    judge_id: str,
    iface,
    params: dict,
    pool: ModelPool,
    quota: QuotaTracker,
) -> dict[str, str]:
    """Score a single response against the rubric using the configured evaluation_mode."""
    common_vars = {
        'task_description': task.description,
        'output_description': task.output_description,
        'input': response['input'],
        'target_attributes': target_attrs_str,
        'reference_response': reference_response,
        'response': response['response'],
    }

    if task.evaluation_mode == 'single':
        rubric_text = '\n'.join(
            f'- {factor}: {desc}' for factor, desc in rubric.items()
        )
        prompt = get_prompt(
            'evaluate_single',
            task.prompt_library,
            judge_id,
            {**common_vars, 'rubric': rubric_text},
        )
        result = call_llm_json(iface, prompt, params)
        quota.consume(judge_id)
        # Validate and normalise scores
        scores: dict[str, str] = {}
        for factor in rubric:
            val = str(result.get(factor, '')).strip()
            if val not in ('High', 'Medium', 'Low'):
                val = 'Low'  # fallback for malformed responses
            scores[factor] = val
        return scores

    else:  # per_factor
        scores = {}
        for factor, desc in rubric.items():
            if quota.is_exhausted(judge_id):
                break
            prompt = get_prompt(
                'evaluate_per_factor',
                task.prompt_library,
                judge_id,
                {
                    **common_vars,
                    'rubric_factor_name': factor,
                    'rubric_factor_description': desc,
                },
            )
            word = call_llm_word(iface, prompt, params)
            quota.consume(judge_id)
            scores[factor] = word
        return scores


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
