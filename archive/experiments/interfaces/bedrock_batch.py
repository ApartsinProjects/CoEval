"""AWS Bedrock Model Invocation Jobs batch runner for CoEval pipeline phases.

Submits many Converse API requests as a single Bedrock Model Invocation Job
instead of making individual synchronous calls.  Benefits:
  - ~50% cost reduction (Bedrock Batch Inference pricing)
  - Higher effective throughput (job-based; no per-minute rate-limit pressure)
  - Consistent add()/run() interface with other CoEval batch runners

Requirements
------------
* boto3 — IAM authentication only; the native Bedrock API key
  (``BedrockAPIKey-...:...``) is **not** supported for the batch management API.
* An S3 bucket in the **same region** as the Bedrock endpoint.
* An IAM service role that the Bedrock service can assume to read input from S3
  and write output to S3.  Minimum permissions on the role::

      s3:GetObject, s3:PutObject, s3:ListBucket

  The role's trust policy must allow ``bedrock.amazonaws.com`` to assume it.

Configuration
-------------
Add to your model parameters (YAML)::

    models:
      - name: claude-bedrock
        interface: bedrock
        batch_enabled: true
        parameters:
          model: anthropic.claude-3-5-haiku-20241022-v1:0
          region: us-east-1
          batch_s3_bucket: my-coeval-batch-bucket   # required for batch
          batch_s3_prefix: coeval-jobs              # optional (default: "coeval")
          batch_role_arn: arn:aws:iam::123456789:role/BedrockBatchRole  # required
        roles: [student, judge]

Or store credentials and the role ARN in ``keys.yaml``::

    providers:
      bedrock:
        access_key_id: AKIA...
        secret_access_key: ...
        region: us-east-1
        batch_role_arn: arn:aws:iam::123456789:role/BedrockBatchRole

IAM setup guide
---------------
1. Create an S3 bucket in the same region as your Bedrock endpoint.
2. Create an IAM role with a trust policy for ``bedrock.amazonaws.com``::

       {
         "Effect": "Allow",
         "Principal": {"Service": "bedrock.amazonaws.com"},
         "Action": "sts:AssumeRole",
         "Condition": {
           "StringEquals": {"aws:SourceAccount": "<YOUR_ACCOUNT_ID>"}
         }
       }

3. Attach a policy granting the role access to the S3 bucket::

       s3:GetObject   on arn:aws:s3:::<bucket>/*
       s3:PutObject   on arn:aws:s3:::<bucket>/*
       s3:ListBucket  on arn:aws:s3:::<bucket>

4. Copy the role ARN (``arn:aws:iam::<account>:role/<name>``) into
   ``batch_role_arn`` in your model parameters or ``keys.yaml``.

Supported models (as of 2026-03-02)
-------------------------------------
Bedrock Batch Inference supports: Anthropic Claude models, Amazon Nova micro/lite/pro,
Meta Llama 3.x, Mistral Large, AI21 Jamba — not all models in all regions.
See https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-supported.html
"""
from __future__ import annotations

import io
import json
import os
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..logger import RunLogger

_DEFAULT_POLL_SECONDS = 60
_DEFAULT_S3_PREFIX = 'coeval'
# Params stripped from the Converse inference body
_STRIP_PARAMS = frozenset({
    'load_in_4bit', 'load_in_8bit', 'device', 'max_new_tokens',
    'region', 'batch_s3_bucket', 'batch_s3_prefix', 'batch_role_arn',
    'api_key', 'access_key_id', 'secret_access_key', 'session_token',
})
# Terminal job statuses per AWS Bedrock docs
_TERMINAL_STATUSES = frozenset({'Completed', 'Failed', 'Stopped', 'PartiallyCompleted'})


