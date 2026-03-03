"""analysis/calibration.py — Judge score calibration via OLS linear fit.

Fits a per-judge, per-task linear calibration:

    adjusted_score = alpha + beta * raw_score

where ``raw_score`` is the CoEval ensemble score_norm [0, 1] and
``adjusted_score`` is aligned to benchmark-native ground-truth [0, 1].

The fit is performed on a holdout set (default 200 items sampled with seed=0)
and the calibration parameters are stored in a JSON file in the experiment
folder.  The calibrated scores can then be used to recompute Spearman ρ and
MAE against the benchmark ground truth (as reported in Table 8 of the paper).

.. warning:: **3-level ordinal limitation — calibration is NOT recommended
   by default.**

   LLM judges currently return only three ordinal score levels:
   High (1.0), Medium (0.5), and Low (0.0).  The OLS regression therefore
   operates on at most **3 unique input values**, which is fundamentally
   insufficient for a reliable linear fit.  The resulting α and β
   coefficients are highly sensitive to score distribution and may not
   generalise.

   Calibration is **disabled by default** in ``paper_tables.py`` (Table 8).
   It should only be enabled when:

   - The experiment uses **metric judges** (``interface: metric``) that
     produce continuous [0, 1] scores (e.g. BERTScore, BLEU), giving the
     OLS fit a meaningful range of input values.
   - You explicitly pass ``--enable-calibration`` to the paper tables CLI
     or set ``calibration_enabled=True`` programmatically.

Usage
-----
    from analyzer.calibration import fit_calibration, apply_calibration, \\
        load_or_fit_calibration

    params = fit_calibration(raw_scores, gt_scores)
    # params = {"alpha": float, "beta": float, "n_holdout": int, "rho_raw": float,
    #           "rho_calibrated": float, "mae_raw": float, "mae_calibrated": float}

    calibrated = apply_calibration(raw_scores, params["alpha"], params["beta"])

    # All-in-one: fit on 200-item holdout from EESDataModel, save to disk:
    params = load_or_fit_calibration(model, out_dir, holdout_n=200)
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

# Optional scipy dependency
try:
    from scipy.stats import spearmanr as _spearmanr

    def _rho(x: list[float], y: list[float]) -> float:
        if len(x) < 3:
            return float("nan")
        r, _ = _spearmanr(x, y)
        return float(r)

except ImportError:
    def _rho(x: list[float], y: list[float]) -> float:  # type: ignore[misc]
        return float("nan")


# ---------------------------------------------------------------------------
# Core OLS helpers
# ---------------------------------------------------------------------------

def _ols_linear(x: list[float], y: list[float]) -> tuple[float, float]:
    """Ordinary least-squares fit: y ≈ alpha + beta * x.

    Returns (alpha, beta).  Raises ValueError if n < 2 or variance is zero.
    """
    n = len(x)
    if n < 2:
        raise ValueError(f"OLS requires at least 2 samples; got {n}")
    mx = sum(x) / n
    my = sum(y) / n
    ss_xx = sum((xi - mx) ** 2 for xi in x)
    ss_xy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    if ss_xx == 0.0:
        raise ValueError("OLS: zero variance in raw scores — cannot fit calibration")
    beta = ss_xy / ss_xx
    alpha = my - beta * mx
    return alpha, beta


def _mae(x: list[float], y: list[float]) -> float:
    if not x:
        return float("nan")
    return sum(abs(a - b) for a, b in zip(x, y)) / len(x)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fit_calibration(
    raw_scores: list[float],
    gt_scores: list[float],
    holdout_n: int | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Fit OLS calibration on (optionally sub-sampled) data.

    Parameters
    ----------
    raw_scores  : CoEval ensemble score_norm values [0, 1]
    gt_scores   : Benchmark-native ground-truth values [0, 1]
    holdout_n   : If given, subsample this many pairs for fitting (seed used).
                  The full set is used for evaluation metrics.
    seed        : Random seed for subsampling

    Returns
    -------
    dict with keys:
        alpha, beta          : OLS calibration parameters
        n_fit                : number of samples used for fitting
        n_total              : total pairs provided
        rho_raw              : Spearman ρ before calibration (full set)
        rho_calibrated       : Spearman ρ after calibration (full set)
        mae_raw              : Mean absolute error before calibration
        mae_calibrated       : Mean absolute error after calibration
    """
    if len(raw_scores) != len(gt_scores):
        raise ValueError("raw_scores and gt_scores must have the same length")
    if len(raw_scores) < 2:
        raise ValueError("Need at least 2 samples to fit calibration")

    pairs = list(zip(raw_scores, gt_scores))
    n_total = len(pairs)

    # Select holdout subset for fitting
    if holdout_n and holdout_n < n_total:
        rng = random.Random(seed)
        fit_pairs = rng.sample(pairs, holdout_n)
    else:
        fit_pairs = pairs

    fit_x = [p[0] for p in fit_pairs]
    fit_y = [p[1] for p in fit_pairs]

    try:
        alpha, beta = _ols_linear(fit_x, fit_y)
    except ValueError:
        # Fallback: identity (no calibration)
        alpha, beta = 0.0, 1.0

    # Evaluate on full set
    raw_x = [p[0] for p in pairs]
    raw_y = [p[1] for p in pairs]
    cal_x = [max(0.0, min(1.0, alpha + beta * v)) for v in raw_x]

    rho_raw = _rho(raw_x, raw_y)
    rho_cal = _rho(cal_x, raw_y)
    mae_raw = _mae(raw_x, raw_y)
    mae_cal = _mae(cal_x, raw_y)

    return {
        "alpha": round(alpha, 6),
        "beta": round(beta, 6),
        "n_fit": len(fit_pairs),
        "n_total": n_total,
        "rho_raw": round(rho_raw, 4) if not math.isnan(rho_raw) else None,
        "rho_calibrated": round(rho_cal, 4) if not math.isnan(rho_cal) else None,
        "mae_raw": round(mae_raw, 4) if not math.isnan(mae_raw) else None,
        "mae_calibrated": round(mae_cal, 4) if not math.isnan(mae_cal) else None,
    }


