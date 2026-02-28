"""AWS Bedrock interface (REQ-10.x).

Uses the ``boto3`` SDK's ``bedrock-runtime`` Converse API, or direct HTTP with
the ``x-amzn-bedrock-key`` header for native Bedrock API keys.

Authentication
--------------
In decreasing priority:

  1. ``api_key`` — Bedrock native API key (format ``BedrockAPIKey-...:...``).
     Uses direct HTTP with the ``x-amzn-bedrock-key`` header; no boto3 needed.
  2. ``access_key_id`` / ``secret_access_key`` in ``bedrock`` block of provider
     key file.
  3. Standard AWS environment variables: ``AWS_ACCESS_KEY_ID``,
     ``AWS_SECRET_ACCESS_KEY``, ``AWS_DEFAULT_REGION``.
  4. IAM role / instance profile (boto3 credential chain).

YAML examples::

    # Native Bedrock API key (obtain from AWS console → Bedrock → API keys):
    models:
      - name: claude-bedrock
        interface: bedrock
        parameters:
          model: anthropic.claude-3-5-sonnet-20241022-v2:0
          region: us-east-1
          temperature: 0.7
          max_tokens: 512
        roles: [teacher, student, judge]

    # IAM credentials (traditional):
    models:
      - name: llama3-bedrock
        interface: bedrock
        parameters:
          model: meta.llama3-70b-instruct-v1:0
          region: us-west-2
          temperature: 0.8
          max_tokens: 1024
        roles: [teacher, student]

Batch support
-------------
AWS Bedrock Batch Inference uses S3 as input/output.  Batch jobs are submitted
via ``bedrock.create_model_invocation_job()`` with an S3 URI input.  This
requires an S3 bucket in the same region.  Configure via::

    parameters:
      batch_s3_bucket: my-coeval-batch-bucket   # required for batch mode
      batch_s3_prefix: coeval-jobs              # optional prefix

Batch is activated when ``batch_enabled: true`` is set on the model.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .base import ModelInterface

_RETRY_CODES = ('ThrottlingException', 'ServiceUnavailableException', 'RequestTimeout')
_FATAL_CODES = ('ValidationException', 'AccessDeniedException', 'ResourceNotFoundException')


class BedrockInterface(ModelInterface):
    """Text generation via AWS Bedrock Converse API with exponential-backoff retry.

    Supports two authentication modes:

    * **Native API key** — pass ``api_key`` (format ``BedrockAPIKey-...:...``).
      Makes direct HTTPS calls with the ``x-amzn-bedrock-key`` header; boto3 is
      not required.
    * **IAM credentials** — pass ``access_key_id`` / ``secret_access_key``, or
      leave empty to use the boto3 credential chain (env vars, ``~/.aws/``,
      instance profile, etc.).
    """

    def __init__(
        self,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        session_token: str | None = None,
        region: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._region = (
            region
            or os.environ.get('AWS_DEFAULT_REGION')
            or os.environ.get('AWS_REGION')
            or 'us-east-1'
        )
        self._api_key = api_key

        if api_key:
            # Native Bedrock API key — no boto3 client needed for runtime calls
            self._client = None
        else:
            # IAM auth via boto3
            try:
                import boto3
            except ImportError:
                raise ImportError(
                    "boto3 is required for the AWS Bedrock interface: pip install boto3"
                )

            session_kwargs: dict = {'region_name': self._region}
            resolved_key_id = access_key_id or os.environ.get('AWS_ACCESS_KEY_ID')
            resolved_secret = secret_access_key or os.environ.get('AWS_SECRET_ACCESS_KEY')
            resolved_token = session_token or os.environ.get('AWS_SESSION_TOKEN')

            if resolved_key_id and resolved_secret:
                session_kwargs['aws_access_key_id'] = resolved_key_id
                session_kwargs['aws_secret_access_key'] = resolved_secret
                if resolved_token:
                    session_kwargs['aws_session_token'] = resolved_token
            # If no explicit keys, boto3 uses its standard credential chain
            # (env vars, ~/.aws/credentials, instance metadata, etc.)

            session = boto3.Session(**session_kwargs)
            self._client = session.client('bedrock-runtime')

    # ------------------------------------------------------------------
    # Internal: HTTP-based Converse call (native API key path)
    # ------------------------------------------------------------------

    def _converse_http(self, model_id: str, body: dict) -> dict:
        """POST to the Bedrock Converse endpoint with the native API key header."""
        safe_model_id = urllib.parse.quote(model_id, safe='')
        url = (
            f"https://bedrock-runtime.{self._region}.amazonaws.com"
            f"/model/{safe_model_id}/converse"
        )
        payload = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(
            url=url,
            data=payload,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'x-amzn-bedrock-key': self._api_key,
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                err = json.loads(raw)
            except Exception:
                err = {'message': raw.decode('utf-8', errors='replace')}
            err_type = err.get('__type', '') or err.get('code', '')
            raise RuntimeError(
                f"Bedrock HTTP {exc.code} ({err_type}): {err.get('message', str(err))}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, prompt: str, parameters: dict) -> str:
        params = dict(parameters)
        model_id = params.pop('model')
        # Strip keys that are not Converse inference parameters
        params.pop('region', None)
        params.pop('batch_s3_bucket', None)
        params.pop('batch_s3_prefix', None)
        params.pop('api_key', None)
        system_prompt = params.pop('system_prompt', None)
        temperature = params.pop('temperature', 0.7)
        max_tokens = int(params.pop('max_tokens', params.pop('max_new_tokens', 512)))

        messages = [{'role': 'user', 'content': [{'text': prompt}]}]
        converse_body: dict = {
            'messages': messages,
            'inferenceConfig': {
                'temperature': float(temperature),
                'maxTokens': max_tokens,
            },
        }
        if system_prompt:
            converse_body['system'] = [{'text': system_prompt}]

        delay = 1.0
        for attempt in range(3):
            try:
                if self._api_key:
                    response = self._converse_http(model_id, converse_body)
                else:
                    response = self._client.converse(modelId=model_id, **converse_body)
                output = response.get('output', {}).get('message', {})
                content = output.get('content', [])
                for block in content:
                    if block.get('text'):
                        return block['text']
                return ''
            except Exception as exc:
                err_code = getattr(exc, 'response', {}).get('Error', {}).get('Code', '')
                msg = str(exc)
                is_fatal = (
                    err_code in _FATAL_CODES
                    or any(f'HTTP {c}' in msg for c in ('400', '403', '404'))
                )
                if is_fatal:
                    raise
                is_retry = (
                    err_code in _RETRY_CODES
                    or 'ThrottlingException' in msg
                    or 'rate' in msg.lower()
                    or 'HTTP 429' in msg
                    or 'HTTP 503' in msg
                )
                if attempt < 2 and is_retry:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        raise RuntimeError('Bedrock generate failed after 3 attempts')
