"""EEA Data Loader — REQ-A-4.x.

Reads all EES artifacts, joins records, classifies validity, and
expands evaluation records into per-aspect analytical units.
"""
from __future__ import annotations

import json
import warnings as _warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EvalRecord:
    """One Phase 5 JSONL line plus validity metadata."""
    id: str
    response_id: str
    datapoint_id: str
    task_id: str
    teacher_model_id: str
    judge_model_id: str
    student_model_id: str          # from Phase 4 join
    scores: dict[str, str]
    evaluated_at: str
    valid: bool
    error_codes: list[str]
    is_self_judging: bool
    is_self_teaching: bool


@dataclass
class AnalyticalUnit:
    """One (response, rubric_aspect) tuple — primary analytical unit (REQ-A-4.2 step 6)."""
    response_id: str
    datapoint_id: str
    task_id: str
    teacher_model_id: str
    student_model_id: str
    judge_model_id: str
    rubric_aspect: str
    score: str          # "High" | "Medium" | "Low"
    score_norm: float   # 1.0 | 0.5 | 0.0
    is_self_judging: bool
    is_self_teaching: bool
    evaluated_at: str


@dataclass
class EESDataModel:
    """Unified in-memory data model (REQ-A-4.2)."""
    run_path: Path
    meta: dict[str, Any]
    config: dict[str, Any]                         # parsed config.yaml snapshot

    # Phase 2 rubrics
    rubrics: dict[str, dict[str, str]]             # task_id -> {factor: desc}

    # Phase 3 datapoints index
    datapoints: dict[str, dict[str, Any]]          # dp_id -> record

    # Phase 4 responses index
    responses: dict[str, dict[str, Any]]           # resp_id -> record

    # Phase 5 evaluation records (raw, with validity flags)
    eval_records: list[EvalRecord]

    # Expanded analytical units (valid records only, one per rubric aspect)
    units: list[AnalyticalUnit]

    # Discovered dimensions
    tasks: list[str]
    teachers: list[str]
    students: list[str]
    judges: list[str]
    aspects_by_task: dict[str, list[str]]           # task_id -> [factor, ...]
    target_attrs_by_task: dict[str, dict[str, list[str]]]  # task_id -> {attr: [vals]}

    # Summary counts
    total_records: int
    valid_records: int
    self_judging_count: int
    self_teaching_count: int
    both_count: int

    # Load-time warnings (missing files, inferred dimensions, etc.)
    load_warnings: list[str]

    # True when meta.status != "completed"
    is_partial: bool


# ---------------------------------------------------------------------------
# Score normalisation helper
# ---------------------------------------------------------------------------

SCORE_MAP: dict[str, float] = {"High": 1.0, "Medium": 0.5, "Low": 0.0}
VALID_SCORES: frozenset[str] = frozenset(SCORE_MAP.keys())


def is_valid_score(score: str) -> bool:
    """Check if a score string is valid (ordinal or continuous float)."""
    if score in VALID_SCORES:
        return True
    try:
        v = float(score)
        return 0.0 <= v <= 1.0
    except (ValueError, TypeError):
        return False


