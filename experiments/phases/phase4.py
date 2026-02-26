"""Phase 4 — Response Collection (REQ-7.1, §4, §6.2.5)."""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import CoEvalConfig, TaskConfig, ModelConfig
from ..interfaces import ModelPool
from ..logger import RunLogger
from ..prompts import get_prompt
from ..storage import ExperimentStorage
from .utils import QuotaTracker


def run_phase4(
    cfg: CoEvalConfig,
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None:
    """Execute Phase 4 for all (task, teacher, student) triples."""
    teachers = cfg.get_models_by_role('teacher')
    students = cfg.get_models_by_role('student')
    errors: list[str] = []

    for task in cfg.tasks:
        for teacher in teachers:
            for student in students:
                try:
                    _collect_responses(
                        task, teacher, student, storage, logger, pool, quota, phase_mode
                    )
                except Exception as exc:
                    msg = (
                        f"Phase 4: response collection failed for "
                        f"(task='{task.name}', teacher='{teacher.name}', "
                        f"student='{student.name}'): {exc}"
                    )
                    logger.error(msg)
                    errors.append(msg)

    if errors:
        raise RuntimeError(
            f"Phase 4 completed with {len(errors)} error(s):\n" + "\n".join(errors)
        )


def _collect_responses(
    task: TaskConfig,
    teacher: ModelConfig,
    student: ModelConfig,
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None:
    task_id = task.name
    teacher_id = teacher.name
    student_id = student.name
    label = f"(task='{task_id}', teacher='{teacher_id}', student='{student_id}')"

    # Keep mode: skip entirely
    if phase_mode == 'Keep':
        logger.info(f"Phase 4: {label} — Keep mode, skipping")
        return

    # Model mode: skip if responses file already exists for this student
    if phase_mode == 'Model' and storage.response_file_exists(task_id, teacher_id, student_id):
        logger.info(f"Phase 4: {label} — Model mode, file exists, skipping")
        return

    datapoints = storage.read_datapoints(task_id, teacher_id)
    if not datapoints:
        logger.warning(f"Phase 4: {label} — no datapoints found, skipping")
        return

    # Extend mode: skip datapoints that already have a response
    if phase_mode == 'Extend':
        responded_ids = storage.get_responded_datapoint_ids(task_id, teacher_id, student_id)
        datapoints = [dp for dp in datapoints if dp['id'] not in responded_ids]
        if not datapoints:
            logger.info(f"Phase 4: {label} — Extend mode, all datapoints already responded, skipping")
            return
        logger.info(f"Phase 4: {label} — Extend mode, {len(datapoints)} remaining datapoints")

    if quota.is_exhausted(student_id):
        logger.warning(
            f"Quota exhausted for model {student_id} in phase response_collection; "
            f"skipping {label}"
        )
        return

    iface = pool.get(student)
    params = student.get_parameters_for_role('student')

    logger.info(f"Phase 4: {label} — collecting {len(datapoints)} responses")

    for dp in datapoints:
        if quota.is_exhausted(student_id):
            logger.warning(
                f"Quota exhausted for model {student_id} in phase response_collection"
            )
            break

        prompt = get_prompt(
            'test',
            task.prompt_library,
            student_id,
            {
                'input': dp['prompt'],
                'task_description': task.description,
                'output_description': task.output_description,
            },
        )

        response_text = iface.generate(prompt, params)
        quota.consume(student_id)

        response_id = f"{dp['id']}__{student_id}"
        record = {
            'id': response_id,
            'datapoint_id': dp['id'],
            'task_id': task_id,
            'teacher_model_id': teacher_id,
            'student_model_id': student_id,
            'input': dp['prompt'],
            'response': response_text,
            'generated_at': _now_iso(),
        }
        storage.append_response(task_id, teacher_id, student_id, record)

    logger.info(f"Phase 4: {label} — done")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
