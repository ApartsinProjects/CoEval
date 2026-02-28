"""Evaluation Experiment Storage (EES): all filesystem I/O for experiment artifacts."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class ExperimentStorage:
    """Manages a single experiment's folder tree under storage_folder/experiment_id/."""

    def __init__(self, storage_folder: str, experiment_id: str) -> None:
        self.root = Path(storage_folder) / experiment_id
        self.run_path = self.root  # alias used by probe / cost_estimator
        self.phase1 = self.root / 'phase1_attributes'
        self.phase2 = self.root / 'phase2_rubric'
        self.phase3 = self.root / 'phase3_datapoints'
        self.phase4 = self.root / 'phase4_responses'
        self.phase5 = self.root / 'phase5_evaluations'
        self.log_path = self.root / 'run.log'

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(
        self,
        config_raw: dict,
        resume_from_id: str | None = None,
        source_storage_folder: str | None = None,
        continue_in_place: bool = False,
    ) -> None:
        """Create the folder tree, write config.yaml snapshot and meta.json.

        If resume_from_id is set, copies phase1/2 artifacts from the source
        experiment into this new experiment folder before execution begins.

        If continue_in_place is True, re-opens an existing experiment folder
        without clearing any data.  config.yaml and meta.json are preserved
        so the runner can read phases_completed and resume from the right point.
        """
        if continue_in_place:
            self.root.mkdir(parents=True, exist_ok=True)
            for d in (self.phase1, self.phase2, self.phase3, self.phase4, self.phase5):
                d.mkdir(exist_ok=True)
            return

        self.root.mkdir(parents=True, exist_ok=False)
        for d in (self.phase1, self.phase2, self.phase3, self.phase4, self.phase5):
            d.mkdir()

        # Write config snapshot
        with open(self.root / 'config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(config_raw, f, default_flow_style=False, allow_unicode=True)

        # Initialize meta.json
        self._write_json(self.root / 'meta.json', {
            'experiment_id': self.root.name,
            'status': 'in_progress',
            'created_at': _now_iso(),
            'updated_at': _now_iso(),
            'phases_completed': [],
            'phases_in_progress': [],
            'resume_from': resume_from_id,
        })

        # Copy phase 1 & 2 artifacts from source if resuming
        if resume_from_id and source_storage_folder:
            src_root = Path(source_storage_folder) / resume_from_id
            for src_file in (src_root / 'phase1_attributes').glob('*.json'):
                shutil.copy2(src_file, self.phase1 / src_file.name)
            for src_file in (src_root / 'phase2_rubric').glob('*.json'):
                shutil.copy2(src_file, self.phase2 / src_file.name)

    # ------------------------------------------------------------------
    # meta.json
    # ------------------------------------------------------------------

    def read_meta(self) -> dict:
        return self._read_json(self.root / 'meta.json')

    def update_meta(
        self,
        phase_started: str | None = None,
        phase_completed: str | None = None,
        status: str | None = None,
    ) -> None:
        meta = self.read_meta()
        meta['updated_at'] = _now_iso()
        if phase_started and phase_started not in meta['phases_in_progress']:
            meta['phases_in_progress'].append(phase_started)
        if phase_completed:
            meta['phases_in_progress'] = [
                p for p in meta['phases_in_progress'] if p != phase_completed
            ]
            if phase_completed not in meta['phases_completed']:
                meta['phases_completed'].append(phase_completed)
        if status:
            meta['status'] = status
        self._write_json(self.root / 'meta.json', meta)

    # ------------------------------------------------------------------
    # Phase 1 — attribute maps
    # ------------------------------------------------------------------

    def write_target_attrs(self, task_id: str, attrs: dict) -> None:
        self._write_json(self.phase1 / f'{task_id}.target_attrs.json', attrs)

    def write_nuanced_attrs(self, task_id: str, attrs: dict) -> None:
        self._write_json(self.phase1 / f'{task_id}.nuanced_attrs.json', attrs)

    def read_target_attrs(self, task_id: str) -> dict:
        return self._read_json(self.phase1 / f'{task_id}.target_attrs.json')

    def read_nuanced_attrs(self, task_id: str) -> dict:
        return self._read_json(self.phase1 / f'{task_id}.nuanced_attrs.json')

    def target_attrs_exist(self, task_id: str) -> bool:
        return (self.phase1 / f'{task_id}.target_attrs.json').exists()

    def nuanced_attrs_exist(self, task_id: str) -> bool:
        return (self.phase1 / f'{task_id}.nuanced_attrs.json').exists()

    # ------------------------------------------------------------------
    # Phase 2 — rubric
    # ------------------------------------------------------------------

    def write_rubric(self, task_id: str, rubric: dict) -> None:
        self._write_json(self.phase2 / f'{task_id}.rubric.json', rubric)

    def read_rubric(self, task_id: str) -> dict:
        return self._read_json(self.phase2 / f'{task_id}.rubric.json')

    def rubric_exists(self, task_id: str) -> bool:
        return (self.phase2 / f'{task_id}.rubric.json').exists()

    # ------------------------------------------------------------------
    # Phase 3 — datapoints
    # ------------------------------------------------------------------

    def datapoints_path(self, task_id: str, teacher_id: str) -> Path:
        return self.phase3 / f'{task_id}.{teacher_id}.datapoints.jsonl'

    def append_datapoint(self, task_id: str, teacher_id: str, record: dict) -> None:
        self._append_jsonl(self.datapoints_path(task_id, teacher_id), record)

    def read_datapoints(self, task_id: str, teacher_id: str) -> list[dict]:
        return self._read_jsonl(self.datapoints_path(task_id, teacher_id))

    def count_datapoints(self, task_id: str, teacher_id: str) -> int:
        p = self.datapoints_path(task_id, teacher_id)
        if not p.exists():
            return 0
        return sum(1 for ln in p.read_text(encoding='utf-8').splitlines() if ln.strip())

    def index_datapoints(self, task_id: str, teacher_id: str) -> dict[str, dict]:
        """Return dict keyed by datapoint id for fast lookup."""
        return {dp['id']: dp for dp in self.read_datapoints(task_id, teacher_id)}

    # ------------------------------------------------------------------
    # Phase 4 — responses
    # ------------------------------------------------------------------

    def responses_path(self, task_id: str, teacher_id: str, student_id: str) -> Path:
        return self.phase4 / f'{task_id}.{teacher_id}.{student_id}.responses.jsonl'

    def append_response(
        self, task_id: str, teacher_id: str, student_id: str, record: dict
    ) -> None:
        self._append_jsonl(self.responses_path(task_id, teacher_id, student_id), record)

    def read_responses(
        self, task_id: str, teacher_id: str, student_id: str
    ) -> list[dict]:
        return self._read_jsonl(self.responses_path(task_id, teacher_id, student_id))

    def iter_response_files(self, task_id: str, teacher_id: str):
        """Yield all response JSONL paths for a (task, teacher) pair."""
        prefix = f'{task_id}.{teacher_id}.'
        for p in sorted(self.phase4.glob(f'{prefix}*.responses.jsonl')):
            yield p

    def response_file_exists(
        self, task_id: str, teacher_id: str, student_id: str
    ) -> bool:
        return self.responses_path(task_id, teacher_id, student_id).exists()

    def get_responded_datapoint_ids(
        self, task_id: str, teacher_id: str, student_id: str
    ) -> set[str]:
        return {r['datapoint_id'] for r in self.read_responses(task_id, teacher_id, student_id)
                if r.get('status') != 'failed'}

    # ------------------------------------------------------------------
    # Phase 5 — evaluations
    # ------------------------------------------------------------------

    def evaluations_path(self, task_id: str, teacher_id: str, judge_id: str) -> Path:
        return self.phase5 / f'{task_id}.{teacher_id}.{judge_id}.evaluations.jsonl'

    def append_evaluation(
        self, task_id: str, teacher_id: str, judge_id: str, record: dict
    ) -> None:
        self._append_jsonl(self.evaluations_path(task_id, teacher_id, judge_id), record)

    def read_evaluations(
        self, task_id: str, teacher_id: str, judge_id: str
    ) -> list[dict]:
        return self._read_jsonl(self.evaluations_path(task_id, teacher_id, judge_id))

    def evaluation_file_exists(
        self, task_id: str, teacher_id: str, judge_id: str
    ) -> bool:
        return self.evaluations_path(task_id, teacher_id, judge_id).exists()

    def get_evaluated_response_ids(
        self, task_id: str, teacher_id: str, judge_id: str
    ) -> set[str]:
        return {e['response_id'] for e in self.read_evaluations(task_id, teacher_id, judge_id)
                if e.get('status') != 'failed'}

    # ------------------------------------------------------------------
    # Run-level error log
    # ------------------------------------------------------------------

    @property
    def run_errors_path(self) -> Path:
        return self.root / 'run_errors.jsonl'

    def append_run_error(self, record: dict) -> None:
        """Append a slot-level or item-level failure record to run_errors.jsonl.

        Each record must contain at minimum:
          phase (str), status='failed', error (str), timestamp (str)
        Optional fields: task, teacher, model, role.

        The file is created on first write.  The runner and validator both
        read this file to produce failure summaries without needing to scan
        all phase JSONL files.
        """
        self._append_jsonl(self.run_errors_path, {'status': 'failed', **record})

    def read_run_errors(self) -> list[dict]:
        """Return all records from run_errors.jsonl (empty list if not created yet)."""
        return self._read_jsonl(self.run_errors_path)

    # ------------------------------------------------------------------
    # Pending batch jobs  (for coeval status --fetch-batches)
    # ------------------------------------------------------------------

    @property
    def pending_batches_path(self) -> Path:
        return self.root / 'pending_batches.json'

    def add_pending_batch(
        self,
        batch_id: str,
        interface: str,
        phase: str,
        description: str,
        n_requests: int,
        id_to_key: dict[str, str],
    ) -> None:
        """Record a submitted batch job so ``coeval status`` can track it.

        Called by batch runners immediately after a batch job is created at the
        API (before polling starts), so a crash during polling still leaves a
        traceable record.

        Args:
            batch_id:    Provider-assigned batch job ID (e.g. ``"batch_abc…"``).
            interface:   ``"openai"`` or ``"anthropic"``.
            phase:       Phase that submitted the job (e.g. ``"evaluation"``).
            description: Human-readable label used as the batch job description.
            n_requests:  Number of requests in this batch.
            id_to_key:   Mapping from compact request IDs (``"r0"``, ``"r1"``, …)
                         to the caller's opaque user-keys (batch_keys).  Persisted
                         so ``status --fetch-batches`` can correlate downloaded
                         results with experiment artifacts.
        """
        data = self._read_json(self.pending_batches_path) if self.pending_batches_path.exists() else {}
        data[batch_id] = {
            'interface':   interface,
            'phase':       phase,
            'description': description,
            'submitted_at': _now_iso(),
            'n_requests':  n_requests,
            'id_to_key':   id_to_key,
            'status':      'pending',
        }
        self._write_json(self.pending_batches_path, data)

    def remove_pending_batch(self, batch_id: str) -> None:
        """Remove a completed batch job record (called after results are saved)."""
        if not self.pending_batches_path.exists():
            return
        data = self._read_json(self.pending_batches_path)
        data.pop(batch_id, None)
        if data:
            self._write_json(self.pending_batches_path, data)
        else:
            self.pending_batches_path.unlink(missing_ok=True)

    def update_pending_batch_status(self, batch_id: str, status: str) -> None:
        """Update the ``status`` field of a tracked batch job record."""
        if not self.pending_batches_path.exists():
            return
        data = self._read_json(self.pending_batches_path)
        if batch_id in data:
            data[batch_id]['status'] = status
            self._write_json(self.pending_batches_path, data)

    def read_pending_batches(self) -> dict[str, dict]:
        """Return all pending batch records keyed by batch_id."""
        if not self.pending_batches_path.exists():
            return {}
        return self._read_json(self.pending_batches_path)

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _write_json(self, path: Path, data: Any) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def _read_json(self, path: Path) -> Any:
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def _append_jsonl(self, path: Path, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

    def _read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        records = []
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
        return records
