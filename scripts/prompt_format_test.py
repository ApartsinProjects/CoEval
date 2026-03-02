"""
prompt_format_test.py
=====================
Experiment: which prompt format + generation parameters maximises structured-
output success for small HuggingFace instruction-tuned models?

Failure modes seen in the smoke test
--------------------------------------
  smollm2-135m  -> echoes attribute names as JSON keys (no format comprehension)
  smollm2-360m  -> uses semantically correct but non-canonical key names
                  e.g. "subject" instead of "prompt"
  smollm2-1b7   -> occasionally produces only one of the two required fields
  qwen2p5-*     -> mostly works, minor formatting deviations

Strategies tested
-----------------
  baseline      Current canonical prompt (control)
  strict_json   Adds explicit "Output ONLY raw JSON, start { end }" guard
  fill_template Gives a literal JSON template with placeholder text to replace
  few_shot      Prepends a complete worked example in the expected format
  xml_tags      Uses <prompt>...</prompt><response>...</response> instead of JSON
  two_step      Two separate single-field calls (avoids JSON entirely; 2x cost)
  temp_zero     Baseline prompt but temperature=0 (greedy/deterministic)

Usage
-----
  python experiments/prompt_format_test.py                 # all models, all strategies
  python experiments/prompt_format_test.py --quick         # 2 smallest models, 2 trials
  python experiments/prompt_format_test.py --models smollm2-135m smollm2-360m
  python experiments/prompt_format_test.py --trials 5

Results are printed as an ASCII table and saved to experiments/results.json.
"""

from __future__ import annotations

import argparse
import gc
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup -- allow running from repo root without installing
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from runner.interfaces.huggingface_iface import HuggingFaceInterface
from runner.phases.utils import extract_prompt_response

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------
ALL_MODELS: dict[str, str] = {
    "smollm2-135m": "HuggingFaceTB/SmolLM2-135M-Instruct",
    "smollm2-360m": "HuggingFaceTB/SmolLM2-360M-Instruct",
    "smollm2-1b7":  "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "qwen2p5-0b5":  "Qwen/Qwen2.5-0.5B-Instruct",
    "qwen2p5-1b5":  "Qwen/Qwen2.5-1.5B-Instruct",
}

# ---------------------------------------------------------------------------
# Fixed task context (email_subject task from the smoke test)
# ---------------------------------------------------------------------------
TASK_DESC     = "Write a concise email subject line for a given email body."
OUTPUT_DESC   = "A single subject line of 5 to 12 words that captures the main point."
TARGET_ATTRS  = json.dumps({"intent": "request"})
NUANCED_ATTRS = json.dumps({"domain": "hr", "writing_style": "terse"})

PARAMS_HOT  = dict(temperature=0.8, max_new_tokens=512)   # default
PARAMS_COLD = dict(temperature=0.0, max_new_tokens=512)   # greedy / temp_zero

RESULTS_FILE = Path(__file__).parent / "results.json"

# ---------------------------------------------------------------------------
# Output extraction
# ---------------------------------------------------------------------------

def _try_json(text: str) -> tuple[str, str] | None:
    """Attempt JSON extraction using CoEval's multi-strategy approach."""
    cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'```\s*$', '', cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    attempts: list[str] = [cleaned]
    for start in ('{', '['):
        idx = cleaned.find(start)
        if idx != -1:
            attempts.append(cleaned[idx:])
    for start, end in (('{', '}'), ('[', ']')):
        s, e = cleaned.find(start), cleaned.rfind(end)
        if 0 <= s < e:
            attempts.append(cleaned[s:e + 1])

    for candidate in attempts:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                obj = obj[0]
            if isinstance(obj, dict):
                return extract_prompt_response(obj)
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _try_xml(text: str) -> tuple[str, str] | None:
    """Attempt XML-tag extraction: <prompt>...</prompt><response>...</response>."""
    p = re.search(r'<prompt>(.*?)</prompt>', text, re.DOTALL | re.IGNORECASE)
    r = re.search(r'<response>(.*?)</response>', text, re.DOTALL | re.IGNORECASE)
    if p and r:
        pv, rv = p.group(1).strip(), r.group(1).strip()
        if pv and rv:
            return pv, rv
    return None


