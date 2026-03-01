"""Interactive Summary Dashboard — REQ-A-7.7.

Generates a single self-contained HTML page that unifies teacher, judge, and
student analysis with live filtering controls.  No external file references
except the Chart.js CDN.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..loader import EESDataModel
from ..metrics import (
    compute_all_agreements,
    compute_judge_scores,
    compute_student_scores,
    compute_teacher_scores,
)

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"


def write_summary_report(
    model: EESDataModel,
    out_dir: Path,
    shared_plotly: Path | None = None,  # accepted for API symmetry, not used
) -> Path:
    """Write summary/index.html.  Returns the Path to the written file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    data = _build_data(model)
    html = _render_html(model, data)
    index_path = out_dir / 'index.html'
    index_path.write_text(html, encoding='utf-8')
    return index_path


# ---------------------------------------------------------------------------
# Data assembly
# ---------------------------------------------------------------------------

def _build_data(model: EESDataModel) -> dict[str, Any]:
    """Compute all pre-aggregated data needed by the dashboard."""
    units = model.units
    teachers = model.teachers
    students = model.students
    judges = model.judges
    tasks = model.tasks

    # ------------------------------------------------------------------
    # Teacher ranking (v1, s2, r3 per teacher)
    # ------------------------------------------------------------------
    teacher_scores_map = compute_teacher_scores(units, teachers, students)
    teacher_rows = []
    for t in teachers:
        ts = teacher_scores_map.get(t)
        dp_count = sum(
            1 for dp in model.datapoints.values()
            if dp.get('teacher_model_id') == t
        )
        # tasks covered by this teacher
        tasks_covered = sorted(set(
            dp.get('task_id', '')
            for dp in model.datapoints.values()
            if dp.get('teacher_model_id') == t and dp.get('task_id')
        ))
        teacher_rows.append({
            'teacher': t,
            'v1': round(ts.v1, 4) if ts else 0.0,
            's2': round(ts.s2, 4) if ts else 0.0,
            'r3': round(ts.r3, 4) if ts else 0.0,
            'datapoints': dp_count,
            'tasks': tasks_covered,
        })

    # ------------------------------------------------------------------
    # Judge ranking (spa, wpa, kappa per judge)
    # ------------------------------------------------------------------
    agreements = compute_all_agreements(units, judges)
    judge_scores_map = compute_judge_scores(units, judges, agreements)
    judge_rows = []
    for j in judges:
        jr = judge_scores_map.get(j)
        n_evals = sum(1 for u in units if u.judge_model_id == j)
        judge_rows.append({
            'judge': j,
            'spa': round(jr.spa_mean, 4) if jr and jr.spa_mean is not None else None,
            'wpa': round(jr.wpa_mean, 4) if jr and jr.wpa_mean is not None else None,
            'kappa': round(jr.kappa_mean, 4) if jr and jr.kappa_mean is not None else None,
            'valid_evals': n_evals,
            'degenerate': bool(jr.degenerate if jr else False),
        })

    # ------------------------------------------------------------------
    # Student ranking (overall + by_task, using ALL units as baseline)
    # ------------------------------------------------------------------
    student_scores_map = compute_student_scores(units, students, model.datapoints)
    student_rows = []
    for s in students:
        sr = student_scores_map.get(s)
        student_rows.append({
            'student': s,
            'overall': round(sr.overall, 4) if sr and sr.overall is not None else None,
            'by_task': {k: round(v, 4) for k, v in sr.by_task.items()} if sr else {},
            'by_judge': {k: round(v, 4) for k, v in sr.by_judge.items()} if sr else {},
            'valid_evals': sr.valid_evals if sr else 0,
        })

    # ------------------------------------------------------------------
    # Grouped units: one record per (task, teacher, student, judge) combo
    # with score averaged over aspects.  Used for live recomputation.
    # ------------------------------------------------------------------
    grouped_units = _group_units(units)

    # ------------------------------------------------------------------
    # Default threshold suggestions (median of each metric)
    # ------------------------------------------------------------------
    t_v1_vals = [r['v1'] for r in teacher_rows if r['v1'] > 0]
    t_s2_vals = [r['s2'] for r in teacher_rows if r['s2'] > 0]
    t_r3_vals = [r['r3'] for r in teacher_rows if r['r3'] > 0]

    def _median(vals):
        if not vals:
            return 0.0
        return round(statistics.median(vals), 4)

    j_spa_vals = [r['spa'] for r in judge_rows if r['spa'] is not None]
    j_wpa_vals = [r['wpa'] for r in judge_rows if r['wpa'] is not None]
    j_kappa_vals = [r['kappa'] for r in judge_rows if r['kappa'] is not None]

    return {
        'teachers': teacher_rows,
        'judges': judge_rows,
        'students': student_rows,
        'tasks': tasks,
        'units': grouped_units,
        'defaults': {
            'teacher_thresholds': {
                'v1': _median(t_v1_vals),
                's2': _median(t_s2_vals),
                'r3': _median(t_r3_vals),
            },
            'judge_thresholds': {
                'spa': _median(j_spa_vals),
                'wpa': _median(j_wpa_vals),
                'kappa': _median(j_kappa_vals),
            },
        },
        'meta': {
            'experiment_id': model.meta.get('experiment_id', model.run_path.name),
            'status': model.meta.get('status', 'unknown'),
            'n_tasks': len(tasks),
            'n_teachers': len(teachers),
            'n_students': len(students),
            'n_judges': len(judges),
            'total_evals': model.total_records,
            'valid_evals': model.valid_records,
            'analysis_date': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
    }


def _group_units(units) -> list[dict]:
    """Average score_norm over rubric aspects for each (task, teacher, student, judge) tuple."""
    groups: dict[tuple, list] = defaultdict(list)
    for u in units:
        key = (u.task_id, u.teacher_model_id, u.student_model_id, u.judge_model_id)
        groups[key].append(u.score_norm)
    return [
        {
            'task': k[0], 'teacher': k[1], 'student': k[2], 'judge': k[3],
            'score': round(sum(v) / len(v), 4),
        }
        for k, v in groups.items()
    ]


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _render_html(model: EESDataModel, data: dict) -> str:
    exp_id = data['meta']['experiment_id']
    status = data['meta']['status']
    is_partial = status != 'completed'

    partial_banner = (
        '<div class="partial-notice">'
        'This experiment is not yet complete — analysis reflects only '
        'artifacts present so far.'
        '</div>'
    ) if is_partial else ''

    data_js = json.dumps(data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Summary Dashboard — {exp_id}</title>
  <script src="{_CHARTJS_CDN}"></script>
  <script>const DATA = {data_js};</script>
  <style>
{_CSS}
  </style>
</head>
<body>
{partial_banner}
<div id="header">
  <div id="header-left">
    <h1>CoEval &mdash; Summary Dashboard</h1>
    <span class="header-sub">Experiment: <b>{exp_id}</b></span>
  </div>
  <div id="header-badges">
    <span class="badge badge-status" id="status-badge">{status}</span>
    <span class="badge">Tasks: <b id="hdr-tasks">?</b></span>
    <span class="badge">Models: <b id="hdr-models">?</b></span>
    <span class="badge">Evals: <b id="hdr-evals">?</b></span>
    <span class="badge">Analyzed: <b id="hdr-date">?</b></span>
  </div>
</div>

<div id="control-panel">
  <div class="cp-group">
    <label data-tip="Controls which teacher score formula is used to decide which teachers are &apos;effective&apos;. Only effective teachers contribute to student rankings.">Teacher formula:</label>
    <div class="btn-group" id="teacher-formula-btns">
      <button class="btn-toggle" data-value="v1" onclick="setTeacherFormula('v1')"
        data-tip="V1 Variance: score = Var(student scores) * coverage. Rewards teachers whose questions produce high variance across student responses — a strong signal of discrimination between strong and weak students.">V1 Variance</button>
      <button class="btn-toggle" data-value="s2" onclick="setTeacherFormula('s2')"
        data-tip="S2 Spread: score = mean(|score - mean|) * coverage. Mean absolute deviation of student scores around the teacher mean. Rewards questions that elicit a spread of response quality without being skewed by outliers.">S2 Spread</button>
      <button class="btn-toggle" data-value="r3" onclick="setTeacherFormula('r3')"
        data-tip="R3 Range: score = (max - min) * coverage. Range of student scores for this teacher. Simple and interpretable: a wide range means at least one student answered well and at least one answered poorly.">R3 Range</button>
    </div>
  </div>
  <div class="cp-group">
    <label data-tip="Teachers with a score below this threshold are excluded from student ranking. Default is the median score across all teachers. Drag left to include more teachers, right to be stricter.">Teacher threshold: <b id="t-thr-label">0</b></label>
    <input type="range" id="teacher-threshold" min="0" max="1" step="0.0001"
           oninput="onTeacherThreshold(this.value)"/>
  </div>
  <div class="cp-group">
    <label data-tip="Controls which agreement metric is used to rank judges and decide which are &apos;consensus&apos; judges. Only consensus judges contribute to student rankings.">Judge metric:</label>
    <div class="btn-group" id="judge-metric-btns">
      <button class="btn-toggle" data-value="spa" onclick="setJudgeMetric('spa')"
        data-tip="SPA (Strict Pair Agreement): fraction of (judgeA, judgeB) response-score pairs that agree exactly on the same ordinal level (High / Medium / Low). The strictest agreement metric.">SPA</button>
      <button class="btn-toggle" data-value="wpa" onclick="setJudgeMetric('wpa')"
        data-tip="WPA (Weighted Pair Agreement): like SPA but gives partial credit for near-misses (adjacent levels, e.g. High vs Medium). More lenient than SPA and less sensitive to small disagreements.">WPA</button>
      <button class="btn-toggle" data-value="kappa" onclick="setKappaMetric('kappa')"
        data-tip="Cohen kappa: agreement corrected for chance. kappa = (p_observed - p_expected) / (1 - p_expected). Interpretation: &lt;0.2 slight, 0.2-0.4 fair, 0.4-0.6 moderate, 0.6-0.8 substantial, &gt;0.8 near-perfect.">Kappa</button>
    </div>
  </div>
  <div class="cp-group">
    <label data-tip="Judges with an agreement score below this threshold are excluded from student ranking. Default is the median score across all judges. Drag left to include more judges, right to be stricter.">Judge threshold: <b id="j-thr-label">0.5</b></label>
    <input type="range" id="judge-threshold" min="0" max="1" step="0.001"
           oninput="onJudgeThreshold(this.value)"/>
  </div>
</div>

<div id="main">

  <!-- ============================================================ -->
  <!-- Section 1: Teacher Effectiveness                             -->
  <!-- ============================================================ -->
  <div class="card" id="section-teacher">
    <div class="card-header">
      <h2>1. Teacher Effectiveness</h2>
      <p class="card-desc">
        Higher scores indicate more discriminative questions that reveal
        student ability differences. Effective teachers are highlighted.
      </p>
    </div>
    <div class="card-body two-col">
      <div class="table-side">
        <div class="filter-row">
          <input type="text" class="name-filter" id="filter-teachers"
                 placeholder="Filter teachers..." oninput="renderTeacherTable()"/>
        </div>
        <div id="teacher-table-wrap"></div>
      </div>
      <div class="chart-side">
        <canvas id="teacher-chart" height="260"></canvas>
      </div>
    </div>
    <div style="padding: 0 20px 14px">
      <details class="fig-explain">
        <summary>About this section</summary>
        <div class="explain-body">
          <b>Table:</b> Each row is a teacher model ranked by the selected formula.
          <b>V1</b> = mean student score on items from this teacher;
          <b>S2</b> = score spread (discrimination index — how well items separate strong
          from weak students);
          <b>R3</b> = composite (V1 × S2). Teachers above the current effectiveness
          threshold (control panel) are highlighted green.<br>
          <b>Chart:</b> Bar chart of the selected formula value per teacher.
          Only teachers in the current filter are shown.<br>
          <b>Tip:</b> A high V1 teacher creates items students score well on overall.
          A high S2 teacher creates discriminating items. Both are desirable for a
          useful benchmark.
        </div>
      </details>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- Section 2: Judge Effectiveness                               -->
  <!-- ============================================================ -->
  <div class="card" id="section-judge">
    <div class="card-header">
      <h2>2. Judge Agreement</h2>
      <p class="card-desc">
        Higher agreement = judge is more aligned with consensus scoring.
        Consensus judges pass the current threshold.
      </p>
    </div>
    <div class="card-body two-col">
      <div class="table-side">
        <div class="filter-row">
          <input type="text" class="name-filter" id="filter-judges"
                 placeholder="Filter judges..." oninput="renderJudgeTable()"/>
        </div>
        <div id="judge-table-wrap"></div>
      </div>
      <div class="chart-side">
        <canvas id="judge-chart" height="260"></canvas>
      </div>
    </div>
    <div style="padding: 0 20px 14px">
      <details class="fig-explain">
        <summary>About this section</summary>
        <div class="explain-body">
          <b>Table:</b> Each row is a judge model with inter-judge agreement scores.
          <b>SPA</b> = Simple Percent Agreement (fraction of pairs with identical scores);
          <b>WPA</b> = Weighted Percent Agreement (weighted by unit count);
          <b>κ</b> = Cohen's Kappa (chance-corrected agreement). Judges above the
          current agreement threshold are highlighted as &ldquo;consensus judges&rdquo;
          and are used in the student ranking computation.<br>
          <b>Chart:</b> Bar chart comparing agreement values per judge for the selected
          metric (SPA / WPA / Kappa).<br>
          <b>Kappa guide:</b> &lt;0 worse than chance; 0–0.2 slight; 0.2–0.4 fair;
          0.4–0.6 moderate; 0.6–0.8 substantial; &gt;0.8 near-perfect.
        </div>
      </details>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- Section 3: Student Ranking                                   -->
  <!-- ============================================================ -->
  <div class="card" id="section-student">
    <div class="card-header">
      <h2>3. Student Ranking</h2>
      <p class="card-desc">
        Rankings computed using only effective teachers and consensus judges.
        Adjust thresholds above to see how rankings change.
      </p>
    </div>
    <div class="card-body">
      <div class="view-tabs" id="student-view-tabs">
        <button class="tab-btn active" onclick="setStudentView('overall')">Overall</button>
        <button class="tab-btn" onclick="setStudentView('by-task')">By Task</button>
        <button class="tab-btn" onclick="setStudentView('by-judge')">By Judge</button>
        <button class="tab-btn" onclick="setStudentView('side-by-side')">Side-by-Side</button>
      </div>
      <div class="filter-row">
        <input type="text" class="name-filter" id="filter-students"
               placeholder="Filter students..." oninput="renderStudentSection()"/>
        <span id="student-coverage-info" class="coverage-info"></span>
      </div>
      <div id="student-section-body"></div>
      <details class="fig-explain" style="margin-top:14px">
        <summary>About this section</summary>
        <div class="explain-body">
          <b>Overall tab:</b> Mean normalised score per student across all rubric aspects,
          filtered by effective teachers and consensus judges. Higher = better.<br>
          <b>By Task tab:</b> Same scores broken down per task — reveals whether a student
          model excels on some tasks but struggles on others.<br>
          <b>By Judge tab:</b> Scores broken down per judge — useful for detecting
          judge-dependent rankings. Stable rankings across judges indicate robust results.<br>
          <b>Side-by-Side tab:</b> All four views above combined in a compact comparison table.<br>
          <b>Normalised score:</b> High = 1.0, Medium = 0.5, Low = 0.0. The mean is taken
          over all valid evaluation units that pass the active teacher and judge filters.<br>
          <b>⚠SJ</b> = self-judging (judge = student model, may inflate scores).
          <b>⚠ST</b> = self-teaching (teacher = student model, may inflate quality signal).
        </div>
      </details>
    </div>
  </div>

</div><!-- #main -->

<footer>
  Generated by CoEval EEA &mdash;
  <span id="ftr-date"></span>
</footer>

<script>
{_JS}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #f4f6fa;
  --card-bg: #fff;
  --header-bg: #14213d;
  --cp-bg: #fff;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --green: #16a34a;
  --green-bg: #dcfce7;
  --gray: #9ca3af;
  --gray-bg: #f3f4f6;
  --border: #e5e7eb;
  --text: #1f2937;
  --text-muted: #6b7280;
  --th-bg: #f0f4f8;
  --row-hover: #f8fafc;
  --bar-color: #bfdbfe;
  --bar-effective: #86efac;
  --shadow: 0 1px 3px rgba(0,0,0,.10);
}

body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: var(--bg); color: var(--text); font-size: 14px; }

