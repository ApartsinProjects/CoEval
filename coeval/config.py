"""Config loading, parsing, and validation (rules V-01 through V-11)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL_NAME_RE = re.compile(r'^[A-Za-z0-9._-]+$')
_TASK_NAME_RE = re.compile(r'^[A-Za-z0-9_-]+$')
_EXPERIMENT_ID_RE = re.compile(r'^[A-Za-z0-9._-]+$')
_RESERVED_SEP = '__'

VALID_ROLES = {'student', 'teacher', 'judge'}
VALID_INTERFACES = {'openai', 'huggingface'}
VALID_LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR'}
VALID_EVAL_MODES = {'single', 'per_factor'}
VALID_PHASE_MODES = {'New', 'Keep', 'Extend', 'Model'}

PHASE_IDS = [
    'attribute_mapping',
    'rubric_mapping',
    'data_generation',
    'response_collection',
    'evaluation',
]
_PHASES_NO_MODEL_MODE = {'attribute_mapping', 'rubric_mapping'}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SamplingConfig:
    target: list[int] | str   # [min, max] or "all"
    nuance: list[int]          # [min, max]
    total: int


@dataclass
class ModelConfig:
    name: str
    interface: str
    parameters: dict[str, Any]
    roles: list[str]
    access_key: str | None = None
    role_parameters: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_parameters_for_role(self, role: str) -> dict[str, Any]:
        merged = dict(self.parameters)
        merged.update(self.role_parameters.get(role, {}))
        return merged


@dataclass
class TaskConfig:
    name: str
    description: str
    output_description: str
    target_attributes: dict[str, list[str]] | str   # map | "auto" | "complete"
    nuanced_attributes: dict[str, list[str]] | str  # map | "auto" | "complete"
    sampling: SamplingConfig
    rubric: dict[str, str] | str                    # map | "auto" | "extend"
    target_attributes_seed: dict[str, list[str]] | None = None
    nuanced_attributes_seed: dict[str, list[str]] | None = None
    store_nuanced: bool = False
    evaluation_mode: str = 'single'
    prompt_library: dict[str, str] = field(default_factory=dict)


@dataclass
class ExperimentConfig:
    id: str
    storage_folder: str
    resume_from: str | None = None
    phases: dict[str, str] = field(default_factory=dict)
    log_level: str = 'INFO'
    quota: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass
class CoEvalConfig:
    models: list[ModelConfig]
    tasks: list[TaskConfig]
    experiment: ExperimentConfig
    _raw: dict = field(default_factory=dict, repr=False, compare=False)

    def get_models_by_role(self, role: str) -> list[ModelConfig]:
        return [m for m in self.models if role in m.roles]

    def get_phase_mode(self, phase_id: str) -> str:
        default = 'Keep' if self.experiment.resume_from else 'New'
        return self.experiment.phases.get(phase_id, default)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_config(path: str) -> CoEvalConfig:
    with open(path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    cfg = _parse_config(raw)
    cfg._raw = raw
    return cfg


def _parse_config(raw: dict) -> CoEvalConfig:
    models = [_parse_model(m) for m in raw.get('models', [])]
    tasks = [_parse_task(t) for t in raw.get('tasks', [])]
    experiment = _parse_experiment(raw.get('experiment', {}))
    return CoEvalConfig(models=models, tasks=tasks, experiment=experiment)


def _parse_model(raw: dict) -> ModelConfig:
    return ModelConfig(
        name=raw['name'],
        interface=raw['interface'],
        parameters=dict(raw.get('parameters', {})),
        roles=list(raw.get('roles', [])),
        access_key=raw.get('access_key'),
        role_parameters={
            k: dict(v) for k, v in raw.get('role_parameters', {}).items()
        },
    )


def _parse_task(raw: dict) -> TaskConfig:
    s = raw.get('sampling', {})
    sampling = SamplingConfig(
        target=s['target'],
        nuance=s['nuance'],
        total=int(s['total']),
    )
    return TaskConfig(
        name=raw['name'],
        description=raw['description'],
        output_description=raw['output_description'],
        target_attributes=raw['target_attributes'],
        nuanced_attributes=raw['nuanced_attributes'],
        sampling=sampling,
        rubric=raw['rubric'],
        target_attributes_seed=raw.get('target_attributes_seed'),
        nuanced_attributes_seed=raw.get('nuanced_attributes_seed'),
        store_nuanced=bool(raw.get('store_nuanced', False)),
        evaluation_mode=raw.get('evaluation_mode', 'single'),
        prompt_library=dict(raw.get('prompt_library', {})),
    )


def _parse_experiment(raw: dict) -> ExperimentConfig:
    return ExperimentConfig(
        id=raw['id'],
        storage_folder=raw['storage_folder'],
        resume_from=raw.get('resume_from'),
        phases=dict(raw.get('phases', {})),
        log_level=raw.get('log_level', 'INFO'),
        quota={k: dict(v) for k, v in raw.get('quota', {}).items()},
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_config(cfg: CoEvalConfig) -> list[str]:
    """Apply all validation rules V-01 through V-11. Returns list of error strings."""
    errors: list[str] = []

    # V-01: all three top-level keys present and non-empty
    if not cfg.models:
        errors.append("Missing required top-level key or empty: 'models'")
    if not cfg.tasks:
        errors.append("Missing required top-level key or empty: 'tasks'")

    # V-02: model names unique
    seen: set[str] = set()
    for m in cfg.models:
        if m.name in seen:
            errors.append(f"Duplicate model name: '{m.name}'")
        seen.add(m.name)

    # V-03: task names unique
    seen = set()
    for t in cfg.tasks:
        if t.name in seen:
            errors.append(f"Duplicate task name: '{t.name}'")
        seen.add(t.name)

    # V-04: name character sets and reserved separator
    for m in cfg.models:
        if not _MODEL_NAME_RE.match(m.name):
            errors.append(
                f"Invalid model name '{m.name}': must match [A-Za-z0-9._-]"
            )
        elif _RESERVED_SEP in m.name:
            errors.append(
                f"Invalid model name '{m.name}': contains reserved separator '__'"
            )
    for t in cfg.tasks:
        if not _TASK_NAME_RE.match(t.name):
            errors.append(
                f"Invalid task name '{t.name}': must match [A-Za-z0-9_-]"
            )
        elif _RESERVED_SEP in t.name:
            errors.append(
                f"Invalid task name '{t.name}': contains reserved separator '__'"
            )
    if cfg.experiment.id and not _EXPERIMENT_ID_RE.match(cfg.experiment.id):
        errors.append(
            f"Invalid experiment id '{cfg.experiment.id}': must match [A-Za-z0-9._-]"
        )

    # V-05: roles valid and non-empty
    for m in cfg.models:
        if not m.roles:
            errors.append(f"Model '{m.name}' has no roles assigned")
        for role in m.roles:
            if role not in VALID_ROLES:
                errors.append(f"Unknown role '{role}' in model '{m.name}'")

    # V-06: interface valid
    for m in cfg.models:
        if m.interface not in VALID_INTERFACES:
            errors.append(f"Unknown interface '{m.interface}' in model '{m.name}'")

    # V-07: required roles present
    needs_teacher = any(
        isinstance(t.target_attributes, str)
        or isinstance(t.nuanced_attributes, str)
        or isinstance(t.rubric, str)
        for t in cfg.tasks
    )
    has_teacher = any('teacher' in m.roles for m in cfg.models)
    has_student = any('student' in m.roles for m in cfg.models)
    has_judge = any('judge' in m.roles for m in cfg.models)

    if needs_teacher and not has_teacher:
        errors.append(
            "No model assigned role 'teacher'; required for phases 1-3 with "
            "auto/complete attributes or rubric"
        )
    if not has_student:
        errors.append(
            "No model assigned role 'student'; required for phase 4"
        )
    if not has_judge:
        errors.append(
            "No model assigned role 'judge'; required for phase 5"
        )

    # V-08: Model mode not valid for phases 1 or 2
    for phase_id in _PHASES_NO_MODEL_MODE:
        mode = cfg.experiment.phases.get(phase_id)
        if mode == 'Model':
            errors.append(
                f"Phase '{phase_id}' does not support mode 'Model'"
            )

    # V-09: rubric 'extend' requires resume_from
    for t in cfg.tasks:
        if t.rubric == 'extend' and not cfg.experiment.resume_from:
            errors.append(
                f"Task '{t.name}': rubric: extend requires resume_from to be set in experiment"
            )

    # V-10: resume_from source folder must exist
    if cfg.experiment.resume_from:
        source_path = os.path.join(
            cfg.experiment.storage_folder, cfg.experiment.resume_from
        )
        if not os.path.isdir(source_path):
            errors.append(
                f"Source experiment '{cfg.experiment.resume_from}' not found in "
                f"{cfg.experiment.storage_folder}"
            )

    # V-11: for new experiments the target folder must NOT already exist
    if not cfg.experiment.resume_from:
        target_path = os.path.join(
            cfg.experiment.storage_folder, cfg.experiment.id
        )
        if os.path.isdir(target_path):
            errors.append(
                f"Experiment folder '{cfg.experiment.id}' already exists in "
                f"'{cfg.experiment.storage_folder}'. Use resume_from to continue it, "
                f"or choose a different experiment ID."
            )

    return errors