def apply_calibration(
    raw_scores: list[float],
    alpha: float,
    beta: float,
    clip: bool = True,
) -> list[float]:
    """Apply linear calibration and optionally clip to [0, 1].

    adjusted = alpha + beta * raw_score
    """
    result = [alpha + beta * v for v in raw_scores]
    if clip:
        result = [max(0.0, min(1.0, v)) for v in result]
    return result


# ---------------------------------------------------------------------------
# EESDataModel integration
# ---------------------------------------------------------------------------

def load_or_fit_calibration(
    model: "EESDataModel",  # type: ignore[name-defined]  # noqa: F821
    out_dir: Path,
    holdout_n: int = 200,
    force: bool = False,
) -> dict[str, Any]:
    """Load calibration parameters from disk, or fit them from EES data.

    Calibration is performed per-judge and per-task, then stored in
    ``<out_dir>/calibration_params.json``.

    Parameters
    ----------
    model       : Loaded EESDataModel (from analyzer.loader)
    out_dir     : Directory to save / load calibration_params.json
    holdout_n   : Number of items to use for fitting per (judge, task) pair
    force       : Re-fit even if calibration_params.json already exists

    Returns
    -------
    dict: {
        "<judge_id>": {
            "<task_id>": {alpha, beta, rho_raw, rho_calibrated, mae_raw, mae_calibrated, ...}
        },
        "_overall": {alpha, beta, rho_raw, rho_calibrated, ...}
    }
    """
    import json as _json
    from collections import defaultdict

    out_dir.mkdir(parents=True, exist_ok=True)
    cache_path = out_dir / "calibration_params.json"

    if cache_path.exists() and not force:
        with open(cache_path, encoding="utf-8") as fh:
            return _json.load(fh)

    # Load benchmark scores
    p3_dir = model.run_path / "phase3_datapoints"
    bm_scores: dict[str, float] = {}
    if p3_dir.exists():
        import json as _j
        for f in p3_dir.glob("*.datapoints.jsonl"):
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = _j.loads(line)
                    dp_id = rec.get("id", "")
                    bns = rec.get("benchmark_native_score")
                    if dp_id and bns is not None:
                        bm_scores[dp_id] = float(bns)
                except Exception:
                    pass

    if not bm_scores:
        return {}

    # Build (judge, task) -> [(raw_score, gt_score)] mapping
    by_judge_task: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for u in model.units:
        bns = bm_scores.get(u.datapoint_id)
        if bns is not None:
            by_judge_task[(u.judge_model_id, u.task_id)].append(
                (u.score_norm, bns)
            )

    result: dict[str, Any] = {}
    all_raw: list[float] = []
    all_gt: list[float] = []

    for (judge, task), pairs in sorted(by_judge_task.items()):
        raw_x = [p[0] for p in pairs]
        raw_y = [p[1] for p in pairs]
        all_raw.extend(raw_x)
        all_gt.extend(raw_y)
        try:
            params = fit_calibration(raw_x, raw_y, holdout_n=holdout_n)
        except ValueError as exc:
            params = {"error": str(exc), "alpha": 0.0, "beta": 1.0}

        if judge not in result:
            result[judge] = {}
        result[judge][task] = params

    # Overall calibration across all judges and tasks
    if all_raw:
        try:
            result["_overall"] = fit_calibration(all_raw, all_gt, holdout_n=holdout_n)
        except ValueError as exc:
            result["_overall"] = {"error": str(exc), "alpha": 0.0, "beta": 1.0}

    with open(cache_path, "w", encoding="utf-8") as fh:
        _json.dump(result, fh, indent=2)

    return result