/* ---- Header ---- */
#header {
  background: var(--header-bg); color: #fff;
  padding: 12px 24px; display: flex; justify-content: space-between;
  align-items: center; flex-wrap: wrap; gap: 12px;
}
#header h1 { font-size: 1.1rem; font-weight: 700; }
.header-sub { font-size: 0.8rem; opacity: 0.8; margin-top: 2px; display: block; }
#header-badges { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.badge {
  background: rgba(255,255,255,.12); border-radius: 5px;
  padding: 3px 10px; font-size: 0.75rem; white-space: nowrap;
}
.badge-status { text-transform: capitalize; }
.badge-status.completed { background: #16a34a33; }
.badge-status.partial, .badge-status.running { background: #d9770633; }

.partial-notice {
  background: #fef3c7; color: #92400e; padding: 8px 24px;
  font-size: 0.82rem; font-weight: 500; border-bottom: 1px solid #fde68a;
}

/* ---- Control Panel ---- */
#control-panel {
  position: sticky; top: 0; z-index: 100;
  background: var(--cp-bg); border-bottom: 1px solid var(--border);
  padding: 10px 24px; display: flex; flex-wrap: wrap; gap: 20px;
  align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,.06);
}
.cp-group { display: flex; align-items: center; gap: 8px; }
.cp-group label { font-size: 0.78rem; font-weight: 600; color: var(--text-muted); white-space: nowrap; }

