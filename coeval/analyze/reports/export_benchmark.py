"""Robust Benchmark Export — REQ-A-7.11."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from ..loader import EESDataModel
from ..metrics import RobustFilterResult, robust_filter


def export_benchmark(
    model: EESDataModel,
    out_path: Path,
    judge_selection: str = 'top_half',
    agreement_metric: str = 'spa',
    agreement_threshold: float = 1.0,
    teacher_score_formula: str = 'v1',
    benchmark_format: str = 'jsonl',
) -> Path:
    """Export robust benchmark datapoints (REQ-A-7.11).

    Parameters
    ----------
    model:
        Loaded EES data model.
    out_path:
        Output file path (.jsonl or .parquet).
    judge_selection, agreement_metric, agreement_threshold, teacher_score_formula:
        Robust filtering parameters.
    benchmark_format:
        'jsonl' or 'parquet'.

    Returns
    -------
    Path to the written output file.
    """
    rfr = robust_filter(
        model=model,
        judge_selection=judge_selection,
        agreement_metric=agreement_metric,
        agreement_threshold=agreement_threshold,
        teacher_score_formula=teacher_score_formula,
    )

    if rfr.robust_count == 0:
        _print_empty_diagnostics(rfr, out_path)
        raise SystemExit(1)

    records = _build_records(model, rfr)

    if benchmark_format == 'parquet':
        _write_parquet(records, out_path)
    else:
        _write_jsonl(records, out_path)

    _print_summary(rfr, len(records), out_path)
    return out_path


def _build_records(model: EESDataModel, rfr: RobustFilterResult) -> list[dict]:
    """Build export records per robust datapoint (REQ-A-7.11.2)."""
    exp_id = model.meta.get('experiment_id', model.run_path.name)
    J_star_set = set(rfr.J_star)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    records = []
    for dp_id in sorted(rfr.D_robust):
        dp = model.datapoints.get(dp_id)
        if not dp:
            continue

        task_id = dp.get('task_id', '')
        rubric = model.rubrics.get(task_id, {})

        # Build student_scores: for each (student, aspect) → plurality vote among J*
        student_aspect_scores: dict[tuple, list] = defaultdict(list)
        for u in model.units:
            if (u.datapoint_id == dp_id
                    and u.judge_model_id in J_star_set):
                student_aspect_scores[(u.student_model_id, u.rubric_aspect)].append(u.score)

        student_scores: dict[str, dict] = {}
        for (student, aspect), score_list in student_aspect_scores.items():
            if not score_list:
                continue
            # Plurality vote; ties broken conservatively (Low > Medium > High)
            from collections import Counter
            counts = Counter(score_list)
            # Conservative tie-breaking order
            for preferred in ('Low', 'Medium', 'High'):
                max_count = max(counts.values())
                tied = [s for s, c in counts.items() if c == max_count]
                if preferred in tied:
                    winner = preferred
                    break
            else:
                winner = score_list[0]
            student_scores.setdefault(student, {})[aspect] = winner

        consistent_fraction = rfr.consistent_fractions.get(dp_id, 0.0)

        records.append({
            'schema_version': 'coeval-benchmark-v1',
            'experiment_id': exp_id,
            'datapoint_id': dp_id,
            'task_id': task_id,
            'teacher_model_id': dp.get('teacher_model_id', ''),
            'prompt': dp.get('prompt', ''),
            'reference_response': dp.get('reference_response', ''),
            'sampled_target_attributes': dp.get('sampled_target_attributes', {}),
            'rubric': rubric,
            'student_scores': student_scores,
            'judge_set': rfr.J_star,
            'agreement_metric': rfr.agreement_metric,
            'agreement_threshold': rfr.agreement_threshold,
            'consistent_fraction': round(consistent_fraction, 4),
            'exported_at': now,
        })

    return records


def _write_jsonl(records: list[dict], out_path: Path) -> None:
    """Write records as JSONL (REQ-A-7.11.3)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def _write_parquet(records: list[dict], out_path: Path) -> None:
    """Write records as Parquet (REQ-A-7.11.3, REQ-A-10.4)."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError(
            "pyarrow is required for Parquet export. "
            "Install it with: pip install pyarrow"
        ) from exc

    # Serialise nested fields to JSON strings for Parquet
    flat_records = []
    for rec in records:
        flat = rec.copy()
        flat['sampled_target_attributes'] = json.dumps(rec['sampled_target_attributes'])
        flat['rubric'] = json.dumps(rec['rubric'])
        flat['student_scores'] = json.dumps(rec['student_scores'])
        flat['judge_set'] = json.dumps(rec['judge_set'])
        flat_records.append(flat)

    table = pa.Table.from_pylist(flat_records)
    # Attach schema-level metadata (compatible with all pyarrow versions)
    table = table.replace_schema_metadata(
        {b'coeval_schema_version': b'coeval-benchmark-v1'}
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, str(out_path))


def _print_summary(rfr: RobustFilterResult, n: int, out_path: Path) -> None:
    print(f"Exported {n} robust datapoints from experiment")
    print(f"  Judge set (J*):   {rfr.J_star}")
    print(f"  Teacher set (T*): {rfr.T_star}")
    print(f"  Agreement metric: {rfr.agreement_metric}")
    print(f"  Threshold θ:      {rfr.agreement_threshold}")
    print(f"  Output:           {out_path}")


def _print_empty_diagnostics(rfr: RobustFilterResult, out_path: Path) -> None:
    d = rfr.diagnostics
    print("ERROR: Robust filter produced 0 datapoints. No export generated.", file=sys.stderr)
    print(f"\nFiltering diagnostics:", file=sys.stderr)
    print(f"  J* = {d.get('J_star', [])}, metric = {d.get('agreement_metric', '')}", file=sys.stderr)
    print(f"  T* = {d.get('T_star', [])}, formula = {d.get('formula', '')}", file=sys.stderr)
    print(f"  Datapoints from T*: {d.get('T_star_count', 0)} / {d.get('all_count', 0)}", file=sys.stderr)
    print(f"  Robust: 0 / {d.get('T_star_count', 0)} (θ={d.get('agreement_threshold', '')})", file=sys.stderr)
    print(f"\nSuggested actions:", file=sys.stderr)
    print(f"  • Lower --agreement-threshold", file=sys.stderr)
    print(f"  • Use --judge-selection all", file=sys.stderr)
    print(f"  • Check coverage-summary for invalid records", file=sys.stderr)