class BedrockBatchRunner:
    """Collect Converse API requests, submit one Bedrock Model Invocation Job,
    return all results.

    Interface mirrors :class:`OpenAIBatchRunner` so phase code is
    interface-agnostic: it calls ``runner.add(...)`` and ``runner.run(...)``
    regardless of provider.

    Credentials (``access_key_id``, ``secret_access_key``, etc.) and the
    S3/role configuration (``batch_s3_bucket``, ``batch_role_arn``) are
    captured from the first :meth:`add` call's ``params`` dict — they flow
    naturally from the model config's ``parameters`` block.

    Requests that fail within the job map to ``''`` in the returned dict.
    The runner clears its internal request list after :meth:`run` completes.
    """

    def __init__(
        self,
        access_key: str | None = None,
        poll_seconds: int = _DEFAULT_POLL_SECONDS,
        region: str | None = None,
        batch_role_arn: str | None = None,
        batch_s3_bucket: str | None = None,
        batch_s3_prefix: str | None = None,
    ) -> None:
        # access_key is the native Bedrock API key — NOT usable for the batch
        # management API (which requires IAM/boto3).  We accept it for API
        # consistency but do not use it; IAM credentials come from env vars,
        # ~/.aws/credentials, or the model params dict captured in add().
        _ = access_key  # acknowledged, not used for batch
        self._poll = poll_seconds
        self._region: str | None = region or os.environ.get('AWS_DEFAULT_REGION')
        self._role_arn: str | None = batch_role_arn
        self._s3_bucket: str | None = batch_s3_bucket
        self._s3_prefix: str = batch_s3_prefix or _DEFAULT_S3_PREFIX
        # IAM credentials — captured from add() params or env vars
        self._access_key_id: str | None = None
        self._secret_access_key: str | None = None
        self._session_token: str | None = None
        # model ID — must be the same for all requests in one job
        self._model_id: str | None = None
        # request accumulator
        self._requests: list[dict] = []
        self._id_to_key: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add(self, key: str, prompt: str, params: dict) -> None:
        """Append one Converse API request to the pending batch.

        The first call captures ``batch_s3_bucket``, ``batch_role_arn``,
        ``region``, and IAM credentials from ``params``, mirroring the
        pattern used by :class:`AzureBatchRunner` for ``azure_endpoint``.
        All Bedrock-specific keys are stripped before building the request
        body.
        """
        p = dict(params)

        # ---- Capture connection / batch config from first add() ----
        if self._model_id is None:
            self._model_id = p.get('model')
        if not self._region:
            self._region = (
                p.get('region')
                or os.environ.get('AWS_DEFAULT_REGION')
                or os.environ.get('AWS_REGION')
                or 'us-east-1'
            )
        if not self._s3_bucket:
            self._s3_bucket = p.get('batch_s3_bucket')
        if p.get('batch_s3_prefix') and self._s3_prefix == _DEFAULT_S3_PREFIX:
            self._s3_prefix = p['batch_s3_prefix']
        if not self._role_arn:
            self._role_arn = p.get('batch_role_arn')
        if not self._access_key_id:
            self._access_key_id = p.get('access_key_id')
        if not self._secret_access_key:
            self._secret_access_key = p.get('secret_access_key')
        if not self._session_token:
            self._session_token = p.get('session_token')

        # ---- Build Converse model input ----
        system_prompt = p.get('system_prompt')
        temperature = float(p.get('temperature', 0.7))
        max_tokens = int(p.get('max_tokens', p.get('max_new_tokens', 512)))

        model_input: dict = {
            'messages': [{'role': 'user', 'content': [{'text': prompt}]}],
            'inferenceConfig': {'temperature': temperature, 'maxTokens': max_tokens},
        }
        if system_prompt:
            model_input['system'] = [{'text': system_prompt}]

        record_id = f"r{len(self._requests)}"
        self._id_to_key[record_id] = key
        self._requests.append({'recordId': record_id, 'modelInput': model_input})

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
        """Upload requests to S3, submit a Bedrock Model Invocation Job, poll
        until complete, download and parse the output.

        Returns:
            ``{user_key: response_text}`` for every request.
            Failed requests map to ``''`` (empty string).

        Raises:
            ValueError: if required configuration (S3 bucket, role ARN) is missing.
            ImportError: if boto3 is not installed.
            RuntimeError: if the batch job ends in a non-Completed terminal state.
        """
        if not self._requests:
            return {}

        self._validate_config()

        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for Bedrock batch: pip install boto3"
            )

        def _log(msg: str) -> None:
            if logger is not None:
                logger.info(msg)

        # ---- Build boto3 session ----
        session_kwargs: dict = {'region_name': self._region}
        key_id = self._access_key_id or os.environ.get('AWS_ACCESS_KEY_ID')
        secret = self._secret_access_key or os.environ.get('AWS_SECRET_ACCESS_KEY')
        token = self._session_token or os.environ.get('AWS_SESSION_TOKEN')
        if key_id and secret:
            session_kwargs['aws_access_key_id'] = key_id
            session_kwargs['aws_secret_access_key'] = secret
            if token:
                session_kwargs['aws_session_token'] = token

        session = boto3.Session(**session_kwargs)
        bedrock = session.client('bedrock')
        s3 = session.client('s3', region_name=self._region)

        n = len(self._requests)
        job_name = f"coeval-{int(time.time())}-{uuid.uuid4().hex[:8]}"

        # ---- 1. Upload input JSONL to S3 ----
        input_key = f"{self._s3_prefix}/input/{job_name}.jsonl"
        input_s3_uri = f"s3://{self._s3_bucket}/{input_key}"
        output_s3_uri = f"s3://{self._s3_bucket}/{self._s3_prefix}/output/{job_name}/"

        jsonl_bytes = '\n'.join(
            json.dumps(r, ensure_ascii=False) for r in self._requests
        ).encode('utf-8')

        _log(
            f"Bedrock Batch: uploading {n:,} request(s) to {input_s3_uri} "
            f"({len(jsonl_bytes) / 1024:.1f} KB, description={description!r})"
        )
        s3.put_object(Bucket=self._s3_bucket, Key=input_key, Body=jsonl_bytes)

        # ---- 2. Create the Model Invocation Job ----
        response = bedrock.create_model_invocation_job(
            jobName=job_name,
            roleArn=self._role_arn,
            modelId=self._model_id,
            inputDataConfig={
                's3InputDataConfig': {
                    's3Uri': input_s3_uri,
                    's3InputFormat': 'JSONLines',
                }
            },
            outputDataConfig={
                's3OutputDataConfig': {'s3Uri': output_s3_uri}
            },
        )
        job_arn = response['jobArn']
        _log(
            f"Bedrock Batch: job created (arn={job_arn!r}), "
            f"polling every {self._poll}s ..."
        )

        # Persist for recovery via coeval status --fetch-batches
        if storage is not None:
            try:
                storage.add_pending_batch(
                    job_arn, 'bedrock', phase, description, n,
                    dict(self._id_to_key),
                )
            except Exception:
                pass

        # ---- 3. Poll until terminal ----
        while True:
            job = bedrock.get_model_invocation_job(jobIdentifier=job_arn)
            status = job['status']
            stats = job.get('statistics', {})
            counts = (
                f"{stats.get('numberOfRecordsCompleted', '?')} completed, "
                f"{stats.get('numberOfRecordsFailed', '?')} failed"
                if stats else "counts unavailable"
            )
            _log(f"Bedrock Batch: status={status!r} -- {counts}")
            if status in _TERMINAL_STATUSES:
                break
            time.sleep(self._poll)

        if status == 'Failed':
            if storage is not None:
                try:
                    storage.update_pending_batch_status(job_arn, f'api_{status}')
                except Exception:
                    pass
            failure_reason = job.get('failureMessage', 'unknown reason')
            raise RuntimeError(
                f"Bedrock batch job {job_arn} ended with status 'Failed': "
                f"{failure_reason}"
            )

        # ---- 4. List and download output files from S3 ----
        output_prefix_key = f"{self._s3_prefix}/output/{job_name}/"
        _log(f"Bedrock Batch: downloading output from s3://{self._s3_bucket}/{output_prefix_key}")

        paginator = s3.get_paginator('list_objects_v2')
        output_s3_keys: list[str] = []
        for page in paginator.paginate(Bucket=self._s3_bucket, Prefix=output_prefix_key):
            for obj in page.get('Contents', []):
                key_name: str = obj['Key']
                if key_name.endswith('.out') or key_name.endswith('.jsonl.out'):
                    output_s3_keys.append(key_name)

        if not output_s3_keys:
            # Fall back: list all objects under prefix (Bedrock may use varied paths)
            for page in paginator.paginate(Bucket=self._s3_bucket, Prefix=output_prefix_key):
                for obj in page.get('Contents', []):
                    output_s3_keys.append(obj['Key'])

        # ---- 5. Parse output JSONL ----
        results: dict[str, str] = {}
        n_errors = 0

        for s3_key in output_s3_keys:
            raw = s3.get_object(Bucket=self._s3_bucket, Key=s3_key)['Body'].read()
            body = raw.decode('utf-8')
            for line in body.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue

                record_id: str = item.get('recordId', '')
                user_key = self._id_to_key.get(record_id, record_id)

                error_info = item.get('errorInfo')
                if error_info:
                    _log(f"Bedrock Batch: record {record_id!r} failed — {error_info}")
                    results[user_key] = ''
                    n_errors += 1
                    continue

                model_output = item.get('modelOutput', {}) or {}
                content_blocks = (
                    model_output.get('output', {})
                    .get('message', {})
                    .get('content', [])
                )
                text = ''
                for block in content_blocks:
                    if block.get('text'):
                        text = block['text']
                        break
                results[user_key] = text

        n_ok = len(results) - n_errors
        _log(
            f"Bedrock Batch: complete — {n_ok:,} succeeded, {n_errors:,} failed "
            f"(out of {n:,})"
        )

        # ---- 6. Clean up S3 input file (best-effort) ----
        try:
            s3.delete_object(Bucket=self._s3_bucket, Key=input_key)
        except Exception:
            pass

        # ---- 7. Remove pending batch record ----
        if storage is not None:
            try:
                storage.remove_pending_batch(job_arn)
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
        if not self._s3_bucket:
            missing.append(
                "  - 'batch_s3_bucket' not set.  Add it to model parameters:\n"
                "      parameters:\n"
                "        batch_s3_bucket: my-coeval-batch-bucket"
            )
        if not self._role_arn:
            missing.append(
                "  - 'batch_role_arn' not set.  Add the IAM service role ARN:\n"
                "      parameters:\n"
                "        batch_role_arn: arn:aws:iam::123456789:role/BedrockBatchRole\n"
                "    (The role must trust bedrock.amazonaws.com and have S3 read/write access.)"
            )
        if missing:
            raise ValueError(
                "Bedrock Batch requires additional configuration:\n"
                + '\n'.join(missing)
                + "\n\nSee docs/README/05-providers.md#aws-bedrock for the full setup guide."
            )