.btn-group { display: flex; border-radius: 6px; overflow: hidden; border: 1px solid var(--border); }
.btn-toggle {
  background: #fff; border: none; padding: 4px 10px; font-size: 0.75rem;
  cursor: pointer; transition: background 0.15s;
  border-right: 1px solid var(--border); color: var(--text);
}
.btn-toggle:last-child { border-right: none; }
.btn-toggle:hover { background: #f0f4f8; }
.btn-toggle.active { background: var(--accent); color: #fff; }

input[type="range"] { width: 120px; accent-color: var(--accent); cursor: pointer; }

/* ---- Main content ---- */
#main { padding: 20px 24px; max-width: 1400px; margin: 0 auto; }

.card {
  background: var(--card-bg); border-radius: 10px; box-shadow: var(--shadow);
  margin-bottom: 20px; overflow: hidden;
  border: 1px solid var(--border);
}
.card-header { padding: 14px 20px; border-bottom: 1px solid var(--border); }
.card-header h2 { font-size: 1rem; font-weight: 700; color: var(--header-bg); }
.card-desc { font-size: 0.78rem; color: var(--text-muted); margin-top: 4px; }
.card-body { padding: 16px 20px; }
/* ---- Collapsible figure explanations ---- */
details.fig-explain { margin-top: 14px; border-top: 1px dashed var(--border); padding-top: 8px; }
details.fig-explain summary {
  font-size: 0.75rem; color: var(--text-muted); cursor: pointer; user-select: none;
  display: inline-flex; align-items: center; gap: 5px; outline: none; list-style: none;
}
details.fig-explain summary::-webkit-details-marker { display: none; }
details.fig-explain summary::before { content: "ℹ"; color: #94a3b8; }
details.fig-explain[open] summary { color: var(--accent); }
details.fig-explain[open] summary::before { color: var(--accent); }
details.fig-explain .explain-body {
  font-size: 0.78rem; color: #475569; line-height: 1.65; margin-top: 8px;
  padding: 10px 14px; background: #f8fafc; border-radius: 6px;
  border-left: 3px solid #94a3b8;
}
details.fig-explain .explain-body b { color: #1e293b; }
details.fig-explain .explain-body code {
  background: #e2e8f0; padding: 1px 4px; border-radius: 3px; font-size: 0.85em;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr minmax(260px, 380px);
  gap: 20px;
  align-items: start;
}
@media (max-width: 800px) {
  .two-col { grid-template-columns: 1fr; }
}

.chart-side { max-width: 380px; }
.chart-side canvas { width: 100% !important; }

/* ---- Filter row ---- */
.filter-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.name-filter {
  border: 1px solid var(--border); border-radius: 5px; padding: 4px 10px;
  font-size: 0.78rem; width: 200px; outline: none;
}
.name-filter:focus { border-color: var(--accent); }
.coverage-info { font-size: 0.75rem; color: var(--text-muted); }

/* ---- Tables ---- */
table.tbl {
  border-collapse: collapse; width: 100%; font-size: 0.80rem;
}
table.tbl th {
  background: var(--th-bg); text-align: left;
  padding: 6px 10px; border-bottom: 2px solid var(--border);
  font-weight: 600; color: #444; white-space: nowrap;
  user-select: none; cursor: pointer;
}
table.tbl th:hover { background: #e4eaf2; }
table.tbl th.sort-asc::after { content: " ↑"; color: var(--accent); }
table.tbl th.sort-desc::after { content: " ↓"; color: var(--accent); }
table.tbl th.sort-active { color: var(--accent); }
table.tbl td {
  padding: 5px 10px; border-bottom: 1px solid #f0f0f0;
  vertical-align: middle;
}
table.tbl tr:hover td { background: var(--row-hover); }

/* Score bar in cells */
.score-cell { position: relative; min-width: 80px; }
.score-bar {
  display: inline-block; height: 10px; border-radius: 3px;
  vertical-align: middle; margin-right: 4px;
  transition: width 0.2s;
}

/* Badges */
.badge-eff {
  display: inline-block; padding: 1px 7px; border-radius: 4px;
  font-size: 0.7rem; font-weight: 600; white-space: nowrap;
}
.badge-eff.yes { background: var(--green-bg); color: var(--green); }
.badge-eff.no  { background: var(--gray-bg);  color: var(--gray); }

/* ---- View tabs ---- */
.view-tabs { display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 2px solid var(--border); padding-bottom: 6px; }
.tab-btn {
  background: none; border: 1px solid var(--border); border-radius: 5px 5px 0 0;
  padding: 5px 14px; font-size: 0.78rem; cursor: pointer; color: var(--text-muted);
  transition: background 0.15s;
}
.tab-btn:hover { background: #f0f4f8; color: var(--text); }
.tab-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

/* ---- Delta column ---- */
.delta-pos { color: var(--green); }
.delta-neg { color: #dc2626; }
.delta-zero { color: var(--gray); }

/* ---- Pivot table ---- */
table.tbl td.pivot-score {
  text-align: center;
}

/* ---- N/A ---- */
.na { color: #aaa; font-style: italic; font-size: 0.75rem; }

footer {
  text-align: center; padding: 20px; font-size: 0.72rem; color: #aaa;
  border-top: 1px solid var(--border); margin-top: 8px;
}

/* ---- Tooltips ---- */
[data-tip] { position: relative; }
[data-tip]::after {
  content: attr(data-tip);
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%; transform: translateX(-50%);
  background: #1e293b; color: #f1f5f9;
  padding: 7px 11px; border-radius: 7px;
  font-size: 0.71rem; font-weight: 400;
  white-space: normal; width: 280px;
  line-height: 1.5; z-index: 9999;
  pointer-events: none; opacity: 0;
  transition: opacity 0.18s;
  box-shadow: 0 6px 18px rgba(0,0,0,.28);
  text-align: left;
}
[data-tip]::before {
  content: '';
  position: absolute;
  bottom: calc(100% + 3px);
  left: 50%; transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: #1e293b;
  z-index: 9999; opacity: 0;
  transition: opacity 0.18s;
  pointer-events: none;
}
[data-tip]:hover::after,
[data-tip]:hover::before { opacity: 1; }

/* Prevent right-edge overflow for last columns */
table.tbl th:last-child[data-tip]::after,
table.tbl th:nth-last-child(2)[data-tip]::after {
  left: auto; right: 0; transform: none;
}
table.tbl th:last-child[data-tip]::before,
table.tbl th:nth-last-child(2)[data-tip]::before {
  left: auto; right: 20px; transform: none;
}

/* Tooltip on control-panel labels */
.cp-group label[data-tip] { cursor: help; border-bottom: 1px dashed var(--text-muted); }
"""

# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

_JS = r"""
// -----------------------------------------------------------------------
// Tooltip content for metrics and formulas
// -----------------------------------------------------------------------
var FORMULA_TIPS = {
  v1: "V1 Variance: score = Var(student scores) \u00d7 coverage. Rewards teachers whose questions produce high variance in student scores \u2014 a strong signal that the questions discriminate between strong and weak students.",
  s2: "S2 Spread: score = mean(|score \u2212 mean|) \u00d7 coverage. Mean absolute deviation of student scores around the teacher mean. Rewards questions that elicit a spread of response quality without being skewed by outliers.",
  r3: "R3 Range: score = (max \u2212 min) \u00d7 coverage. Range of student scores for this teacher. Simple and interpretable: a wide range means at least one student answered well and at least one answered poorly."
};

var METRIC_TIPS = {
  spa: "SPA (Strict Pair Agreement): fraction of (judgeA, judgeB) score-pairs on the same response that agree exactly on the same ordinal level (High / Medium / Low). The strictest agreement metric.",
  wpa: "WPA (Weighted Pair Agreement): like SPA but tolerates near-misses with partial credit (adjacent levels count as partial agreement). More lenient than SPA, less sensitive to small disagreements.",
  kappa: "Cohen \u03ba: inter-rater reliability corrected for chance. \u03ba = (p_observed \u2212 p_expected) / (1 \u2212 p_expected). Interpretation: <0.2 slight, 0.2\u20130.4 fair, 0.4\u20130.6 moderate, 0.6\u20130.8 substantial, >0.8 near-perfect."
};

var COL_TIPS = {
  teacher_score:    "Discriminativeness score for this teacher under the selected formula. Higher = questions that better separate strong from weak students.",
  teacher_dp:       "Number of reference datapoints generated by this teacher across all tasks.",
  teacher_tasks:    "Tasks for which this teacher generated reference datapoints.",
  teacher_eff:      "A teacher is Effective when their score \u2265 the current threshold. Only effective teachers contribute to student rankings.",
  judge_spa:        "Strict Pair Agreement: fraction of judge-pairs that give the exact same score level (High / Medium / Low) on the same response.",
  judge_wpa:        "Weighted Pair Agreement: like SPA but with partial credit for adjacent-level disagreements.",
  judge_kappa:      "Cohen \u03ba: agreement corrected for chance. Higher = more reliable and consistent scoring.",
  judge_evals:      "Number of phase-5 evaluation records produced by this judge that have valid (non-null) scores.",
  judge_cons:       "A judge is Consensus when their agreement score \u2265 the current threshold. Only consensus judges contribute to student rankings.",
  student_filtered: "Average normalised score (0\u20131) across datapoints from effective teachers, evaluated by consensus judges. Reflects the current formula / metric / threshold settings.",
  student_all:      "Average normalised score using all teachers and judges, before any filtering. Serves as the unfiltered baseline for comparison.",
  student_delta:    "Filtered score minus all-data score. Positive = student performs relatively better when evaluated by consensus judges on effective-teacher datapoints.",
  student_overall:  "Mean score across all tasks, using only effective teachers and consensus judges.",
  student_cons_avg: "Mean score across all consensus judges, using only effective teachers."
};

// -----------------------------------------------------------------------
// State
// -----------------------------------------------------------------------
var state = {
  teacherFormula: 's2',
  teacherThreshold: null,   // set from DATA.defaults on init
  judgeMetric: 'spa',
  judgeThreshold: null,
  studentView: 'overall',
  sortState: {},            // key: tableId, value: {col, dir}
};

var teacherChartInst = null;
var judgeChartInst = null;

// -----------------------------------------------------------------------
// Initialisation
// -----------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function() {
  var m = DATA.meta;
  document.getElementById('hdr-tasks').textContent = m.n_tasks;
  document.getElementById('hdr-models').textContent =
    (new Set(
      DATA.teachers.map(function(r){return r.teacher;}).concat(
      DATA.students.map(function(r){return r.student;})).concat(
      DATA.judges.map(function(r){return r.judge;}))
    )).size;
  document.getElementById('hdr-evals').textContent = m.valid_evals;
  document.getElementById('hdr-date').textContent = m.analysis_date;
  document.getElementById('ftr-date').textContent = m.analysis_date;

  var sbEl = document.getElementById('status-badge');
  sbEl.classList.add(m.status === 'completed' ? 'completed' : 'partial');

  // Set initial thresholds from DATA.defaults
  var defs = DATA.defaults;
  state.teacherThreshold = defs.teacher_thresholds[state.teacherFormula] || 0;
  state.judgeThreshold   = defs.judge_thresholds[state.judgeMetric]    || 0.5;

  // Sync sliders
  _syncTeacherSlider();
  _syncJudgeSlider();

  // Activate initial button states
  _activateBtn('teacher-formula-btns', state.teacherFormula);
  _activateBtn('judge-metric-btns', state.judgeMetric);

  renderAll();
});

// -----------------------------------------------------------------------
// Control handlers
// -----------------------------------------------------------------------
function setTeacherFormula(f) {
  state.teacherFormula = f;
  state.teacherThreshold = DATA.defaults.teacher_thresholds[f] || 0;
  _activateBtn('teacher-formula-btns', f);
  _syncTeacherSlider();
  renderAll();
}

function setJudgeMetric(m) {
  state.judgeMetric = m;
  state.judgeThreshold = DATA.defaults.judge_thresholds[m] || 0.5;
  _activateBtn('judge-metric-btns', m);
  _syncJudgeSlider();
  renderAll();
}

function setKappaMetric(m) { setJudgeMetric(m); }

function onTeacherThreshold(v) {
  state.teacherThreshold = parseFloat(v);
  document.getElementById('t-thr-label').textContent = parseFloat(v).toFixed(4);
  renderAll();
}

function onJudgeThreshold(v) {
  state.judgeThreshold = parseFloat(v);
  document.getElementById('j-thr-label').textContent = parseFloat(v).toFixed(3);
  renderAll();
}

function setStudentView(v) {
  state.studentView = v;
  var tabs = document.querySelectorAll('#student-view-tabs .tab-btn');
  var views = ['overall', 'by-task', 'by-judge', 'side-by-side'];
  tabs.forEach(function(btn, i) {
    btn.classList.toggle('active', views[i] === v);
  });
  renderStudentSection();
}

function _activateBtn(groupId, value) {
  var btns = document.querySelectorAll('#' + groupId + ' .btn-toggle');
  btns.forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.value === value);
  });
}

function _syncTeacherSlider() {
  var sl = document.getElementById('teacher-threshold');
  var rows = DATA.teachers;
  var maxVal = rows.reduce(function(mx, r){ return Math.max(mx, r[state.teacherFormula]||0); }, 0);
  sl.max = maxVal > 0 ? (maxVal * 1.05).toFixed(4) : '1';
  sl.value = state.teacherThreshold;
  document.getElementById('t-thr-label').textContent =
    parseFloat(state.teacherThreshold).toFixed(4);
}

function _syncJudgeSlider() {
  var sl = document.getElementById('judge-threshold');
  sl.max = '1';
  sl.value = state.judgeThreshold;
  document.getElementById('j-thr-label').textContent =
    parseFloat(state.judgeThreshold).toFixed(3);
}

// -----------------------------------------------------------------------
// Derived helpers
// -----------------------------------------------------------------------
function getEffectiveTeachers() {
  var f = state.teacherFormula;
  var thr = state.teacherThreshold;
  return DATA.teachers
    .filter(function(r){ return (r[f] || 0) >= thr; })
    .map(function(r){ return r.teacher; });
}

function getConsensusJudges() {
  var m = state.judgeMetric;
  var thr = state.judgeThreshold;
  return DATA.judges
    .filter(function(r){ return r[m] !== null && r[m] >= thr; })
    .map(function(r){ return r.judge; });
}

function getFilteredStudentScores(groupByTask, groupByJudge) {
  var effTeachers = new Set(getEffectiveTeachers());
  var consJudges  = new Set(getConsensusJudges());

  // Filter units by effective teacher + consensus judge
  var filtered = DATA.units.filter(function(u) {
    return effTeachers.has(u.teacher) && consJudges.has(u.judge);
  });

  if (groupByTask) {
    // Returns {student -> {task -> [scores]}}
    var agg = {};
    filtered.forEach(function(u) {
      if (!agg[u.student]) agg[u.student] = {};
      if (!agg[u.student][u.task]) agg[u.student][u.task] = [];
      agg[u.student][u.task].push(u.score);
    });
    var result = {};
    Object.keys(agg).forEach(function(s) {
      result[s] = {};
      Object.keys(agg[s]).forEach(function(t) {
        var arr = agg[s][t];
        result[s][t] = arr.reduce(function(a,b){return a+b;},0)/arr.length;
      });
    });
    return result;
  }

  if (groupByJudge) {
    // Returns {student -> {judge -> avg_score}}
    var agg2 = {};
    filtered.forEach(function(u) {
      if (!agg2[u.student]) agg2[u.student] = {};
      if (!agg2[u.student][u.judge]) agg2[u.student][u.judge] = [];
      agg2[u.student][u.judge].push(u.score);
    });
    var result2 = {};
    Object.keys(agg2).forEach(function(s) {
      result2[s] = {};
      Object.keys(agg2[s]).forEach(function(j) {
        var arr = agg2[s][j];
        result2[s][j] = arr.reduce(function(a,b){return a+b;},0)/arr.length;
      });
    });
    return result2;
  }

  // Returns {student -> avg_score}
  var agg3 = {};
  filtered.forEach(function(u) {
    if (!agg3[u.student]) agg3[u.student] = [];
    agg3[u.student].push(u.score);
  });
  var result3 = {};
  Object.keys(agg3).forEach(function(s) {
    var arr = agg3[s];
    result3[s] = arr.reduce(function(a,b){return a+b;},0)/arr.length;
  });
  return result3;
}

// -----------------------------------------------------------------------
// Render all
// -----------------------------------------------------------------------
function renderAll() {
  renderTeacherTable();
  renderTeacherChart();
  renderJudgeTable();
  renderJudgeChart();
  renderStudentSection();
}

// -----------------------------------------------------------------------
// Teacher table
// -----------------------------------------------------------------------
function renderTeacherTable() {
  var f = state.teacherFormula;
  var thr = state.teacherThreshold;
  var nameFilter = document.getElementById('filter-teachers').value.toLowerCase();

  var rows = DATA.teachers.slice();
  if (nameFilter) rows = rows.filter(function(r){ return r.teacher.toLowerCase().includes(nameFilter); });

  // Sort
  var ss = _getSortState('teacher-tbl');
  rows = _sortRows(rows, ss);

  var maxScore = rows.reduce(function(mx, r){ return Math.max(mx, r[f]||0); }, 0) || 1;

  var html = '<table class="tbl" id="teacher-tbl">';
  html += '<thead><tr>';
  html += _th('teacher-tbl', 'teacher', 'Teacher');
  html += _th('teacher-tbl', f, 'Score (' + f.toUpperCase() + ')', FORMULA_TIPS[f]);
  html += _th('teacher-tbl', 'datapoints', 'Datapoints', COL_TIPS.teacher_dp);
  html += '<th data-tip="' + COL_TIPS.teacher_tasks + '">Tasks</th>';
  html += '<th data-tip="' + COL_TIPS.teacher_eff + '">Effective</th>';
  html += '</tr></thead><tbody>';

  rows.forEach(function(r) {
    var score = r[f] || 0;
    var isEff = score >= thr;
    var barW = maxScore > 0 ? Math.round(score / maxScore * 100) : 0;
    var barColor = isEff ? 'var(--bar-effective)' : 'var(--bar-color)';
    html += '<tr>';
    html += '<td>' + _esc(r.teacher) + '</td>';
    html += '<td class="score-cell">'
          + '<span class="score-bar" style="width:' + barW + 'px;background:' + barColor + '"></span>'
          + score.toFixed(4)
          + '</td>';
    html += '<td>' + r.datapoints + '</td>';
    html += '<td>' + (r.tasks || []).map(_esc).join(', ') + '</td>';
    html += '<td><span class="badge-eff ' + (isEff ? 'yes' : 'no') + '">'
          + (isEff ? 'Effective' : 'Inactive') + '</span></td>';
    html += '</tr>';
  });

  html += '</tbody></table>';
  document.getElementById('teacher-table-wrap').innerHTML = html;
  _attachSortHandlers('teacher-tbl', renderTeacherTable);
}

// -----------------------------------------------------------------------
// Teacher chart
// -----------------------------------------------------------------------
function renderTeacherChart() {
  var f = state.teacherFormula;
  var thr = state.teacherThreshold;
  var rows = DATA.teachers.slice().sort(function(a,b){ return (b[f]||0)-(a[f]||0); });
  var labels = rows.map(function(r){ return _shortName(r.teacher); });
  var vals   = rows.map(function(r){ return r[f]||0; });
  var colors = rows.map(function(r){ return (r[f]||0) >= thr ? '#4ade80' : '#93c5fd'; });

  var canvas = document.getElementById('teacher-chart');
  if (teacherChartInst) { teacherChartInst.destroy(); }
  teacherChartInst = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Score (' + f.toUpperCase() + ')',
        data: vals,
        backgroundColor: colors,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return rows[ctx.dataIndex].teacher + ': ' + ctx.raw.toFixed(4);
            }
          }
        }
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'Score (' + f.toUpperCase() + ')' } },
        x: { ticks: { font: { size: 10 } } }
      }
    }
  });
}

