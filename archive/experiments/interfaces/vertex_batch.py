"""Google Vertex AI Batch Prediction runner for CoEval pipeline phases.

Submits many Gemini generation requests as a single Vertex AI Batch Prediction
Job instead of making individual synchronous calls.  Benefits:
  - ~50% cost reduction (Vertex AI Batch Prediction pricing for Gemini)
  - Higher effective throughput (job-based; no per-request rate-limit pressure)
  - Consistent add()/run() interface with other CoEval batch runners

Requirements
------------
* google-cloud-aiplatform — the Vertex AI Python SDK
* A Google Cloud Storage (GCS) bucket in the **same region** as the Vertex AI
  endpoint (default ``us-central1``).
* Application Default Credentials (ADC) configured via one of:
    - ``gcloud auth application-default login``
    - ``GOOGLE_APPLICATION_CREDENTIALS`` env var pointing to a service account key
    - A service account key path in ``vertex.service_account_key`` in ``keys.yaml``

Configuration
-------------
Add to your model parameters (YAML)::

    models:
      - name: gemini-vertex
        interface: vertex
        batch_enabled: true
        parameters:
          model: gemini-2.0-flash-001
          project: my-gcp-project
          location: us-central1
          batch_gcs_bucket: gs://my-coeval-batch-bucket   # required for batch
          batch_gcs_prefix: coeval-jobs                   # optional (default: "coeval")
        roles: [student, judge]

Or store project details in ``keys.yaml``::

    providers:
      vertex:
        project: my-gcp-project
        location: us-central1
        service_account_key: /path/to/sa-key.json

Supported models
----------------
Vertex AI Batch Prediction for Gemini supports: Gemini 1.5 Flash, Gemini 1.5 Pro,
Gemini 2.0 Flash, Gemini 2.5 Flash, Gemini 2.5 Pro, and variants.
See https://cloud.google.com/vertex-ai/docs/generative-ai/batch-requests

Output matching
---------------
Vertex AI batch output files do not contain explicit record IDs.  This runner
writes a ``custom_id`` field into each input request (``"custom_id": "r0"``,
``"r1"``, …).  Vertex echoes back the full request object alongside the
response, enabling reliable key correlation.

IAM permissions required on the service account
------------------------------------------------
* ``aiplatform.batchPredictionJobs.create``
* ``aiplatform.batchPredictionJobs.get``
* ``storage.objects.create``, ``storage.objects.get`` on the GCS bucket
* ``storage.buckets.get`` on the bucket
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..logger import RunLogger

_DEFAULT_POLL_SECONDS = 60
_DEFAULT_GCS_PREFIX = 'coeval'
# Params stripped before building the generationConfig
_STRIP_PARAMS = frozenset({
    'load_in_4bit', 'load_in_8bit', 'device', 'max_new_tokens',
    'project', 'location', 'service_account_key',
    'batch_gcs_bucket', 'batch_gcs_prefix',
    'api_key',
})
# Terminal job states per Vertex AI docs
_TERMINAL_STATES = frozenset({
    'JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED',
    'JOB_STATE_PAUSED', 'JOB_STATE_EXPIRED',
})


class VertexBatchRunner:
    """Collect Gemini generation requests, submit one Vertex AI Batch Prediction
    Job, return all results.

    Interface mirrors :class:`OpenAIBatchRunner` so phase code is
    interface-agnostic.

    The GCS bucket path (``batch_gcs_bucket``) and optional prefix
    (``batch_gcs_prefix``) are captured from the first :meth:`add` call's
    ``params`` dict — they flow naturally from the model config.

    Requests that fail within the job map to ``''`` in the returned dict.
    The runner clears its internal request list after :meth:`run` completes.
    """

    def __init__(
        self,
        access_key: str | None = None,
        poll_seconds: int = _DEFAULT_POLL_SECONDS,
        project: str | None = None,
        location: str | None = None,
        service_account_key: str | None = None,
        batch_gcs_bucket: str | None = None,
        batch_gcs_prefix: str | None = None,
    ) -> None:
        # access_key is unused for Vertex (ADC / service-account auth)
        _ = access_key
        self._poll = poll_seconds
        self._project: str | None = project or os.environ.get('GOOGLE_CLOUD_PROJECT')
        self._location: str = location or os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-central1')
        self._service_account_key: str | None = (
            service_account_key or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        )
        self._gcs_bucket: str | None = batch_gcs_bucket
        self._gcs_prefix: str = batch_gcs_prefix or _DEFAULT_GCS_PREFIX
        # model name — captured from first add()
        self._model_name: str | None = None
        # request accumulator (each entry is the full API request dict)
        self._requests: list[dict] = []  # list of {custom_id, request_body}
        self._id_to_key: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add(self, key: str, prompt: str, params: dict) -> None:
        """Append one Gemini generation request to the pending batch.

        The first call captures ``batch_gcs_bucket``, ``batch_gcs_prefix``,
        ``project``, and ``location`` from ``params`` if not already set.
        """
        p = dict(params)

        # ---- Capture batch config from first add() ----
        if self._model_name is None:
            self._model_name = p.get('model')
        if not self._project:
            self._project = p.get('project') or os.environ.get('GOOGLE_CLOUD_PROJECT')
        if p.get('location') and self._location == 'us-central1':
            self._location = p['location']
        if not self._gcs_bucket:
            raw_bucket = p.get('batch_gcs_bucket', '')
            # Normalise: strip gs:// prefix (we'll add it when needed)
            self._gcs_bucket = raw_bucket.removeprefix('gs://')
        if p.get('batch_gcs_prefix') and self._gcs_prefix == _DEFAULT_GCS_PREFIX:
            self._gcs_prefix = p['batch_gcs_prefix']

        # ---- Build Vertex Gemini request body ----
        system_prompt = p.get('system_prompt')
        temperature = float(p.get('temperature', 0.7))
        max_tokens = int(p.get('max_tokens', p.get('max_new_tokens', 512)))

        contents = [{'role': 'user', 'parts': [{'text': prompt}]}]
        generation_config: dict = {
            'temperature': temperature,
            'maxOutputTokens': max_tokens,
        }

        request_body: dict = {'contents': contents, 'generationConfig': generation_config}
        if system_prompt:
            request_body['system_instruction'] = {'parts': [{'text': system_prompt}]}

        custom_id = f"r{len(self._requests)}"
        self._id_to_key[custom_id] = key
        # Embed custom_id inside the request so Vertex echoes it back
        self._requests.append({
            'custom_id': custom_id,
            'request': request_body,
        })

    def __len__(self) -> int:
        return len(self._requests)

    def clear(self) -> None:
        """Discard all pending requests without submitting them."""
        self._requests.clear()
        self._id_to_key.clear()

    def run(
        self,
        description: str = 'CoEval batch',
        logger: 'RunLogger | None' = None,
        storage=None,
        phase: str = '',
    ) -> dict[str, str]:
        """Upload requests to GCS, submit a Vertex AI Batch Prediction Job,
        poll until complete, download and parse the output.

        Returns:
            ``{user_key: response_text}`` for every request.
            Failed requests map to ``''`` (empty string).

        Raises:
            ValueError: if required configuration (GCS bucket, project) is missing.
            ImportError: if google-cloud-aiplatform is not installed.
            RuntimeError: if the batch job ends in a non-SUCCEEDED state.
        """
        if not self._requests:
            return {}

        self._validate_config()
        self._maybe_set_credentials()

        try:
            from google.cloud import aiplatform, storage as gcs_storage
        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform and google-cloud-storage are required for "
                "Vertex batch: pip install google-cloud-aiplatform google-cloud-storage"
            )

        aiplatform.init(project=self._project, location=self._location)

        def _log(msg: str) -> None:
            if logger is not None:
                logger.info(msg)

        n = len(self._requests)
        job_id = f"coeval-{int(time.time())}-{uuid.uuid4().hex[:8]}"

        # ---- 1. Upload input JSONL to GCS ----
        storage_client = gcs_storage.Client(project=self._project)
        bucket = storage_client.bucket(self._gcs_bucket)

        input_blob_name = f"{self._gcs_prefix}/input/{job_id}.jsonl"
        input_gcs_uri = f"gs://{self._gcs_bucket}/{input_blob_name}"
        output_gcs_uri = f"gs://{self._gcs_bucket}/{self._gcs_prefix}/output/{job_id}/"

        jsonl_content = '\n'.join(
            json.dumps(r, ensure_ascii=False) for r in self._requests
        )
        blob = bucket.blob(input_blob_name)
        blob.upload_from_string(jsonl_content.encode('utf-8'), content_type='application/jsonl')

        _log(
            f"Vertex Batch: uploaded {n:,} request(s) to {input_gcs_uri} "
            f"({len(jsonl_content) / 1024:.1f} KB, description={description!r})"
        )

        # ---- 2. Resolve Vertex model resource name ----
        model_name = self._model_name or ''
        # Normalise short model IDs to publisher resource name
        if not model_name.startswith('projects/') and not model_name.startswith('publishers/'):
            model_resource = f"publishers/google/models/{model_name}"
        else:
            model_resource = model_name

        # ---- 3. Create the Batch Prediction Job ----
        job = aiplatform.BatchPredictionJob.create(
            job_display_name=f"{description} — {job_id}",
            model_name=model_resource,
            instances_format='jsonl',
            predictions_format='jsonl',
            gcs_source=input_gcs_uri,
            gcs_destination_prefix=output_gcs_uri,
            sync=False,  # non-blocking; we poll manually below
        )
        job_resource_name = job.resource_name
        _log(
            f"Vertex Batch: job created (name={job_resource_name!r}), "
            f"polling every {self._poll}s ..."
        )

        # Persist for recovery
        if storage is not None:
            try:
                storage.add_pending_batch(
                    job_resource_name, 'vertex', phase, description, n,
                    dict(self._id_to_key),
                )
            except Exception:
                pass

        # ---- 4. Poll until terminal ----
        while job.state.name not in _TERMINAL_STATES:
            time.sleep(self._poll)
            job.refresh()
            _log(f"Vertex Batch: state={job.state.name!r}")

        if job.state.name != 'JOB_STATE_SUCCEEDED':
            if storage is not None:
                try:
                    storage.update_pending_batch_status(
                        job_resource_name, f'api_{job.state.name}'
                    )
                except Exception:
                    pass
            raise RuntimeError(
                f"Vertex batch job {job_resource_name} ended with state "
                f"'{job.state.name}'."
            )

        # ---- 5. List and download output files from GCS ----
        output_prefix = f"{self._gcs_prefix}/output/{job_id}/"
        _log(f"Vertex Batch: downloading output from gs://{self._gcs_bucket}/{output_prefix}")

        blobs = list(storage_client.list_blobs(self._gcs_bucket, prefix=output_prefix))
        output_blobs = [b for b in blobs if b.name.endswith('.jsonl') or b.name.endswith('.json')]

        # ---- 6. Parse output JSONL ----
        results: dict[str, str] = {}
        n_errors = 0

        for out_blob in output_blobs:
            body = out_blob.download_as_text()
            for line in body.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Retrieve custom_id from the echoed request field
                custom_id = (item.get('request') or {}).get('custom_id', '')
                user_key = self._id_to_key.get(custom_id, custom_id)

                status = item.get('status')
                if status and status != 'succeeded':
                    _log(f"Vertex Batch: request {custom_id!r} failed — status={status!r}")
                    results[user_key] = ''
                    n_errors += 1
                    continue

                response = item.get('response') or {}
                candidates = response.get('candidates') or []
                text = ''
                if candidates:
                    parts = (
                        candidates[0].get('content', {}).get('parts') or []
                    )
                    for part in parts:
                        if part.get('text'):
                            text = part['text']
                            break
                if not text and not candidates:
                    n_errors += 1
                results[user_key] = text

        n_ok = len(results) - n_errors
        _log(
            f"Vertex Batch: complete — {n_ok:,} succeeded, {n_errors:,} failed "
            f"(out of {n:,})"
        )

        # ---- 7. Clean up GCS input file (best-effort) ----
        try:
            blob.delete()
        except Exception:
            pass

        # ---- 8. Remove pending batch record ----
        if storage is not None:
            try:
                storage.remove_pending_batch(job_resource_name)
            except Exception:
                pass

        self.clear()
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Raise ValueError with actionable instructions if required config is absent."""
        missing = []
        if not self._gcs_bucket:
            missing.append(
                "  - 'batch_gcs_bucket' not set.  Add it to model parameters:\n"
                "      parameters:\n"
                "        batch_gcs_bucket: gs://my-coeval-batch-bucket"
            )
        if not self._project:
            missing.append(
                "  - GCP project not set.  Add 'project' to model parameters or\n"
                "      set the GOOGLE_CLOUD_PROJECT environment variable."
            )
        if missing:
            raise ValueError(
                "Vertex AI Batch requires additional configuration:\n"
                + '\n'.join(missing)
                + "\n\nSee docs/README/05-providers.md#google-vertex-ai for the setup guide."
            )

    def _maybe_set_credentials(self) -> None:
        """Apply service account key path to env if provided."""
        if self._service_account_key:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self._service_account_key