def try_extract(raw: str, strategy: str) -> tuple[str, str] | None:
    """Return (prompt_text, response_text) or None.  For xml_tags, try XML first."""
    if strategy == 'xml_tags':
        return _try_xml(raw) or _try_json(raw)
    return _try_json(raw) or _try_xml(raw)

# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def make_prompt(strategy: str) -> str:
    """Build the prompt string for a given strategy (all except two_step)."""

    if strategy in ('baseline', 'temp_zero'):
        # Canonical CoEval template -- identical wording to prompts.py
        return (
            f"Generate a natural benchmark data point for the task {TASK_DESC} and produce a "
            f"response {OUTPUT_DESC}, where the response is specified with {TARGET_ATTRS}. "
            f"To make the datapoint naturalistic, use the following nuance parameters: "
            f"{NUANCED_ATTRS}. Return as JSON with exactly two keys: \"prompt\" and \"response\"."
        )

    if strategy == 'strict_json':
        # Adds hard constraints: no prose, no code fences, must start/end with braces
        return (
            f"Generate a natural benchmark data point.\n"
            f"Task: {TASK_DESC}\n"
            f"Output format: {OUTPUT_DESC}\n"
            f"Required attributes: {TARGET_ATTRS}\n"
            f"Nuance parameters: {NUANCED_ATTRS}\n\n"
            f"IMPORTANT: Your entire response must be a single raw JSON object -- "
            f"no explanation, no markdown code fences, no text before or after. "
            f"Start your response with {{ and end with }}. "
            f"Use exactly two keys: \"prompt\" (the input text) and \"response\" (the output text)."
        )

    if strategy == 'fill_template':
        # Show a literal template; the model just needs to replace the placeholders
        return (
            f"Task: {TASK_DESC}\n"
            f"Output: {OUTPUT_DESC}\n"
            f"Attributes: {TARGET_ATTRS} | Nuance: {NUANCED_ATTRS}\n\n"
            f"Complete the JSON below by replacing the placeholder text with real content:\n"
            f"{{\n"
            f'  "prompt": "WRITE THE EMAIL BODY HERE",\n'
            f'  "response": "WRITE THE SUBJECT LINE HERE"\n'
            f"}}\n\n"
            f"Return only the completed JSON object."
        )

    if strategy == 'few_shot':
        # One concrete worked example, then ask for a new one
        example = json.dumps(
            {"prompt": "Hi team, please submit your timesheets by Friday EOD.",
             "response": "Timesheet Submission Reminder -- Due Friday"},
            indent=2
        )
        return (
            f"Generate a benchmark data point for: {TASK_DESC}\n"
            f"Response format: {OUTPUT_DESC}\n"
            f"Required attributes: {TARGET_ATTRS}. Nuance: {NUANCED_ATTRS}.\n\n"
            f"Follow this example format exactly:\n{example}\n\n"
            f"Now generate a NEW data point in the same JSON format "
            f"(keys must be \"prompt\" and \"response\"):"
        )

    if strategy == 'xml_tags':
        # Use XML instead of JSON -- simpler tag-matching for small models
        return (
            f"Generate a benchmark data point.\n"
            f"Task: {TASK_DESC}\n"
            f"Output format: {OUTPUT_DESC}\n"
            f"Attributes: {TARGET_ATTRS}. Nuance: {NUANCED_ATTRS}.\n\n"
            f"Respond using exactly these XML tags -- put real content between the tags:\n"
            f"<prompt>the email body text</prompt>\n"
            f"<response>the subject line</response>"
        )

    raise ValueError(f"Unknown strategy: {strategy!r}")

# ---------------------------------------------------------------------------
# Two-step strategy helper
# ---------------------------------------------------------------------------