// -----------------------------------------------------------------------
// Judge table
// -----------------------------------------------------------------------
function renderJudgeTable() {
  var m  = state.judgeMetric;
  var thr = state.judgeThreshold;
  var nameFilter = document.getElementById('filter-judges').value.toLowerCase();

  var rows = DATA.judges.slice();
  if (nameFilter) rows = rows.filter(function(r){ return r.judge.toLowerCase().includes(nameFilter); });

  var ss = _getSortState('judge-tbl');
  rows = _sortRows(rows, ss);

  var maxScore = rows.reduce(function(mx, r){ return Math.max(mx, r[m] !== null ? r[m] : 0); }, 0) || 1;

  var html = '<table class="tbl" id="judge-tbl">';
  html += '<thead><tr>';
  html += _th('judge-tbl', 'judge', 'Judge');
  html += _th('judge-tbl', 'spa',   'SPA',   COL_TIPS.judge_spa);
  html += _th('judge-tbl', 'wpa',   'WPA',   COL_TIPS.judge_wpa);
  html += _th('judge-tbl', 'kappa', 'Kappa', COL_TIPS.judge_kappa);
  html += _th('judge-tbl', 'valid_evals', 'Valid Evals', COL_TIPS.judge_evals);
  html += '<th data-tip="' + COL_TIPS.judge_cons + '">Consensus</th>';
  html += '</tr></thead><tbody>';

  rows.forEach(function(r) {
    var score = r[m] !== null ? r[m] : null;
    var isCons = score !== null && score >= thr;
    var barW = (score !== null && maxScore > 0) ? Math.round(score / maxScore * 100) : 0;
    var barColor = isCons ? 'var(--bar-effective)' : 'var(--bar-color)';
    html += '<tr>';
    html += '<td>' + _esc(r.judge) + '</td>';
    html += '<td class="score-cell">'
          + '<span class="score-bar" style="width:' + barW + 'px;background:' + barColor + '"></span>'
          + _fmtScore(r.spa) + '</td>';
    html += '<td>' + _fmtScore(r.wpa) + '</td>';
    html += '<td>' + _fmtScore(r.kappa) + '</td>';
    html += '<td>' + r.valid_evals + '</td>';
    html += '<td><span class="badge-eff ' + (isCons ? 'yes' : 'no') + '">'
          + (isCons ? 'Consensus' : 'Excluded') + '</span></td>';
    html += '</tr>';
  });

  html += '</tbody></table>';
  document.getElementById('judge-table-wrap').innerHTML = html;
  _attachSortHandlers('judge-tbl', renderJudgeTable);
}

