"""Google Vertex AI interface (REQ-10.x).

Uses ``vertexai.generative_models.GenerativeModel`` to call Gemini models
hosted on Google Cloud Vertex AI.  Vertex AI Gemini offers the same models
as Google AI Studio but with enterprise-grade SLAs, VPC Service Controls,
CMEK, and access to Batch Prediction.

Authentication
--------------
In decreasing priority:
  1. ``service_account_key`` path in ``vertex`` block of provider key file
     (sets ``GOOGLE_APPLICATION_CREDENTIALS`` before initialising the SDK)
  2. ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable
  3. Application Default Credentials (``gcloud auth application-default login``)

Also required:
  - ``project`` parameter or ``GOOGLE_CLOUD_PROJECT`` env var
  - ``location`` parameter or ``GOOGLE_CLOUD_LOCATION`` env var (default ``us-central1``)

YAML example::

    models:
      - name: gemini-vertex
        interface: vertex
        parameters:
          model: gemini-1.5-pro
          project: my-gcp-project
          location: us-central1
          temperature: 0.7
          max_tokens: 512
        roles: [teacher, student, judge]

Batch support
-------------
Vertex AI Batch Prediction for Gemini accepts a Cloud Storage (GCS) JSONL input
and writes output to GCS.  Configure via::

    parameters:
      batch_gcs_bucket: gs://my-coeval-batch-bucket
      batch_gcs_prefix: coeval-jobs

Batch is activated when ``batch_enabled: true`` is set on the model.
"""
from __future__ import annotations

import os
import time

from .base import ModelInterface

_RETRY_ERRORS = ('quota', 'rate', 'resource_exhausted', 'unavailable', '503', '429')
_FATAL_ERRORS = ('permission_denied', 'unauthenticated', 'invalid_argument', '403', '401')


class VertexInterface(ModelInterface):
    """Text generation via Google Vertex AI Gemini with exponential-backoff retry."""

    def __init__(
        self,
        project: str | None = None,
        location: str | None = None,
        service_account_key: str | None = None,
    ) -> None:
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel  # noqa: F401 (verify import)
        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform is required for the Vertex AI interface: "
                "pip install google-cloud-aiplatform"
            )

        resolved_project = (
            project
            or os.environ.get('GOOGLE_CLOUD_PROJECT')
            or os.environ.get('GCLOUD_PROJECT')
        )
        resolved_location = (
            location
            or os.environ.get('GOOGLE_CLOUD_LOCATION')
            or 'us-central1'
        )
        resolved_sa_key = service_account_key or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

        if not resolved_project:
            raise ValueError(
                "Google Cloud project not found.  Set GOOGLE_CLOUD_PROJECT, "
                "add 'project' to model parameters, or define "
                "'vertex.project' in your provider key file."
            )

        if resolved_sa_key:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = resolved_sa_key

        vertexai.init(project=resolved_project, location=resolved_location)
        self._project = resolved_project
        self._location = resolved_location

    def generate(self, prompt: str, parameters: dict) -> str:
        from vertexai.generative_models import GenerationConfig, GenerativeModel

        params = dict(parameters)
        model_id = params.pop('model')
        params.pop('project', None)
        params.pop('location', None)
        params.pop('service_account_key', None)
        params.pop('batch_gcs_bucket', None)
        params.pop('batch_gcs_prefix', None)
        system_prompt = params.pop('system_prompt', None)
        temperature = float(params.pop('temperature', 0.7))
        max_tokens = int(params.pop('max_tokens', params.pop('max_new_tokens', 512)))

        model = GenerativeModel(
            model_name=model_id,
            system_instruction=system_prompt if system_prompt else None,
        )
        gen_config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        delay = 1.0
        for attempt in range(3):
            try:
                response = model.generate_content(prompt, generation_config=gen_config)
                return response.text or ''
            except Exception as exc:
                msg = str(exc).lower()
                if any(e in msg for e in _FATAL_ERRORS):
                    raise
                if attempt < 2 and any(e in msg for e in _RETRY_ERRORS):
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        raise RuntimeError('Vertex AI generate failed after 3 attempts')