def score_norm(score: str) -> float:
    """Convert score string to numeric value.

    Handles both ordinal LLM scores ("High"/"Medium"/"Low") and continuous
    metric judge scores (e.g. "0.8423").  Metric judges return float strings
    in [0, 1] which are parsed directly.
    """
    if score in SCORE_MAP:
        return SCORE_MAP[score]
    try:
        v = float(score)
        return max(0.0, min(1.0, v))
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_ees(run_path: str | Path, partial_ok: bool = False) -> EESDataModel:
    """Load an EES experiment folder into the unified data model (REQ-A-4.x).

    Parameters
    ----------
    run_path:
        Path to the experiment folder (the ``{experiment_id}`` subfolder
        under ``storage_folder``).
    partial_ok:
        If False (default), prints a warning when the experiment status is
        not ``"completed"``; if True, suppresses that warning.

    Returns
    -------
    EESDataModel
        Fully joined data model.  Loading warnings are stored in
        ``model.load_warnings``; they do not raise exceptions.
    """
    run_path = Path(run_path)
    load_warnings: list[str] = []

    # ------------------------------------------------------------------
    # Step 1 – meta.json
    # ------------------------------------------------------------------
    meta_file = run_path / 'meta.json'
    if not meta_file.exists():
        raise FileNotFoundError(
            f"EES folder has no meta.json: {run_path}. "
            "Is this a valid experiment folder?"
        )
    with open(meta_file, encoding='utf-8') as f:
        meta = json.load(f)

    is_partial = meta.get('status') != 'completed'
    if is_partial and not partial_ok:
        load_warnings.append(
            f"Experiment status is '{meta.get('status')}' (not completed). "
            "Analysis reflects only artifacts present so far. "
            "Pass --partial-ok to suppress this warning."
        )

    # ------------------------------------------------------------------
    # Step 2 – config.yaml
    # ------------------------------------------------------------------
    config_file = run_path / 'config.yaml'
    if not config_file.exists():
        load_warnings.append(f"config.yaml not found in {run_path}; "
                             "some metadata may be unavailable.")
        config: dict = {}
    else:
        with open(config_file, encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

    # ------------------------------------------------------------------
    # Step 3 – Phase 2 rubrics
    # ------------------------------------------------------------------
    rubrics: dict[str, dict] = {}
    phase2_dir = run_path / 'phase2_rubric'
    if phase2_dir.exists():
        for rf in phase2_dir.glob('*.rubric.json'):
            task_id = rf.name.replace('.rubric.json', '')
            try:
                with open(rf, encoding='utf-8') as f:
                    rubrics[task_id] = json.load(f)
            except Exception as exc:
                load_warnings.append(f"Could not read rubric {rf}: {exc}")
    else:
        load_warnings.append(f"phase2_rubric/ not found in {run_path}")

    # ------------------------------------------------------------------
    # Step 4 – Phase 3 datapoints
    # ------------------------------------------------------------------
    datapoints: dict[str, dict] = {}
    phase3_dir = run_path / 'phase3_datapoints'
    teacher_set: set[str] = set()
    task_set: set[str] = set()
    target_attrs_by_task: dict[str, dict[str, list]] = {}

    if phase3_dir.exists():
        for dpf in phase3_dir.glob('*.datapoints.jsonl'):
            for lineno, line in enumerate(_iter_jsonl(dpf, load_warnings), 1):
                dp_id = line.get('id', '')
                if dp_id:
                    datapoints[dp_id] = line
                task_id = line.get('task_id', '')
                teacher_id = line.get('teacher_model_id', '')
                if task_id:
                    task_set.add(task_id)
                if teacher_id:
                    teacher_set.add(teacher_id)
                # Collect target attribute keys/values
                attrs = line.get('sampled_target_attributes', {})
                if attrs and task_id:
                    ta = target_attrs_by_task.setdefault(task_id, {})
                    for k, v in attrs.items():
                        ta.setdefault(k, set()).add(v)
    else:
        load_warnings.append(f"phase3_datapoints/ not found in {run_path}")

    # Convert sets to sorted lists for deterministic output
    target_attrs_by_task_final: dict[str, dict[str, list[str]]] = {
        task: {k: sorted(v) for k, v in attrs.items()}
        for task, attrs in target_attrs_by_task.items()
    }

    # ------------------------------------------------------------------
    # Step 5 – Phase 4 responses
    # ------------------------------------------------------------------
    responses: dict[str, dict] = {}
    phase4_dir = run_path / 'phase4_responses'
    student_set: set[str] = set()

    if phase4_dir.exists():
        for rspf in phase4_dir.glob('*.responses.jsonl'):
            for line in _iter_jsonl(rspf, load_warnings):
                resp_id = line.get('id', '')
                if resp_id:
                    responses[resp_id] = line
                student_id = line.get('student_model_id', '')
                task_id = line.get('task_id', '')
                if student_id:
                    student_set.add(student_id)
                if task_id:
                    task_set.add(task_id)
    else:
        load_warnings.append(f"phase4_responses/ not found in {run_path}")

    # ------------------------------------------------------------------
    # Step 6 – Phase 5 evaluations — classify validity + expand tuples
    # ------------------------------------------------------------------
    eval_records: list[EvalRecord] = []
    units: list[AnalyticalUnit] = []
    judge_set: set[str] = set()

    # Build rubric key sets for quick validity checks
    rubric_keys: dict[str, set[str]] = {
        t: set(r.keys()) for t, r in rubrics.items()
    }
    # Collect aspects per task from Phase 2 (authoritative) + Phase 5 supplements
    aspects_by_task: dict[str, set[str]] = {
        t: set(r.keys()) for t, r in rubrics.items()
    }

    phase5_dir = run_path / 'phase5_evaluations'
    if phase5_dir.exists():
        for evf in phase5_dir.glob('*.evaluations.jsonl'):
            for line in _iter_jsonl(evf, load_warnings):
                rec = _classify_eval_record(
                    line=line,
                    responses=responses,
                    datapoints=datapoints,
                    rubric_keys=rubric_keys,
                    load_warnings=load_warnings,
                )
                eval_records.append(rec)

                task_id = rec.task_id
                judge_id = rec.judge_model_id
                if judge_id:
                    judge_set.add(judge_id)
                if task_id:
                    task_set.add(task_id)

                # Supplement aspects from Phase 5 scores if Phase 2 is missing
                if task_id not in aspects_by_task:
                    aspects_by_task[task_id] = set()
                for factor in rec.scores:
                    aspects_by_task[task_id].add(factor)

                # Expand valid records into analytical units (REQ-A-4.2 step 6)
                if rec.valid:
                    for aspect, score in rec.scores.items():
                        units.append(AnalyticalUnit(
                            response_id=rec.response_id,
                            datapoint_id=rec.datapoint_id,
                            task_id=rec.task_id,
                            teacher_model_id=rec.teacher_model_id,
                            student_model_id=rec.student_model_id,
                            judge_model_id=rec.judge_model_id,
                            rubric_aspect=aspect,
                            score=score,
                            score_norm=score_norm(score),
                            is_self_judging=rec.is_self_judging,
                            is_self_teaching=rec.is_self_teaching,
                            evaluated_at=rec.evaluated_at,
                        ))
    else:
        load_warnings.append(
            f"phase5_evaluations/ not found in {run_path}. "
            "No evaluation data available."
        )

    # ------------------------------------------------------------------
    # Step 7 – Supplement dimensions from config.yaml
    # ------------------------------------------------------------------
    config_models = config.get('models', [])
    config_tasks = config.get('tasks', [])

    for m in config_models:
        mname = m.get('name', '')
        roles = m.get('roles', [])
        if 'teacher' in roles and mname:
            teacher_set.add(mname)
        if 'student' in roles and mname:
            student_set.add(mname)
        if 'judge' in roles and mname:
            judge_set.add(mname)
    for t in config_tasks:
        tname = t.get('name', '')
        if tname:
            task_set.add(tname)

    # ------------------------------------------------------------------
    # Step 8 – Summary counts
    # ------------------------------------------------------------------
    self_judging_count = sum(1 for r in eval_records if r.is_self_judging)
    self_teaching_count = sum(1 for r in eval_records if r.is_self_teaching)
    both_count = sum(1 for r in eval_records if r.is_self_judging and r.is_self_teaching)
    valid_records = sum(1 for r in eval_records if r.valid)

    return EESDataModel(
        run_path=run_path,
        meta=meta,
        config=config,
        rubrics=rubrics,
        datapoints=datapoints,
        responses=responses,
        eval_records=eval_records,
        units=units,
        tasks=sorted(task_set),
        teachers=sorted(teacher_set),
        students=sorted(student_set),
        judges=sorted(judge_set),
        aspects_by_task={t: sorted(v) for t, v in aspects_by_task.items()},
        target_attrs_by_task=target_attrs_by_task_final,
        total_records=len(eval_records),
        valid_records=valid_records,
        self_judging_count=self_judging_count,
        self_teaching_count=self_teaching_count,
        both_count=both_count,
        load_warnings=load_warnings,
        is_partial=is_partial,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _iter_jsonl(
    path: Path,
    load_warnings: list[str],
) -> list[dict]:
    """Read a JSONL file, skipping unparseable lines (REQ-A-4.3)."""
    records: list[dict] = []
    if not path.exists():
        return records
    for lineno, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            records.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            phase_tag = _phase_tag_from_path(path)
            load_warnings.append(
                f"{path.name}:{lineno}: JSON parse error ({exc}). "
                f"Record classified as {phase_tag}."
            )
    return records


def _phase_tag_from_path(path: Path) -> str:
    parent = path.parent.name
    tags = {
        'phase3_datapoints': 'PARSE_ERROR_P3',
        'phase4_responses': 'PARSE_ERROR_P4',
        'phase5_evaluations': 'PARSE_ERROR_P5',
    }
    return tags.get(parent, 'PARSE_ERROR')


def _classify_eval_record(
    line: dict,
    responses: dict[str, dict],
    datapoints: dict[str, dict],
    rubric_keys: dict[str, set[str]],
    load_warnings: list[str],
) -> EvalRecord:
    """Classify a Phase 5 record as valid/invalid per REQ-A-3.2 / REQ-A-5.2.1."""
    error_codes: list[str] = []

    record_id = line.get('id', '')
    response_id = line.get('response_id', '')
    datapoint_id = line.get('datapoint_id', '')
    task_id = line.get('task_id', '')
    teacher_model_id = line.get('teacher_model_id', '')
    judge_model_id = line.get('judge_model_id', '')
    scores = line.get('scores', {})
    evaluated_at = line.get('evaluated_at', '')

    # Resolve student_model_id from Phase 4 response join
    student_model_id = ''
    resp_record = responses.get(response_id)
    if resp_record is None:
        error_codes.append('MISSING_RESPONSE')
    else:
        student_model_id = resp_record.get('student_model_id', '')

    # Condition 4: datapoint must exist
    if datapoint_id not in datapoints:
        error_codes.append('MISSING_DATAPOINT')

    # Condition 2: validate scores against rubric
    if isinstance(scores, dict):
        expected_keys = rubric_keys.get(task_id, set())
        if expected_keys:
            missing = expected_keys - set(scores.keys())
            if missing:
                error_codes.append('INCOMPLETE_SCORES')
        # Check score values (ordinal or continuous float from metric judges)
        for val in scores.values():
            if not is_valid_score(val):
                error_codes.append('INVALID_SCORE_VALUE')
                break
    else:
        error_codes.append('INCOMPLETE_SCORES')
        scores = {}

    valid = len(error_codes) == 0

    is_self_judging = bool(
        judge_model_id and student_model_id and
        judge_model_id == student_model_id
    )
    is_self_teaching = bool(
        teacher_model_id and student_model_id and
        teacher_model_id == student_model_id
    )

    return EvalRecord(
        id=record_id,
        response_id=response_id,
        datapoint_id=datapoint_id,
        task_id=task_id,
        teacher_model_id=teacher_model_id,
        judge_model_id=judge_model_id,
        student_model_id=student_model_id,
        scores=scores if isinstance(scores, dict) else {},
        evaluated_at=evaluated_at,
        valid=valid,
        error_codes=error_codes,
        is_self_judging=is_self_judging,
        is_self_teaching=is_self_teaching,
    )