def run_two_step(iface: HuggingFaceInterface) -> tuple[bool, str, str, float]:
    """
    Strategy 'two_step': two separate plain-text LLM calls.
    Call 1 -> generate the email body (prompt field)
    Call 2 -> generate the subject line for that body (response field)
    No JSON parsing required.
    """
    t0 = time.perf_counter()

    p1 = (
        f"Write a short, realistic HR department email body requesting something "
        f"from employees. Style: terse. Output only the email body text, nothing else."
    )
    email_body = iface.generate(p1, PARAMS_HOT).strip()

    p2 = (
        f"Write a concise email subject line (5 to 12 words) for this email body:\n\n"
        f"{email_body}\n\n"
        f"Output only the subject line, nothing else."
    )
    subject_line = iface.generate(p2, PARAMS_HOT).strip()

    elapsed = time.perf_counter() - t0
    ok = bool(email_body) and bool(subject_line) and len(email_body) > 10 and len(subject_line) > 3
    return ok, email_body, subject_line, elapsed

# ---------------------------------------------------------------------------
# Single trial runner
# ---------------------------------------------------------------------------

def run_trial(strategy: str, iface: HuggingFaceInterface) -> dict:
    """Run one trial and return a result dict."""
    if strategy == 'two_step':
        ok, pt, rt, elapsed = run_two_step(iface)
        return {
            'success': ok,
            'prompt_text':   (pt[:120] if ok else ""),
            'response_text': (rt[:80]  if ok else ""),
            'raw_output': f"[body] {pt[:100]} | [subject] {rt[:80]}",
            'error': None if ok else "Two-step fields empty/too short",
            'elapsed_s': round(elapsed, 2),
        }

    params = PARAMS_COLD if strategy == 'temp_zero' else PARAMS_HOT
    prompt = make_prompt(strategy)

    t0 = time.perf_counter()
    try:
        raw = iface.generate(prompt, params)
    except Exception as exc:
        return {
            'success': False, 'prompt_text': '', 'response_text': '',
            'raw_output': '', 'error': str(exc)[:150],
            'elapsed_s': round(time.perf_counter() - t0, 2),
        }
    elapsed = round(time.perf_counter() - t0, 2)

    extracted = try_extract(raw, strategy)
    if extracted:
        pt, rt = extracted
        return {
            'success': True,
            'prompt_text':   pt[:120],
            'response_text': rt[:80],
            'raw_output': raw[:250],
            'error': None,
            'elapsed_s': elapsed,
        }

    # Diagnosis: what keys did the model actually return?
    key_info = ""
    try:
        m = re.search(r'\{[^}]+\}', raw)
        if m:
            obj = json.loads(m.group())
            key_info = f"keys={list(obj.keys())}"
    except Exception:
        pass
    error_msg = f"Cannot extract -- {key_info or repr(raw[:100])}"

    return {
        'success': False, 'prompt_text': '', 'response_text': '',
        'raw_output': raw[:250], 'error': error_msg,
        'elapsed_s': elapsed,
    }

# ---------------------------------------------------------------------------
# Experiment loop
# ---------------------------------------------------------------------------

ALL_STRATEGIES = ['baseline', 'strict_json', 'fill_template', 'few_shot',
                  'xml_tags', 'two_step', 'temp_zero']


