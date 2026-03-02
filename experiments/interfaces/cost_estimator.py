"""Cost and time estimation for CoEval experiments.

This module provides a lightweight pre-flight cost and time estimator that:

1. **Runs a small number of sample LLM calls** per model (configurable; default 2)
   to measure real-world round-trip latency and token throughput.
2. **Uses built-in pricing tables** (USD per 1 M tokens) for all known models;
   falls back to a configurable default for unknown models.
3. **Extrapolates to the full experiment size** based on the phase call-count
   estimates already computed in ``runner.print_execution_plan``.
4. **Adjusts for batch discounts** when batch processing is enabled for a phase
   (50 % for OpenAI/Anthropic native batch; no discount for Gemini pseudo-batch).

Results are returned as a structured dict, printed as a human-readable table,
and written to ``{experiment_folder}/cost_estimate.json``.

Typical usage::

    from experiments.interfaces.cost_estimator import estimate_experiment_cost
    report = estimate_experiment_cost(cfg, storage, logger)
    # report["total_cost_usd"]   → float
    # report["total_time_min"]   → float
    # report["per_model"]        → { model_name: {...} }
    # report["per_phase"]        → { phase_id: {"cost_usd": ..., "calls": ...} }

CLI integration (``coeval run --estimate-only``)::

    coeval run --config my.yaml --estimate-only

Writes the estimate and exits without making pipeline LLM calls.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import CoEvalConfig, ModelConfig
    from ..logger import RunLogger
    from ..storage import ExperimentStorage

# ---------------------------------------------------------------------------
# Pricing tables — loaded from benchmark/provider_pricing.yaml
# Falls back to hardcoded defaults when the YAML is unavailable.
# ---------------------------------------------------------------------------

#: Path to the shared provider pricing YAML (relative to project root)
_PRICING_YAML_PATH = Path(__file__).parent.parent.parent / 'benchmark' / 'provider_pricing.yaml'


def _load_pricing_yaml() -> dict:
    """Load benchmark/provider_pricing.yaml; return {} on failure."""
    try:
        import yaml  # type: ignore
        if _PRICING_YAML_PATH.is_file():
            with open(_PRICING_YAML_PATH, encoding='utf-8') as fh:
                return yaml.safe_load(fh) or {}
    except Exception:
        pass
    return {}


def _build_price_table(pricing_data: dict) -> dict[str, tuple[float, float]]:
    """Convert the providers block of pricing_data to the PRICE_TABLE format.

    Returns a dict of  '''model_id_fragment → (input_price, output_price)'''.

    Provider priority order: 'primary' providers (openai, anthropic, gemini)
    are processed last so their prices take precedence over regional variants
    (e.g. azure_openai) for identically-named model IDs.
    """
    PRIMARY = ('openai', 'anthropic', 'gemini')
    table: dict[str, tuple[float, float]] = {}
    providers = pricing_data.get('providers', {})
    # Process secondary providers first (they can be overridden)
    for provider, pdata in providers.items():
        if provider not in PRIMARY:
            for model_id, prices in pdata.get('models', {}).items():
                table[model_id] = (float(prices['input']), float(prices['output']))
    # Process primary providers last (they take precedence)
    for provider in PRIMARY:
        if provider in providers:
            for model_id, prices in providers[provider].get('models', {}).items():
                table[model_id] = (float(prices['input']), float(prices['output']))
    return table


def _build_batch_discount(pricing_data: dict) -> dict[str, float]:
    """Extract per-interface batch discount multipliers from pricing YAML."""
    discounts: dict[str, float] = {}
    for provider, pdata in pricing_data.get('providers', {}).items():
        interface = pdata.get('interface', provider)
        discounts[interface] = float(pdata.get('batch_discount', 1.0))
    return discounts


#: Hardcoded fallback price table (used when pricing YAML is unavailable).
#: '''model_id_fragment → (input_price, output_price)'''
_FALLBACK_PRICE_TABLE: dict[str, tuple[float, float]] = {
    # OpenAI
    'gpt-4o-mini':		    (0.15,   0.60),
    'gpt-4o':			      (2.50,  10.00),
    'gpt-4-turbo':		   (10.00, 30.00),
    'gpt-4':			      (30.00, 60.00),
    'gpt-3.5-turbo':		  (0.50,   1.50),
    'o1-mini':			    (3.00,  12.00),
    'o1':				     (15.00, 60.00),
    'o3-mini':			    (1.10,   4.40),
    'o4-mini':			    (1.10,   4.40),
    'gpt-4.1-mini':		   (0.40,   1.60),
    'gpt-4.1-nano':		   (0.10,   0.40),
    'gpt-4.1':			    (2.00,   8.00),
    # Anthropic
    'claude-3-5-sonnet':	  (3.00,  15.00),
    'claude-3-5-haiku':	   (0.80,   4.00),
    'claude-3-opus':		  (15.00, 75.00),
    'claude-3-sonnet':	   (3.00,  15.00),
    'claude-3-haiku':		  (0.25,   1.25),
    'claude-opus-4':		  (15.00, 75.00),
    'claude-sonnet-4':	   (3.00,  15.00),
    'claude-haiku-4':		  (0.80,   4.00),
    # Gemini
    'gemini-2.5-pro':		  (1.25,  10.00),
    'gemini-2.5-flash':	   (0.15,   0.60),
    'gemini-2.5-flash-lite':	(0.075,  0.30),
    'gemini-2.0-flash':	   (0.10,   0.40),
    'gemini-2.0-flash-lite':	(0.075,  0.30),
    'gemini-1.5-flash':	   (0.075,  0.30),
    'gemini-1.5-pro':		  (1.25,   5.00),
    'gemini-1.0-pro':		  (0.50,   1.50),
    # OpenRouter open models
    'llama-3.3-70b':		  (0.12,   0.40),
    'llama-3.1-70b':		  (0.10,   0.28),
    'llama-3.1-8b':		   (0.05,   0.08),
    'mistral-small':		  (0.10,   0.30),
    'deepseek-chat':		  (0.14,   0.28),
    'deepseek-r1':		   (0.55,   2.19),
    'qwen-2.5-72b':		   (0.12,   0.39),
    'qwen2.5-72b':		   (0.12,   0.39),
    # Generic OpenRouter fallback
    'openrouter':			(1.00,   3.00),
}

#: Hardcoded fallback batch discounts.
_FALLBACK_BATCH_DISCOUNT: dict[str, float] = {
    'openai':       0.50,
    'anthropic':    0.50,
    'gemini':       0.50,        # Gemini Batch API (50% off) — updated 2026-03
    'azure_openai': 0.50,        # Azure Global Batch API (50% off) — CoEval AzureBatchRunner
    # 'bedrock': 0.50            # Bedrock Batch ~50% off natively but runner not yet implemented
}

# Attempt to load from YAML; fall back to hardcoded defaults.
_pricing_data = _load_pricing_yaml()
PRICE_TABLE: dict[str, tuple[float, float]] = (
    _build_price_table(_pricing_data) or _FALLBACK_PRICE_TABLE
)
BATCH_DISCOUNT: dict[str, float] = (
    _build_batch_discount(_pricing_data) or _FALLBACK_BATCH_DISCOUNT
)

#: Fallback prices when the model is not found in PRICE_TABLE.
DEFAULT_PRICE_INPUT  = 1.00   # USD / 1M tokens
DEFAULT_PRICE_OUTPUT = 3.00

#: Sample prompts used for the estimation probe (short, realistic).
_SAMPLE_PROMPTS = [
    "Generate a short sentence about artificial intelligence.",
    "What is the capital of France? Answer in one word.",
]

#: Typical output tokens expected from sample prompts (for time calibration).
_EXPECTED_SAMPLE_OUTPUT_TOKENS = 20

#: Characters-per-token ratio used as a fallback when tiktoken is unavailable.
_CHARS_PER_TOKEN = 4.0


# ---------------------------------------------------------------------------
# Token counting helpers
# ---------------------------------------------------------------------------

def count_tokens_approx(text: str) -> int:
    """Estimate the token count of *text* using a character-ratio heuristic."""
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def count_tokens_openai(text: str, model: str = 'gpt-4o-mini') -> int:
    """Count tokens using tiktoken (falls back to character ratio)."""
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except Exception:
        return count_tokens_approx(text)


# ---------------------------------------------------------------------------
# Per-model price lookup
# ---------------------------------------------------------------------------

def get_prices(model_cfg: 'ModelConfig') -> tuple[float, float]:
    """Return ``(input_price, output_price)`` in USD per 1 M tokens for *model_cfg*."""
    model_id = (model_cfg.parameters.get('model') or model_cfg.name).lower()
    # Sort by fragment length descending so more-specific keys take priority
    # (e.g. 'gpt-4o-mini' beats 'gpt-4o' for the model 'gpt-4o-mini').
    for fragment, prices in sorted(PRICE_TABLE.items(), key=lambda kv: len(kv[0]), reverse=True):
        if fragment.lower() in model_id:
            return prices
    return DEFAULT_PRICE_INPUT, DEFAULT_PRICE_OUTPUT


# ---------------------------------------------------------------------------
# Estimation probe (sample calls)
# ---------------------------------------------------------------------------

@dataclass
class ModelProbeResult:
    model_name: str
    interface: str
    latency_s: float             = 0.0   # mean round-trip seconds per call
    input_tokens_sample: int     = 0     # tokens in sample prompt
    output_tokens_sample: int    = 0     # tokens in sample response
    tokens_per_second: float     = 0.0   # output tokens / second
    price_input_per_m: float     = 0.0   # USD per 1M input tokens
    price_output_per_m: float    = 0.0   # USD per 1M output tokens
    error: str | None            = None


def _run_sample_calls(
    model_cfg: 'ModelConfig',
    n_samples: int,
    logger: 'RunLogger',
) -> ModelProbeResult:
    """Make *n_samples* tiny LLM calls and return timing/token statistics."""
    result = ModelProbeResult(
        model_name=model_cfg.name,
        interface=model_cfg.interface,
    )
    result.price_input_per_m, result.price_output_per_m = get_prices(model_cfg)

    try:
        iface = _build_interface(model_cfg)
    except Exception as exc:
        result.error = f"Failed to build interface: {exc}"
        logger.warning(f"Estimator: skipping '{model_cfg.name}' — {exc}")
        return result

    latencies: list[float] = []
    in_tokens_list: list[int] = []
    out_tokens_list: list[int] = []
    params = model_cfg.get_parameters_for_role(model_cfg.roles[0])

    for prompt in _SAMPLE_PROMPTS[:n_samples]:
        try:
            t0 = time.perf_counter()
            response = iface.generate(prompt, params)
            elapsed = time.perf_counter() - t0
            latencies.append(elapsed)
            in_tokens_list.append(count_tokens_approx(prompt))
            out_tokens = count_tokens_approx(response)
            out_tokens_list.append(out_tokens)
            logger.info(
                f"Estimator: '{model_cfg.name}' sample call "
                f"({elapsed:.2f}s, ~{out_tokens} output tokens)"
            )
        except Exception as exc:
            logger.warning(
                f"Estimator: sample call for '{model_cfg.name}' failed: {exc}"
            )

    if latencies:
        result.latency_s = sum(latencies) / len(latencies)
        result.input_tokens_sample = (
            sum(in_tokens_list) // len(in_tokens_list)
        )
        result.output_tokens_sample = (
            sum(out_tokens_list) // len(out_tokens_list)
        )
        result.tokens_per_second = (
            result.output_tokens_sample / result.latency_s
            if result.latency_s > 0 else 0.0
        )
    else:
        result.error = "All sample calls failed"

    return result


def _build_interface(model_cfg: 'ModelConfig'):
    """Instantiate the appropriate ModelInterface for *model_cfg*."""
    iface_name = model_cfg.interface
    key = model_cfg.access_key
    if iface_name == 'openai':
        from .openai_iface import OpenAIInterface
        return OpenAIInterface(access_key=key)
    if iface_name == 'anthropic':
        from .anthropic_iface import AnthropicInterface
        return AnthropicInterface(access_key=key)
    if iface_name == 'gemini':
        from .gemini_iface import GeminiInterface
        return GeminiInterface(access_key=key)
    # HuggingFace: don't load weights during estimation — use heuristic only
    raise RuntimeError(
        f"HuggingFace model '{model_cfg.name}' cannot be sampled during "
        "estimation (loading weights would take too long). "
        "Latency and throughput will be estimated from heuristics."
    )


# ---------------------------------------------------------------------------
# Main estimation function
# ---------------------------------------------------------------------------

def estimate_experiment_cost(
    cfg: 'CoEvalConfig',
    storage: 'ExperimentStorage',
    logger: 'RunLogger',
    n_samples: int = 2,
    run_sample_calls: bool = True,
    continue_in_place: bool = False,
    completed_phases: set[str] | None = None,
) -> dict:
    """Estimate cost and time for the experiment.

    When *continue_in_place* is ``True`` the function estimates only the
    **remaining** work by reading already-completed records from storage and
    subtracting them from the full-experiment call counts.  Phases listed in
    *completed_phases* contribute zero calls to the estimate.

    Parameters
    ----------
    cfg:
        Loaded and validated experiment configuration.
    storage:
        Initialised ExperimentStorage (used to write ``cost_estimate.json``
        and to read already-written records when *continue_in_place* is True).
    logger:
        Run logger (output goes to both log file and console via logger).
    n_samples:
        Number of sample LLM calls per model used to calibrate latency.
        Set to 0 to skip sample calls and rely entirely on heuristics.
    run_sample_calls:
        If ``False``, skip sample calls entirely.  Useful in tests or when
        the user only wants a fast heuristic estimate.
    continue_in_place:
        When ``True``, compute **remaining** calls by inspecting storage
        rather than the full experiment budget.
    completed_phases:
        Set of phase IDs already finished (read from ``meta.json``).  Only
        relevant when *continue_in_place* is ``True``; ignored otherwise.

    Returns
    -------
    dict
        ``total_cost_usd``      : float
        ``total_time_min``      : float
        ``per_model``           : dict[str, dict]
        ``per_phase``           : dict[str, dict]
        ``assumptions``         : dict  — values used for the calculation
        ``is_remaining_estimate``: bool — True when estimating remaining work
        ``completed_phases``    : list[str] — phases skipped in resume mode
    """
    _done_phases: set[str] = completed_phases if completed_phases is not None else set()
    mode_label = 'remaining' if continue_in_place else 'full'
    logger.info(
        f"Cost estimator: collecting model statistics "
        f"(mode={mode_label}) ..."
    )

    # --- Probe models with sample calls -----------------------------------
    probe_results: dict[str, ModelProbeResult] = {}
    for model in cfg.models:
        if run_sample_calls and n_samples > 0 and model.interface != 'huggingface':
            pr = _run_sample_calls(model, n_samples, logger)
        else:
            # Heuristic-only (HF or sample calls disabled)
            pr = ModelProbeResult(
                model_name=model.name,
                interface=model.interface,
                latency_s=_heuristic_latency(model),
                input_tokens_sample=count_tokens_approx(
                    _SAMPLE_PROMPTS[0]
                ),
                output_tokens_sample=_EXPECTED_SAMPLE_OUTPUT_TOKENS,
                tokens_per_second=_heuristic_tps(model),
            )
            pr.price_input_per_m, pr.price_output_per_m = get_prices(model)
        probe_results[model.name] = pr

    # --- Build call-count estimates per phase/model -----------------------
    teachers  = cfg.get_models_by_role('teacher')
    students  = cfg.get_models_by_role('student')
    judges    = cfg.get_models_by_role('judge')

    per_phase: dict[str, dict] = {
        'attribute_mapping': {
            'calls_per_model': {},
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'cost_usd': 0.0,
            'time_s': 0.0,
        },
        'rubric_mapping': {
            'calls_per_model': {},
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'cost_usd': 0.0,
            'time_s': 0.0,
        },
        'data_generation': {
            'calls_per_model': {},
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'cost_usd': 0.0,
            'time_s': 0.0,
        },
        'response_collection': {
            'calls_per_model': {},
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'cost_usd': 0.0,
            'time_s': 0.0,
        },
        'evaluation': {
            'calls_per_model': {},
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'cost_usd': 0.0,
            'time_s': 0.0,
        },
    }

    # Typical token counts per prompt type (these match average observed values)
    _TOKENS = {
        'teacher_prompt':  350,   # attribute_mapping prompt
        'teacher_output':  250,   # sampled datapoint (prompt+response pair)
        'student_input':   200,   # the generated prompt sent to student
        'student_output':  180,   # student response
        'judge_prompt':    600,   # evaluation prompt (includes rubric + response)
        'judge_output':    80,    # JSON or word score
        'rubric_prompt':   300,
        'rubric_output':   200,
        'attr_prompt':     250,
        'attr_output':     200,
    }

    total_calls = 0
    total_cost = 0.0
    total_time_s = 0.0

    # Per-provider accumulator  {interface_name: {calls, cost_usd, time_s, models}}
    per_provider: dict[str, dict] = {}

    def _add_phase_cost(
        phase_id: str,
        model_cfg: 'ModelConfig',
        n_calls: int,
        in_tok: int,
        out_tok: int,
    ) -> None:
        nonlocal total_calls, total_cost, total_time_s

        pr   = probe_results[model_cfg.name]
        iface = model_cfg.interface
        # Batch discount
        use_batch_flag = cfg.use_batch(iface, phase_id)
        discount = BATCH_DISCOUNT.get(iface, 1.0) if use_batch_flag else 1.0

        cost_in  = (in_tok  / 1_000_000) * pr.price_input_per_m  * discount
        cost_out = (out_tok / 1_000_000) * pr.price_output_per_m * discount
        phase_cost = cost_in + cost_out

        tps = pr.tokens_per_second if pr.tokens_per_second > 0 else 20.0
        if use_batch_flag and iface in ('openai', 'anthropic'):
            # Batch calls run in the background; use 30 s avg turnaround / call
            phase_time = n_calls * 30.0
        else:
            phase_time = (out_tok / tps) if tps > 0 else n_calls * pr.latency_s

        name = model_cfg.name
        pp = per_phase[phase_id]
        pp['calls_per_model'][name] = pp['calls_per_model'].get(name, 0) + n_calls
        pp['total_input_tokens']    += in_tok
        pp['total_output_tokens']   += out_tok
        pp['cost_usd']              += phase_cost
        pp['time_s']                += phase_time

        total_calls += n_calls
        total_cost  += phase_cost
        total_time_s += phase_time

        # Accumulate per-provider
        if iface not in per_provider:
            per_provider[iface] = {'calls': 0, 'cost_usd': 0.0, 'time_s': 0.0, 'models': []}
        prov = per_provider[iface]
        prov['calls'] += n_calls
        prov['cost_usd'] += phase_cost
        prov['time_s'] += phase_time
        if name not in prov['models']:
            prov['models'].append(name)

    if continue_in_place:
        # ------------------------------------------------------------------
        # Remaining-work estimate: read what's already on disk and only
        # count what still needs to be done.  Completed phases contribute 0.
        # ------------------------------------------------------------------

        # Phase 1 — attribute mapping
        if 'attribute_mapping' not in _done_phases:
            for task in cfg.tasks:
                if (
                    isinstance(task.target_attributes, str)
                    and task.target_attributes != 'complete'
                    and not storage.target_attrs_exist(task.name)
                ):
                    for teacher in teachers:
                        _add_phase_cost(
                            'attribute_mapping', teacher, 1,
                            _TOKENS['attr_prompt'], _TOKENS['attr_output'],
                        )

        # Phase 2 — rubric mapping
        if 'rubric_mapping' not in _done_phases:
            for task in cfg.tasks:
                if isinstance(task.rubric, str) and not storage.rubric_exists(task.name):
                    for teacher in teachers:
                        _add_phase_cost(
                            'rubric_mapping', teacher, 1,
                            _TOKENS['rubric_prompt'], _TOKENS['rubric_output'],
                        )

        # Phase 3 — data generation
        if 'data_generation' not in _done_phases:
            for task in cfg.tasks:
                n = task.sampling.total
                for teacher in teachers:
                    already = storage.count_datapoints(task.name, teacher.name)
                    remaining = max(0, n - already)
                    if remaining:
                        _add_phase_cost(
                            'data_generation', teacher, remaining,
                            _TOKENS['teacher_prompt'] * remaining,
                            _TOKENS['teacher_output'] * remaining,
                        )

        # Phase 4 — response collection
        if 'response_collection' not in _done_phases:
            for task in cfg.tasks:
                n = task.sampling.total
                for teacher in teachers:
                    for student in students:
                        already = len(
                            storage.get_responded_datapoint_ids(
                                task.name, teacher.name, student.name
                            )
                        )
                        remaining = max(0, n - already)
                        if remaining:
                            _add_phase_cost(
                                'response_collection', student, remaining,
                                _TOKENS['student_input'] * remaining,
                                _TOKENS['student_output'] * remaining,
                            )

        # Phase 5 — evaluation
        if 'evaluation' not in _done_phases:
            for task in cfg.tasks:
                n = task.sampling.total
                n_factors = (
                    len(task.rubric) if isinstance(task.rubric, dict) else 4
                )
                calls_per_resp = (
                    n_factors if task.evaluation_mode == 'per_factor' else 1
                )
                for teacher in teachers:
                    for judge in judges:
                        already_evals = len(
                            storage.get_evaluated_response_ids(
                                task.name, teacher.name, judge.name
                            )
                        )
                        # Total expected responses for this (task, teacher, judge):
                        # every student's responses to this teacher's datapoints.
                        total_expected = len(students) * n
                        remaining_responses = max(0, total_expected - already_evals)
                        remaining_calls = remaining_responses * calls_per_resp
                        if remaining_calls:
                            _add_phase_cost(
                                'evaluation', judge, remaining_calls,
                                _TOKENS['judge_prompt'] * remaining_calls,
                                _TOKENS['judge_output'] * remaining_calls,
                            )

    else:
        # ------------------------------------------------------------------
        # Full-experiment estimate (no existing data considered).
        # ------------------------------------------------------------------

        # Attribute mapping (Phase 1): teacher × task (if 'auto'/'complete')
        from ..config import TaskConfig  # noqa: F401 (import kept for future use)
        for task in cfg.tasks:
            if isinstance(task.target_attributes, str) and task.target_attributes != 'complete':
                auto_tasks = 1
            else:
                auto_tasks = 0
            for teacher in teachers:
                calls = auto_tasks
                if calls:
                    _add_phase_cost(
                        'attribute_mapping', teacher, calls,
                        _TOKENS['attr_prompt'] * calls,
                        _TOKENS['attr_output'] * calls,
                    )

        # Rubric mapping (Phase 2): teacher × task (if rubric == 'auto')
        for task in cfg.tasks:
            if isinstance(task.rubric, str):
                for teacher in teachers:
                    _add_phase_cost(
                        'rubric_mapping', teacher, 1,
                        _TOKENS['rubric_prompt'],
                        _TOKENS['rubric_output'],
                    )

        # Data generation (Phase 3): teacher × task × total_per_task
        for task in cfg.tasks:
            n = task.sampling.total
            for teacher in teachers:
                _add_phase_cost(
                    'data_generation', teacher, n,
                    _TOKENS['teacher_prompt'] * n,
                    _TOKENS['teacher_output'] * n,
                )

        # Response collection (Phase 4): student × teacher × task × total
        for task in cfg.tasks:
            n = task.sampling.total
            for teacher in teachers:
                for student in students:
                    _add_phase_cost(
                        'response_collection', student,
                        n * len(teachers),
                        _TOKENS['student_input'] * n,
                        _TOKENS['student_output'] * n,
                    )

        # Evaluation (Phase 5): judge × teacher × student × task × total
        for task in cfg.tasks:
            n = task.sampling.total
            n_factors = (
                len(task.rubric) if isinstance(task.rubric, dict) else 4
            )
            calls_per_resp = n_factors if task.evaluation_mode == 'per_factor' else 1
            for teacher in teachers:
                for student in students:
                    for judge in judges:
                        calls = n * calls_per_resp
                        _add_phase_cost(
                            'evaluation', judge, calls,
                            _TOKENS['judge_prompt'] * calls,
                            _TOKENS['judge_output'] * calls,
                        )

    # --- Per-model summary ------------------------------------------------
    per_model: dict[str, dict] = {}
    for model in cfg.models:
        pr = probe_results[model.name]
        model_calls = sum(
            pp['calls_per_model'].get(model.name, 0)
            for pp in per_phase.values()
        )
        per_model[model.name] = {
            'interface':           model.interface,
            'roles':               model.roles,
            'latency_s':           round(pr.latency_s, 3),
            'tokens_per_second':   round(pr.tokens_per_second, 1),
            'price_input_per_m':   pr.price_input_per_m,
            'price_output_per_m':  pr.price_output_per_m,
            'estimated_calls':     model_calls,
            'sample_error':        pr.error,
        }

    report = {
        'is_remaining_estimate': continue_in_place,
        'completed_phases':      sorted(_done_phases),
        'total_cost_usd':  round(total_cost, 4),
        'total_calls':     total_calls,
        'total_time_min':  round(total_time_s / 60.0, 2),
        'per_phase':       {
            pid: {
                **pdata,
                'cost_usd': round(pdata['cost_usd'], 4),
                'time_min': round(pdata['time_s'] / 60.0, 2),
            }
            for pid, pdata in per_phase.items()
        },
        'per_provider': {
            iface: {
                'calls':    pdata['calls'],
                'cost_usd': round(pdata['cost_usd'], 4),
                'time_min': round(pdata['time_s'] / 60.0, 2),
                'models':   pdata['models'],
            }
            for iface, pdata in sorted(
                per_provider.items(),
                key=lambda kv: kv[1]['cost_usd'],
                reverse=True,
            )
        },
        'per_model':       per_model,
        'assumptions': {
            'token_counts':        _TOKENS,
            'price_table':         PRICE_TABLE,
            'batch_discount':      BATCH_DISCOUNT,
            'pricing_yaml':        str(_PRICING_YAML_PATH) if _PRICING_YAML_PATH.is_file() else 'fallback',
            'n_samples_per_model': n_samples,
        },
    }

    # Write to cost_estimate.json
    try:
        estimate_path = storage.run_path / 'cost_estimate.json'
        estimate_path.write_text(
            json.dumps(report, indent=2, default=str), encoding='utf-8'
        )
        logger.info(f"Cost estimate written to {estimate_path}")
    except Exception as exc:
        logger.warning(f"Could not write cost_estimate.json: {exc}")

    # Print human-readable table
    _print_estimate(report, logger)

    return report


# ---------------------------------------------------------------------------
# Heuristics for HuggingFace and unknown models
# ---------------------------------------------------------------------------

def _heuristic_latency(model_cfg: 'ModelConfig') -> float:
    """Return a rough latency estimate (seconds/call) when sampling is skipped."""
    iface = model_cfg.interface
    if iface == 'openai':
        return 1.5
    if iface == 'anthropic':
        return 2.0
    if iface == 'gemini':
        return 2.0
    if iface == 'openrouter':
        return 2.5
    if iface in ('bedrock', 'azure_openai', 'azure_ai', 'vertex'):
        return 2.0
    # HuggingFace: varies enormously; assume a small-to-medium GPU
    return 10.0


def _heuristic_tps(model_cfg: 'ModelConfig') -> float:
    """Return a rough tokens-per-second estimate."""
    iface = model_cfg.interface
    if iface == 'openai':
        return 80.0
    if iface == 'anthropic':
        return 60.0
    if iface == 'gemini':
        return 100.0
    if iface == 'openrouter':
        return 60.0
    if iface in ('bedrock', 'azure_openai', 'azure_ai', 'vertex'):
        return 70.0
    return 15.0   # HuggingFace on typical GPU


# ---------------------------------------------------------------------------
# Static (no-I/O) heuristic estimator — used by `coeval describe`
# ---------------------------------------------------------------------------

def estimate_cost_static(cfg: 'CoEvalConfig') -> dict:
    """Return a cost estimate dict using only heuristics — no LLM calls, no I/O.

    Designed for lightweight use by ``coeval describe`` and other tooling that
    needs a cost preview without side effects (no files written, no printing).

    Parameters
    ----------
    cfg:
        Loaded experiment configuration.

    Returns
    -------
    dict with keys:
        ``total_cost_usd``   : float
        ``per_phase``        : dict[phase_id, {"cost_usd": float, "calls": int}]
        ``per_provider``     : dict[interface, {"cost_usd": float, "calls": int, "batch": bool}]
        ``per_model``        : dict[model_name, {"cost_usd": float, "calls": int, "interface": str}]
        ``batch_savings_usd``: float — amount saved vs. full-price (no batch)
    """
    # Token constants (same as in estimate_experiment_cost)
    _TOKENS = {
        'teacher_prompt': 350,
        'teacher_output': 250,
        'student_input':  200,
        'student_output': 180,
        'judge_prompt':   600,
        'judge_output':    80,
        'attr_prompt':    250,
        'attr_output':    200,
        'rubric_prompt':  300,
        'rubric_output':  200,
    }

    teachers = cfg.get_models_by_role('teacher')
    students = cfg.get_models_by_role('student')
    judges   = cfg.get_models_by_role('judge')
    active_teachers = [t for t in teachers if t.interface != 'benchmark']

    per_phase:    dict[str, dict] = {
        p: {'cost_usd': 0.0, 'calls': 0, 'cost_usd_no_batch': 0.0}
        for p in ('attribute_mapping', 'rubric_mapping',
                  'data_generation', 'response_collection', 'evaluation')
    }
    per_provider: dict[str, dict] = {}
    per_model:    dict[str, dict] = {}

    def _add(phase_id: str, model_cfg: 'ModelConfig',
             calls: int, in_tok: int, out_tok: int) -> None:
        pi, po  = get_prices(model_cfg)
        iface   = model_cfg.interface
        use_bat = cfg.use_batch(iface, phase_id)
        disc    = BATCH_DISCOUNT.get(iface, 1.0) if use_bat else 1.0
        cost    = (pi * in_tok + po * out_tok) / 1_000_000 * disc
        cost_nb = (pi * in_tok + po * out_tok) / 1_000_000  # no-batch reference

        per_phase[phase_id]['cost_usd']          += cost
        per_phase[phase_id]['cost_usd_no_batch'] += cost_nb
        per_phase[phase_id]['calls']             += calls

        name = model_cfg.name
        if iface not in per_provider:
            per_provider[iface] = {'cost_usd': 0.0, 'calls': 0,
                                   'batch': False, 'models': []}
        per_provider[iface]['cost_usd'] += cost
        per_provider[iface]['calls']    += calls
        if use_bat:
            per_provider[iface]['batch'] = True
        if name not in per_provider[iface]['models']:
            per_provider[iface]['models'].append(name)

        if name not in per_model:
            per_model[name] = {'cost_usd': 0.0, 'calls': 0,
                               'interface': iface, 'roles': model_cfg.roles}
        per_model[name]['cost_usd'] += cost
        per_model[name]['calls']    += calls

    for task in cfg.tasks:
        n = task.sampling.total

        # Phase 1 — attribute mapping (only if 'auto')
        if isinstance(task.target_attributes, str) and task.target_attributes != 'complete':
            for t in active_teachers:
                _add('attribute_mapping', t, 1,
                     _TOKENS['attr_prompt'], _TOKENS['attr_output'])

        # Phase 2 — rubric mapping (only if 'auto')
        if isinstance(task.rubric, str):
            for t in active_teachers:
                _add('rubric_mapping', t, 1,
                     _TOKENS['rubric_prompt'], _TOKENS['rubric_output'])

        # Phase 3 — data generation (active teachers only)
        for t in active_teachers:
            _add('data_generation', t, n,
                 _TOKENS['teacher_prompt'] * n, _TOKENS['teacher_output'] * n)

        # Phase 4 — response collection (all teachers incl. benchmark)
        for _t in teachers:
            for s in students:
                _add('response_collection', s, n,
                     _TOKENS['student_input'] * n, _TOKENS['student_output'] * n)

        # Phase 5 — evaluation
        n_factors = len(task.rubric) if isinstance(task.rubric, dict) else 4
        cpr = n_factors if task.evaluation_mode == 'per_factor' else 1
        for _t in teachers:
            for _s in students:
                for j in judges:
                    calls = n * cpr
                    _add('evaluation', j, calls,
                         _TOKENS['judge_prompt'] * calls,
                         _TOKENS['judge_output'] * calls)

    total_cost    = sum(p['cost_usd']          for p in per_phase.values())
    total_no_bat  = sum(p['cost_usd_no_batch'] for p in per_phase.values())
    batch_savings = max(0.0, total_no_bat - total_cost)

    return {
        'total_cost_usd':    round(total_cost, 2),
        'batch_savings_usd': round(batch_savings, 2),
        'per_phase': {
            pid: {
                'cost_usd': round(p['cost_usd'], 2),
                'calls':    p['calls'],
                'batch_savings_usd': round(
                    max(0.0, p['cost_usd_no_batch'] - p['cost_usd']), 2),
            }
            for pid, p in per_phase.items()
        },
        'per_provider': {
            iface: {
                'cost_usd': round(p['cost_usd'], 2),
                'calls':    p['calls'],
                'batch':    p['batch'],
                'models':   p['models'],
            }
            for iface, p in sorted(
                per_provider.items(),
                key=lambda kv: kv[1]['cost_usd'], reverse=True)
        },
        'per_model': {
            name: {
                'cost_usd':  round(m['cost_usd'], 2),
                'calls':     m['calls'],
                'interface': m['interface'],
                'roles':     m['roles'],
            }
            for name, m in sorted(
                per_model.items(),
                key=lambda kv: kv[1]['cost_usd'], reverse=True)
        },
    }


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def _print_estimate(report: dict, logger: 'RunLogger') -> None:
    """Print a formatted cost/time estimate table."""
    is_remaining = report.get('is_remaining_estimate', False)
    title = (
        'CoEval -- Remaining Work Estimate'
        if is_remaining else
        'CoEval -- Cost & Time Estimate'
    )
    done_phases = report.get('completed_phases', [])
    lines = ['', '=' * 64, title, '=' * 64]
    if is_remaining and done_phases:
        lines.append(f"  Phases already done  : {', '.join(done_phases)}")
    lines += [
        f"  Total estimated cost : ${report['total_cost_usd']:.4f} USD",
        f"  Total LLM calls      : {report['total_calls']}",
        f"  Total estimated time : {report['total_time_min']:.1f} min",
        '',
        '  Per-phase breakdown:',
        f"  {'Phase':<25}  {'Calls':>7}  {'Cost (USD)':>12}  {'Time (min)':>11}",
        '  ' + '-' * 60,
    ]
    for pid, pdata in report['per_phase'].items():
        calls = sum(pdata['calls_per_model'].values())
        lines.append(
            f"  {pid:<25}  {calls:>7}  "
            f"${pdata['cost_usd']:>10.4f}  {pdata['time_min']:>10.1f}"
        )
    if report.get('per_provider'):
        lines += [
            '',
            '  Per-provider breakdown:',
            f"  {'Provider':<16}  {'Calls':>7}  {'Cost (USD)':>12}  {'Time (min)':>11}  Models",
            '  ' + '-' * 72,
        ]
        for iface, pdata in report['per_provider'].items():
            models_str = ', '.join(pdata['models'])
            lines.append(
                f"  {iface:<16}  {pdata['calls']:>7}  "
                f"${pdata['cost_usd']:>10.4f}  {pdata['time_min']:>10.1f}"
                f"  {models_str}"
            )
    lines += [
        '',
        '  Per-model breakdown:',
        f"  {'Model':<30}  {'Calls':>7}  {'Latency':>9}  {'TPS':>6}",
        '  ' + '-' * 60,
    ]
    for mname, mdata in report['per_model'].items():
        err = f'  [!] {mdata["sample_error"]}' if mdata.get('sample_error') else ''
        lines.append(
            f"  {mname:<30}  {mdata['estimated_calls']:>7}  "
            f"{mdata['latency_s']:>8.2f}s  {mdata['tokens_per_second']:>5.0f}"
            + err
        )
    lines += ['=' * 64, '']
    output = '\n'.join(lines)
    # Print to stdout and log
    print(output)
    logger.info(output)