// -----------------------------------------------------------------------
// Judge chart
// -----------------------------------------------------------------------
function renderJudgeChart() {
  var m = state.judgeMetric;
  var thr = state.judgeThreshold;
  var rows = DATA.judges.slice().sort(function(a,b){ return (b[m]||0)-(a[m]||0); });
  var labels = rows.map(function(r){ return _shortName(r.judge); });
  var vals   = rows.map(function(r){ return r[m] !== null ? r[m] : 0; });
  var colors = rows.map(function(r){ return (r[m] !== null && r[m] >= thr) ? '#4ade80' : '#93c5fd'; });

  var canvas = document.getElementById('judge-chart');
  if (judgeChartInst) { judgeChartInst.destroy(); }
  judgeChartInst = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: m.toUpperCase(),
        data: vals,
        backgroundColor: colors,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return rows[ctx.dataIndex].judge + ': ' + ctx.raw.toFixed(4);
            }
          }
        }
      },
      scales: {
        y: { min: 0, max: 1, title: { display: true, text: m.toUpperCase() } },
        x: { ticks: { font: { size: 10 } } }
      }
    }
  });
}

// -----------------------------------------------------------------------
// Student section dispatcher
// -----------------------------------------------------------------------
function renderStudentSection() {
  var nEff  = getEffectiveTeachers().length;
  var nCons = getConsensusJudges().length;
  var infoEl = document.getElementById('student-coverage-info');
  infoEl.textContent = 'Using ' + nEff + ' effective teacher(s) and ' + nCons + ' consensus judge(s).';

  var v = state.studentView;
  if (v === 'overall')      renderStudentOverall();
  else if (v === 'by-task') renderStudentByTask();
  else if (v === 'by-judge')renderStudentByJudge();
  else                      renderStudentSideBySide();
}