def run_experiment(
    model_names: list[str],
    strategies: list[str],
    n_trials: int,
) -> dict[str, Any]:

    results: dict[str, Any] = {}

    for model_name in model_names:
        model_id = ALL_MODELS[model_name]
        print(f"\n{'=' * 62}")
        print(f"  Model: {model_name}  ({model_id})")
        print(f"{'=' * 62}")

        try:
            iface = HuggingFaceInterface(model_id=model_id)
        except Exception as exc:
            print(f"  x Failed to load: {exc}")
            results[model_name] = {'load_error': str(exc)}
            continue

        results[model_name] = {}

        for strategy in strategies:
            print(f"\n  -- strategy: {strategy} --")
            trials: list[dict] = []
            passes = 0

            for t_idx in range(n_trials):
                result = run_trial(strategy, iface)
                trials.append(result)
                if result['success']:
                    passes += 1
                    print(f"    [{t_idx+1}/{n_trials}] v  ({result['elapsed_s']:.1f}s)")
                    print(f"           prompt:   {result['prompt_text'][:70]!r}")
                    print(f"           response: {result['response_text'][:55]!r}")
                else:
                    print(f"    [{t_idx+1}/{n_trials}] x  {result['error']}  ({result['elapsed_s']:.1f}s)")

            avg_t = round(sum(r['elapsed_s'] for r in trials) / len(trials), 2)
            pass_rate = passes / n_trials
            print(f"    ->  {passes}/{n_trials} passed ({pass_rate:.0%}), avg {avg_t:.1f}s/call")

            results[model_name][strategy] = {
                'pass_rate': pass_rate,
                'passes': passes,
                'n_trials': n_trials,
                'avg_time_s': avg_t,
                'trials': trials,
            }

        # Free GPU/CPU memory before loading the next model
        del iface
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    return results

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_summary(results: dict, strategies: list[str]) -> None:
    loaded = [m for m in results if 'load_error' not in results[m]]
    if not loaded:
        print("\nNo models loaded successfully.")
        return

    # -- Pass-rate table ------------------------------------------------------
    col0, colw = 15, 13
    header = f"{'Model':{col0}}" + "".join(f"{s:{colw}}" for s in strategies)
    divider = "-" * len(header)
    print(f"\n{'=' * len(header)}")
    print("  PASS RATE -- successes / trials (% pass)")
    print(f"{'=' * len(header)}")
    print(header)
    print(divider)
    for model in loaded:
        row = f"{model:{col0}}"
        for s in strategies:
            d = results[model].get(s)
            if d is None:
                row += f"{'--':{colw}}"
            else:
                cell = f"{d['passes']}/{d['n_trials']} ({d['pass_rate']:.0%})"
                row += f"{cell:{colw}}"
        print(row)
    print(f"{'=' * len(header)}")

    # -- Average call-time table ----------------------------------------------
    print(f"\n{'-' * len(header)}")
    print("  AVG TIME per call (seconds)")
    print(f"{'-' * len(header)}")
    print(header)
    print(divider)
    for model in loaded:
        row = f"{model:{col0}}"
        for s in strategies:
            d = results[model].get(s)
            if d is None:
                row += f"{'--':{colw}}"
            else:
                cell = f"{d['avg_time_s']:.1f}s"
                row += f"{cell:{colw}}"
        print(row)
    print(f"{'-' * len(header)}")

    # -- Per-model best strategy ----------------------------------------------
    print("\n  BEST STRATEGY per model (by pass rate, tie-broken by speed):")
    for model in loaded:
        best_s = max(
            strategies,
            key=lambda s: (
                results[model].get(s, {}).get('pass_rate', -1),
                -results[model].get(s, {}).get('avg_time_s', 9999),
            ),
        )
        d = results[model].get(best_s, {})
        print(f"    {model:15s}  ->  {best_s!r}  "
              f"({d.get('passes',0)}/{d.get('n_trials',0)}, "
              f"{d.get('avg_time_s',0):.1f}s/call)")

    # -- Overall strategy ranking ---------------------------------------------
    print("\n  OVERALL STRATEGY RANKING (across all tested models):")
    strategy_totals: dict[str, dict] = {}
    for s in strategies:
        total_passes  = sum(results[m].get(s, {}).get('passes',  0) for m in loaded)
        total_trials  = sum(results[m].get(s, {}).get('n_trials', 0) for m in loaded)
        total_time    = sum(results[m].get(s, {}).get('avg_time_s', 0) for m in loaded)
        strategy_totals[s] = {
            'passes': total_passes,
            'trials': total_trials,
            'rate':   total_passes / total_trials if total_trials else 0,
            'avg_time': total_time / len(loaded) if loaded else 0,
        }

    ranked = sorted(strategies, key=lambda s: (-strategy_totals[s]['rate'],
                                                strategy_totals[s]['avg_time']))
    for rank, s in enumerate(ranked, 1):
        t = strategy_totals[s]
        print(f"    #{rank}  {s:20s}  {t['passes']}/{t['trials']} ({t['rate']:.0%})  "
              f"avg {t['avg_time']:.1f}s/call")