// -----------------------------------------------------------------------
// Student — Overall view
// -----------------------------------------------------------------------
function renderStudentOverall() {
  var nameFilter = document.getElementById('filter-students').value.toLowerCase();
  var filtScores   = getFilteredStudentScores(false, false);  // {student -> avg}

  // Build unfiltered scores from DATA.students (original baseline)
  var unfiltScores = {};
  DATA.students.forEach(function(r) { unfiltScores[r.student] = r.overall; });

  // Build row array
  var students = DATA.students.map(function(r){ return r.student; });
  if (nameFilter) students = students.filter(function(s){ return s.toLowerCase().includes(nameFilter); });

  var rows = students.map(function(s) {
    var filtered = filtScores[s] !== undefined ? filtScores[s] : null;
    var unfiltered = unfiltScores[s] !== undefined ? unfiltScores[s] : null;
    var delta = (filtered !== null && unfiltered !== null) ? filtered - unfiltered : null;
    return { student: s, filtered: filtered, unfiltered: unfiltered, delta: delta };
  });

  var ss = _getSortState('student-overall-tbl');
  rows = _sortRows(rows, ss);

  var html = '<table class="tbl" id="student-overall-tbl">';
  html += '<thead><tr>';
  html += _th('student-overall-tbl', 'student',    'Student');
  html += _th('student-overall-tbl', 'filtered',   'Score (filtered)',   COL_TIPS.student_filtered);
  html += _th('student-overall-tbl', 'unfiltered', 'Score (all data)',   COL_TIPS.student_all);
  html += _th('student-overall-tbl', 'delta',      'Delta',              COL_TIPS.student_delta);
  html += '</tr></thead><tbody>';

  rows.forEach(function(r) {
    var cls = r.delta === null ? 'delta-zero'
            : r.delta > 0.001 ? 'delta-pos'
            : r.delta < -0.001 ? 'delta-neg' : 'delta-zero';
    html += '<tr>';
    html += '<td>' + _esc(r.student) + '</td>';
    html += '<td>' + _fmtScoreBar(r.filtered, 1.0) + '</td>';
    html += '<td>' + _fmtScore(r.unfiltered) + '</td>';
    html += '<td class="' + cls + '">' + (r.delta !== null ? (r.delta >= 0 ? '+' : '') + r.delta.toFixed(4) : '<span class="na">—</span>') + '</td>';
    html += '</tr>';
  });

  html += '</tbody></table>';
  document.getElementById('student-section-body').innerHTML = html;
  _attachSortHandlers('student-overall-tbl', renderStudentSection);
}

// -----------------------------------------------------------------------
// Student — By Task view
// -----------------------------------------------------------------------
function renderStudentByTask() {
  var nameFilter = document.getElementById('filter-students').value.toLowerCase();
  var byTask = getFilteredStudentScores(true, false);  // {student -> {task -> avg}}
  var tasks = DATA.tasks;

  var students = DATA.students.map(function(r){ return r.student; });
  if (nameFilter) students = students.filter(function(s){ return s.toLowerCase().includes(nameFilter); });

  // Sort by first task score descending (or by 'student' key)
  var ss = _getSortState('student-task-tbl');
  var rows = students.map(function(s) {
    var row = { student: s };
    tasks.forEach(function(t) {
      var v = (byTask[s] && byTask[s][t] !== undefined) ? byTask[s][t] : null;
      row[t] = v;
    });
    // compute overall for sort
    var vals = tasks.map(function(t){ return row[t]; }).filter(function(v){ return v !== null; });
    row._overall = vals.length ? vals.reduce(function(a,b){return a+b;},0)/vals.length : null;
    return row;
  });
  rows = _sortRows(rows, ss);

  var html = '<table class="tbl" id="student-task-tbl">';
  html += '<thead><tr>';
  html += _th('student-task-tbl', 'student', 'Student');
  tasks.forEach(function(t) {
    html += _th('student-task-tbl', t, _shortName(t, 16));
  });
  html += _th('student-task-tbl', '_overall', 'Overall', COL_TIPS.student_overall);
  html += '</tr></thead><tbody>';

  rows.forEach(function(r) {
    html += '<tr><td>' + _esc(r.student) + '</td>';
    tasks.forEach(function(t) {
      html += '<td class="pivot-score">' + _fmtScore(r[t]) + '</td>';
    });
    html += '<td class="pivot-score"><b>' + _fmtScore(r._overall) + '</b></td>';
    html += '</tr>';
  });

  html += '</tbody></table>';
  document.getElementById('student-section-body').innerHTML = html;
  _attachSortHandlers('student-task-tbl', renderStudentSection);
}