def print_recommendations(results: dict, strategies: list[str]) -> None:
    """Print actionable recommendations for updating the smoke-test config."""
    loaded = [m for m in results if 'load_error' not in results[m]]
    print("\n" + "=" * 62)
    print("  RECOMMENDATIONS")
    print("=" * 62)

    # Best single strategy across all models
    totals: dict[str, float] = {}
    for s in strategies:
        passes = sum(results[m].get(s, {}).get('passes', 0) for m in loaded)
        trials = sum(results[m].get(s, {}).get('n_trials', 0) for m in loaded)
        totals[s] = passes / trials if trials else 0

    best_global = max(totals, key=lambda s: totals[s])

    print(f"\n  1. GLOBAL WINNER: '{best_global}' ({totals[best_global]:.0%} pass rate).")
    if best_global != 'baseline':
        note = {
            'strict_json':    "Add it as the default 'sample' template in prompts.py.",
            'fill_template':  "Add it as the default 'sample' template in prompts.py.",
            'few_shot':       "Add it as the default 'sample' template in prompts.py.",
            'xml_tags':       "Add XML extraction to phases/utils.py and update the template.",
            'two_step':       "Refactor phase3._generate_datapoints into two sequential calls.",
            'temp_zero':      "Set teacher temperature=0.0 in the smoke-test YAML for all models.",
        }.get(best_global, "")
        if note:
            print(f"     -> {note}")

    print(f"\n  2. PER-MODEL OVERRIDES via prompt_library in the YAML config:")
    print(f"     Models that still fail with the global winner can use")
    print(f"     model-specific prompt overrides, e.g.:")
    print(f"       prompt_library:")
    for model in loaded:
        d = results[model]
        best = max(strategies,
                   key=lambda s: d.get(s, {}).get('pass_rate', -1))
        rate = d.get(best, {}).get('pass_rate', 0)
        if best != best_global and rate > 0:
            print(f"         sample.{model}: \"<{best} template>\"  # {rate:.0%} pass")

    print(f"\n  3. COST CONSIDERATION:")
    two_step_ok = 'two_step' in totals and totals.get('two_step', 0) > 0
    if two_step_ok:
        print(f"     'two_step' avoids JSON parsing entirely but costs 2x LLM calls.")
        print(f"     Use it as a per-model fallback, not the global default.")

    print(f"\n  4. IRREDEEMABLY SMALL MODELS:")
    for model in loaded:
        all_failed = all(
            results[model].get(s, {}).get('pass_rate', 0) == 0
            for s in strategies
        )
        if all_failed:
            print(f"     '{model}' failed every strategy -- consider removing it from the")
            print(f"     teacher/judge roles and keeping it as student-only.")
    print()

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CoEval prompt-format experiment for small HuggingFace models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--models', nargs='+', choices=list(ALL_MODELS.keys()),
        default=list(ALL_MODELS.keys()),
        help='Models to test (default: all 5)',
    )
    parser.add_argument(
        '--strategies', nargs='+', choices=ALL_STRATEGIES,
        default=ALL_STRATEGIES,
        help='Strategies to test (default: all 7)',
    )
    parser.add_argument(
        '--trials', type=int, default=3,
        help='Trials per (model x strategy) cell (default: 3)',
    )
    parser.add_argument(
        '--quick', action='store_true',
        help='Quick mode: smollm2-135m + smollm2-360m, 2 trials',
    )
    args = parser.parse_args()

    if args.quick:
        model_names = ['smollm2-135m', 'smollm2-360m']
        n_trials    = 2
    else:
        model_names = args.models
        n_trials    = args.trials
    strategies = args.strategies

    print("CoEval -- Prompt Format Experiment")
    print(f"Models     : {model_names}")
    print(f"Strategies : {strategies}")
    print(f"Trials/cell: {n_trials}")
    print(f"Task       : {TASK_DESC}")

    results = run_experiment(model_names, strategies, n_trials)

    print_summary(results, strategies)
    print_recommendations(results, strategies)

    RESULTS_FILE.parent.mkdir(exist_ok=True)
    with open(RESULTS_FILE, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=2)
    print(f"Detailed results saved -> {RESULTS_FILE}")


if __name__ == '__main__':
    main()