// -----------------------------------------------------------------------
// Student — By Judge view
// -----------------------------------------------------------------------
function renderStudentByJudge() {
  var nameFilter = document.getElementById('filter-students').value.toLowerCase();
  var byJudge = getFilteredStudentScores(false, true);  // {student -> {judge -> avg}}
  var judges = DATA.judges.map(function(r){ return r.judge; });
  var consJudges = new Set(getConsensusJudges());

  var students = DATA.students.map(function(r){ return r.student; });
  if (nameFilter) students = students.filter(function(s){ return s.toLowerCase().includes(nameFilter); });

  var ss = _getSortState('student-judge-tbl');
  var rows = students.map(function(s) {
    var row = { student: s };
    judges.forEach(function(j) {
      var v = (byJudge[s] && byJudge[s][j] !== undefined) ? byJudge[s][j] : null;
      row[j] = v;
    });
    // overall
    var activeJudges = judges.filter(function(j){ return consJudges.has(j); });
    var vals = activeJudges.map(function(j){ return row[j]; }).filter(function(v){ return v !== null; });
    row._overall = vals.length ? vals.reduce(function(a,b){return a+b;},0)/vals.length : null;
    return row;
  });
  rows = _sortRows(rows, ss);

  var html = '<table class="tbl" id="student-judge-tbl">';
  html += '<thead><tr>';
  html += _th('student-judge-tbl', 'student', 'Student');
  judges.forEach(function(j) {
    var mark = consJudges.has(j) ? '' : ' <span class="na">[excl]</span>';
    html += _th('student-judge-tbl', j, _shortName(j, 16) + mark);
  });
  html += _th('student-judge-tbl', '_overall', 'Consensus Avg', COL_TIPS.student_cons_avg);
  html += '</tr></thead><tbody>';

  rows.forEach(function(r) {
    html += '<tr><td>' + _esc(r.student) + '</td>';
    judges.forEach(function(j) {
      var cls = consJudges.has(j) ? '' : ' style="opacity:0.45"';
      html += '<td class="pivot-score"' + cls + '>' + _fmtScore(r[j]) + '</td>';
    });
    html += '<td class="pivot-score"><b>' + _fmtScore(r._overall) + '</b></td>';
    html += '</tr>';
  });

  html += '</tbody></table>';
  document.getElementById('student-section-body').innerHTML = html;
  _attachSortHandlers('student-judge-tbl', renderStudentSection);
}

// -----------------------------------------------------------------------
// Student — Side-by-Side view (compare formulas/metrics)
// -----------------------------------------------------------------------
function renderStudentSideBySide() {
  var nameFilter = document.getElementById('filter-students').value.toLowerCase();
  var formulas = ['v1', 's2', 'r3'];
  var metrics  = ['spa', 'wpa', 'kappa'];

  // Compute scores for every formula/metric combination
  var rankData = {};  // key: "f_m", value: {student -> score}
  formulas.forEach(function(f) {
    metrics.forEach(function(m) {
      // temporarily override state
      var savedF = state.teacherFormula;
      var savedM = state.judgeMetric;
      var savedThr = state.teacherThreshold;
      var savedJThr = state.judgeThreshold;
      state.teacherFormula = f;
      state.judgeMetric = m;
      state.teacherThreshold = DATA.defaults.teacher_thresholds[f] || 0;
      state.judgeThreshold   = DATA.defaults.judge_thresholds[m]   || 0.5;
      rankData[f + '_' + m] = getFilteredStudentScores(false, false);
      state.teacherFormula = savedF;
      state.judgeMetric = savedM;
      state.teacherThreshold = savedThr;
      state.judgeThreshold = savedJThr;
    });
  });

  var students = DATA.students.map(function(r){ return r.student; });
  if (nameFilter) students = students.filter(function(s){ return s.toLowerCase().includes(nameFilter); });

  // Build header: current combination first, then others
  var currentKey = state.teacherFormula + '_' + state.judgeMetric;

  var html = '<div style="overflow-x:auto"><table class="tbl" id="student-sbs-tbl">';
  html += '<thead><tr><th>Student</th>';
  formulas.forEach(function(f) {
    metrics.forEach(function(m) {
      var key = f + '_' + m;
      var label = f.toUpperCase() + '+' + m.toUpperCase();
      var style = (key === currentKey) ? ' style="color:var(--accent);font-weight:700"' : '';
      var tip = (FORMULA_TIPS[f] || '') + ' | ' + (METRIC_TIPS[m] || '');
      var tipAttr = ' data-tip="' + tip.replace(/"/g, '&quot;') + '"';
      html += '<th' + style + tipAttr + '>' + label + '</th>';
    });
  });
  html += '</tr></thead><tbody>';

  // Sort by current key descending
  var rows = students.map(function(s) {
    var row = { student: s, _current: rankData[currentKey][s] || null };
    formulas.forEach(function(f) {
      metrics.forEach(function(m) {
        row[f + '_' + m] = rankData[f + '_' + m][s] !== undefined ? rankData[f + '_' + m][s] : null;
      });
    });
    return row;
  });
  rows.sort(function(a, b) { return (b._current || 0) - (a._current || 0); });

  rows.forEach(function(r) {
    html += '<tr><td>' + _esc(r.student) + '</td>';
    formulas.forEach(function(f) {
      metrics.forEach(function(m) {
        var key = f + '_' + m;
        var v = r[key];
        var style = (key === currentKey) ? ' style="font-weight:600"' : '';
        html += '<td class="pivot-score"' + style + '>' + _fmtScore(v) + '</td>';
      });
    });
    html += '</tr>';
  });

  html += '</tbody></table></div>';
  document.getElementById('student-section-body').innerHTML = html;
}

// -----------------------------------------------------------------------
// Sortable table helpers
// -----------------------------------------------------------------------
function _getSortState(tblId) {
  return state.sortState[tblId] || { col: null, dir: 'desc' };
}

function _sortRows(rows, ss) {
  if (!ss.col) return rows;
  var col = ss.col;
  var dir = ss.dir === 'asc' ? 1 : -1;
  return rows.slice().sort(function(a, b) {
    var av = a[col], bv = b[col];
    // Null-last
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (typeof av === 'string') return dir * av.localeCompare(bv);
    return dir * (av - bv);
  });
}

function _th(tblId, col, label, tip) {
  var ss = _getSortState(tblId);
  var sortCls = '';
  if (ss.col === col) sortCls = ' sort-active ' + (ss.dir === 'asc' ? 'sort-asc' : 'sort-desc');
  var tipAttr = tip ? ' data-tip="' + String(tip).replace(/"/g, '&quot;') + '"' : '';
  return '<th class="' + sortCls + '" data-tbl="' + tblId + '" data-col="' + col + '"' + tipAttr + '>'
       + label + '</th>';
}

function _attachSortHandlers(tblId, renderFn) {
  var el = document.getElementById(tblId);
  if (!el) return;
  el.querySelectorAll('th[data-col]').forEach(function(th) {
    th.addEventListener('click', function() {
      var col = this.dataset.col;
      var ss = _getSortState(tblId);
      if (ss.col === col) {
        state.sortState[tblId] = { col: col, dir: ss.dir === 'asc' ? 'desc' : 'asc' };
      } else {
        state.sortState[tblId] = { col: col, dir: 'desc' };
      }
      renderFn();
    });
  });
}

// -----------------------------------------------------------------------
// Formatting helpers
// -----------------------------------------------------------------------
function _fmtScore(v) {
  if (v === null || v === undefined) return '<span class="na">—</span>';
  return parseFloat(v).toFixed(4);
}

function _fmtScoreBar(v, max) {
  if (v === null || v === undefined) return '<span class="na">—</span>';
  var pct = max > 0 ? Math.round(v / max * 100) : 0;
  return '<span class="score-bar" style="width:' + pct + 'px;background:var(--bar-effective)"></span>'
       + parseFloat(v).toFixed(4);
}

function _shortName(s, maxLen) {
  maxLen = maxLen || 20;
  return s.length > maxLen ? s.slice(0, maxLen - 1) + '…' : s;
}

function _esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
"""
