"""Comprehensive tests for BedrockBatchRunner, VertexBatchRunner, and the
create_batch_runner() factory function.

Coverage:
  - BedrockBatchRunner: add(), len(), clear(), _validate_config(), run()
  - VertexBatchRunner: add(), len(), clear(), _validate_config(), run()
  - create_batch_runner(): factory for all supported interfaces
"""
from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_bedrock_output_line(record_id: str, text: str) -> str:
    """Build one output JSONL line in Bedrock Model Invocation Job format."""
    return json.dumps({
        "recordId": record_id,
        "modelOutput": {
            "output": {
                "message": {
                    "content": [{"text": text}]
                }
            }
        }
    })


def _make_bedrock_error_line(record_id: str, reason: str = "throttled") -> str:
    """Build one failed-record JSONL line in Bedrock output format."""
    return json.dumps({
        "recordId": record_id,
        "errorInfo": {"errorCode": "ThrottlingException", "errorMessage": reason}
    })


def _make_vertex_output_line(custom_id: str, text: str, status: str = "succeeded") -> str:
    """Build one output JSONL line in Vertex AI Batch Prediction format."""
    return json.dumps({
        "request": {"custom_id": custom_id},
        "response": {
            "candidates": [
                {"content": {"parts": [{"text": text}]}}
            ]
        },
        "status": status
    })


def _make_vertex_failed_line(custom_id: str) -> str:
    """Build one failed-request JSONL line in Vertex AI Batch Prediction format."""
    return json.dumps({
        "request": {"custom_id": custom_id},
        "response": {},
        "status": "failed"
    })

# ---------------------------------------------------------------------------
# Fixtures: boto3 mock
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_boto3(monkeypatch: pytest.MonkeyPatch):
    """Patch sys.modules so that import boto3 inside the runner returns a MagicMock."""
    mock = MagicMock()
    with patch.dict(sys.modules, {"boto3": mock}):
        yield mock


# ---------------------------------------------------------------------------
# Fixtures: Google Cloud mocks
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_gcloud():
    """Patch sys.modules so that Google Cloud imports return MagicMocks."""
    mock_aip = MagicMock()
    mock_gcs = MagicMock()
    google_mock = MagicMock()
    google_cloud_mock = MagicMock()
    with patch.dict(sys.modules, {
        "google": google_mock,
        "google.cloud": google_cloud_mock,
        "google.cloud.aiplatform": mock_aip,
        "google.cloud.storage": mock_gcs,
    }):
        yield mock_aip, mock_gcs

# ---------------------------------------------------------------------------
# Helper: build a runner instance without hitting real libraries
# ---------------------------------------------------------------------------

def _bedrock_runner(**kwargs):
    """Return a fresh BedrockBatchRunner with a short poll interval."""
    from runner.interfaces.bedrock_batch import BedrockBatchRunner
    return BedrockBatchRunner(poll_seconds=0, **kwargs)


def _vertex_runner(**kwargs):
    """Return a fresh VertexBatchRunner with a short poll interval."""
    from runner.interfaces.vertex_batch import VertexBatchRunner
    return VertexBatchRunner(poll_seconds=0, **kwargs)


# ===========================================================================
# BedrockBatchRunner -- add()
# ===========================================================================

class TestBedrockAdd:
    """Tests for BedrockBatchRunner.add()."""

    def test_add_captures_model_id(self):
        runner = _bedrock_runner()
        runner.add("k1", "Hello", {"model": "anthropic.claude-3-haiku", "batch_s3_bucket": "b", "batch_role_arn": "arn:x"})
        assert runner._model_id == "anthropic.claude-3-haiku"

    def test_add_captures_region_from_params(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        runner = _bedrock_runner()
        runner.add("k1", "Hi", {"model": "m", "region": "eu-west-1", "batch_s3_bucket": "b", "batch_role_arn": "r"})
        assert runner._region == "eu-west-1"

    def test_add_captures_s3_bucket(self):
        runner = _bedrock_runner()
        runner.add("k1", "Hi", {"model": "m", "batch_s3_bucket": "my-bucket", "batch_role_arn": "r"})
        assert runner._s3_bucket == "my-bucket"

    def test_add_captures_role_arn(self):
        runner = _bedrock_runner()
        runner.add("k1", "Hi", {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "arn:aws:iam::123:role/R"})
        assert runner._role_arn == "arn:aws:iam::123:role/R"

    def test_add_captures_iam_credentials(self):
        runner = _bedrock_runner()
        runner.add("k1", "Hi", {
            "model": "m",
            "batch_s3_bucket": "b",
            "batch_role_arn": "r",
            "access_key_id": "AKIAIOSFODNN7",
            "secret_access_key": "wJalrXUtnFEMI",
            "session_token": "tok123",
        })
        assert runner._access_key_id == "AKIAIOSFODNN7"
        assert runner._secret_access_key == "wJalrXUtnFEMI"
        assert runner._session_token == "tok123"

    def test_add_builds_correct_converse_messages(self):
        runner = _bedrock_runner()
        runner.add("k1", "What is 2+2?", {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"})
        req = runner._requests[0]
        assert req["modelInput"]["messages"] == [
            {"role": "user", "content": [{"text": "What is 2+2?"}]}
        ]

    def test_add_builds_inference_config(self):
        runner = _bedrock_runner()
        runner.add("k1", "p", {
            "model": "m",
            "batch_s3_bucket": "b",
            "batch_role_arn": "r",
            "temperature": 0.5,
            "max_tokens": 256,
        })
        ic = runner._requests[0]["modelInput"]["inferenceConfig"]
        assert ic["temperature"] == 0.5
        assert ic["maxTokens"] == 256

    def test_add_includes_system_prompt_when_provided(self):
        runner = _bedrock_runner()
        runner.add("k1", "p", {
            "model": "m",
            "batch_s3_bucket": "b",
            "batch_role_arn": "r",
            "system_prompt": "You are helpful.",
        })
        model_input = runner._requests[0]["modelInput"]
        assert "system" in model_input
        assert model_input["system"] == [{"text": "You are helpful."}]

    def test_add_omits_system_when_not_provided(self):
        runner = _bedrock_runner()
        runner.add("k1", "p", {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"})
        assert "system" not in runner._requests[0]["modelInput"]

    def test_add_assigns_sequential_record_ids(self):
        runner = _bedrock_runner()
        params = {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"}
        runner.add("key_a", "prompt a", params)
        runner.add("key_b", "prompt b", params)
        runner.add("key_c", "prompt c", params)
        assert runner._requests[0]["recordId"] == "r0"
        assert runner._requests[1]["recordId"] == "r1"
        assert runner._requests[2]["recordId"] == "r2"

    def test_add_maps_record_ids_to_user_keys(self):
        runner = _bedrock_runner()
        params = {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"}
        runner.add("my-key", "hello", params)
        assert runner._id_to_key["r0"] == "my-key"

    def test_add_custom_s3_prefix(self):
        runner = _bedrock_runner()
        runner.add("k", "p", {
            "model": "m",
            "batch_s3_bucket": "b",
            "batch_role_arn": "r",
            "batch_s3_prefix": "experiments/phase1",
        })
        assert runner._s3_prefix == "experiments/phase1"

    def test_add_model_id_captured_only_from_first_call(self):
        runner = _bedrock_runner()
        params = {"model": "first-model", "batch_s3_bucket": "b", "batch_role_arn": "r"}
        runner.add("k1", "p1", params)
        runner.add("k2", "p2", {**params, "model": "second-model"})
        assert runner._model_id == "first-model"


# ===========================================================================
# BedrockBatchRunner -- len() and clear()
# ===========================================================================

class TestBedrockLenClear:
    """Tests for BedrockBatchRunner.__len__() and .clear()."""

    def test_len_zero_initially(self):
        runner = _bedrock_runner()
        assert len(runner) == 0

    def test_len_increments_on_add(self):
        runner = _bedrock_runner()
        params = {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"}
        runner.add("k1", "p1", params)
        runner.add("k2", "p2", params)
        assert len(runner) == 2

    def test_clear_resets_len(self):
        runner = _bedrock_runner()
        params = {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"}
        runner.add("k1", "p1", params)
        runner.add("k2", "p2", params)
        runner.clear()
        assert len(runner) == 0

    def test_clear_empties_id_map(self):
        runner = _bedrock_runner()
        runner.add("k1", "p1", {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"})
        runner.clear()
        assert runner._id_to_key == {}

    def test_clear_empties_requests_list(self):
        runner = _bedrock_runner()
        runner.add("k1", "p1", {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"})
        runner.clear()
        assert runner._requests == []


# ===========================================================================
# BedrockBatchRunner -- _validate_config()
# ===========================================================================

class TestBedrockValidateConfig:
    """Tests for BedrockBatchRunner._validate_config()."""

    def test_raises_if_s3_bucket_missing(self):
        runner = _bedrock_runner(batch_role_arn="arn:aws:iam::123:role/R")
        with pytest.raises(ValueError, match="batch_s3_bucket"):
            runner._validate_config()

    def test_raises_if_role_arn_missing(self):
        runner = _bedrock_runner(batch_s3_bucket="my-bucket")
        with pytest.raises(ValueError, match="batch_role_arn"):
            runner._validate_config()

    def test_raises_both_messages_when_both_missing(self):
        runner = _bedrock_runner()
        with pytest.raises(ValueError) as exc_info:
            runner._validate_config()
        msg = str(exc_info.value)
        assert "batch_s3_bucket" in msg
        assert "batch_role_arn" in msg

    def test_passes_when_both_configured(self):
        runner = _bedrock_runner(batch_s3_bucket="b", batch_role_arn="r")
        runner._validate_config()  # should not raise

    def test_raises_value_error_type(self):
        runner = _bedrock_runner()
        with pytest.raises(ValueError):
            runner._validate_config()


# ===========================================================================
# BedrockBatchRunner -- run()
# ===========================================================================

class TestBedrockRun:
    """Tests for BedrockBatchRunner.run()."""

    def test_run_returns_empty_dict_when_no_requests(self):
        runner = _bedrock_runner()
        assert runner.run() == {}

    def test_run_raises_import_error_without_boto3(self, monkeypatch):
        runner = _bedrock_runner(batch_s3_bucket="b", batch_role_arn="r")
        runner.add("k1", "hello", {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"})
        with patch.dict(sys.modules, {"boto3": None}):
            with pytest.raises(ImportError, match="boto3"):
                runner.run()

    def _build_full_mock_boto3(self, output_lines):
        """Construct a fully-wired boto3 MagicMock for a successful job flow."""
        mock_b3 = MagicMock()
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}
        output_body = ("\n".join(output_lines)).encode("utf-8")
        mock_body = MagicMock()
        mock_body.read.return_value = output_body
        mock_s3.get_object.return_value = {"Body": mock_body}
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": "coeval/output/job/output.jsonl.out"}]}
        ]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_bedrock = MagicMock()
        mock_bedrock.create_model_invocation_job.return_value = {
            "jobArn": "arn:aws:bedrock:us-east-1::batch/job123"
        }
        mock_bedrock.get_model_invocation_job.return_value = {
            "status": "Completed",
            "statistics": {
                "numberOfRecordsCompleted": len(output_lines),
                "numberOfRecordsFailed": 0,
            },
        }
        mock_session = MagicMock()
        mock_session.client.side_effect = (
            lambda svc, **kw: mock_s3 if svc == "s3" else mock_bedrock
        )
        mock_b3.Session.return_value = mock_session
        return mock_b3

    def test_run_full_flow_returns_results(self):
        output_lines = [
            _make_bedrock_output_line("r0", "Hello world"),
            _make_bedrock_output_line("r1", "Goodbye world"),
        ]
        mock_b3 = self._build_full_mock_boto3(output_lines)
        with patch.dict(sys.modules, {"boto3": mock_b3}):
            runner = _bedrock_runner(batch_s3_bucket="my-bucket", batch_role_arn="arn:r")
            params = {
                "model": "anthropic.claude-3-haiku",
                "batch_s3_bucket": "my-bucket",
                "batch_role_arn": "arn:r",
            }
            runner.add("user-key-0", "prompt 0", params)
            runner.add("user-key-1", "prompt 1", params)
            results = runner.run()
        del mock_b3
        assert results["user-key-0"] == "Hello world"
        assert results["user-key-1"] == "Goodbye world"

    def test_run_maps_failed_records_to_empty_string(self):
        output_lines = [
            _make_bedrock_output_line("r0", "OK"),
            _make_bedrock_error_line("r1", "ThrottlingException"),
        ]
        mock_b3 = self._build_full_mock_boto3(output_lines)
        with patch.dict(sys.modules, {"boto3": mock_b3}):
            runner = _bedrock_runner(batch_s3_bucket="b", batch_role_arn="r")
            params = {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"}
            runner.add("k0", "p0", params)
            runner.add("k1", "p1", params)
            results = runner.run()
        del mock_b3
        assert results["k0"] == "OK"
        assert results["k1"] == ""

    def test_run_calls_clear_after_completion(self):
        output_lines = [_make_bedrock_output_line("r0", "hi")]
        mock_b3 = self._build_full_mock_boto3(output_lines)
        with patch.dict(sys.modules, {"boto3": mock_b3}):
            runner = _bedrock_runner(batch_s3_bucket="b", batch_role_arn="r")
            runner.add("k0", "p0", {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"})
            runner.run()
        del mock_b3
        assert len(runner) == 0

    def test_run_raises_runtime_error_on_failed_job(self):
        mock_b3 = MagicMock()
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}
        mock_s3.get_paginator.return_value = MagicMock()
        mock_bedrock = MagicMock()
        mock_bedrock.create_model_invocation_job.return_value = {"jobArn": "arn:fail"}
        mock_bedrock.get_model_invocation_job.return_value = {
            "status": "Failed",
            "failureMessage": "Internal server error",
        }
        mock_session = MagicMock()
        mock_session.client.side_effect = (
            lambda svc, **kw: mock_s3 if svc == "s3" else mock_bedrock
        )
        mock_b3.Session.return_value = mock_session
        with patch.dict(sys.modules, {"boto3": mock_b3}):
            runner = _bedrock_runner(batch_s3_bucket="b", batch_role_arn="r")
            runner.add("k0", "p0", {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"})
            with pytest.raises(RuntimeError, match="Failed"):
                runner.run()

    def test_run_uploads_input_jsonl_to_s3(self):
        output_lines = [_make_bedrock_output_line("r0", "hi")]
        mock_b3 = self._build_full_mock_boto3(output_lines)
        with patch.dict(sys.modules, {"boto3": mock_b3}):
            runner = _bedrock_runner(batch_s3_bucket="test-bucket", batch_role_arn="r")
            runner.add("k0", "hello there", {
                "model": "m",
                "batch_s3_bucket": "test-bucket",
                "batch_role_arn": "r",
            })
            runner.run()
        mock_session = mock_b3.Session.return_value
        mock_s3 = mock_session.client.return_value
        assert mock_s3.put_object.called
        call_args = mock_s3.put_object.call_args
        assert call_args.kwargs.get("Bucket") == "test-bucket"

    def test_run_creates_model_invocation_job(self):
        output_lines = [_make_bedrock_output_line("r0", "hi")]
        mock_b3 = self._build_full_mock_boto3(output_lines)
        with patch.dict(sys.modules, {"boto3": mock_b3}):
            runner = _bedrock_runner(batch_s3_bucket="b", batch_role_arn="arn:aws:iam::123:role/R")
            runner.add("k0", "p0", {
                "model": "anthropic.claude",
                "batch_s3_bucket": "b",
                "batch_role_arn": "arn:aws:iam::123:role/R",
            })
            runner.run()
        mock_session = mock_b3.Session.return_value
        mock_bedrock = mock_session.client.return_value
        assert mock_bedrock.create_model_invocation_job.called

    def test_run_uses_iam_creds_from_add_params(self):
        output_lines = [_make_bedrock_output_line("r0", "result")]
        mock_b3 = self._build_full_mock_boto3(output_lines)
        with patch.dict(sys.modules, {"boto3": mock_b3}):
            runner = _bedrock_runner(batch_s3_bucket="b", batch_role_arn="r")
            runner.add("k0", "p0", {
                "model": "m",
                "batch_s3_bucket": "b",
                "batch_role_arn": "r",
                "access_key_id": "AKIATEST",
                "secret_access_key": "secretkey",
            })
            runner.run()
        session_call_kwargs = mock_b3.Session.call_args.kwargs
        assert session_call_kwargs.get("aws_access_key_id") == "AKIATEST"
        assert session_call_kwargs.get("aws_secret_access_key") == "secretkey"

    def test_run_polls_until_terminal_status(self):
        output_lines = [_make_bedrock_output_line("r0", "done")]
        mock_b3 = MagicMock()
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}
        mock_body = MagicMock()
        mock_body.read.return_value = ("\n".join(output_lines)).encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "out.jsonl.out"}]}]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_bedrock = MagicMock()
        mock_bedrock.create_model_invocation_job.return_value = {"jobArn": "arn:x"}
        mock_bedrock.get_model_invocation_job.side_effect = [
            {"status": "InProgress"},
            {"status": "InProgress"},
            {"status": "Completed", "statistics": {"numberOfRecordsCompleted": 1}},
        ]
        mock_session = MagicMock()
        mock_session.client.side_effect = (
            lambda svc, **kw: mock_s3 if svc == "s3" else mock_bedrock
        )
        mock_b3.Session.return_value = mock_session
        with patch.dict(sys.modules, {"boto3": mock_b3}):
            runner = _bedrock_runner(batch_s3_bucket="b", batch_role_arn="r")
            runner.add("k0", "p0", {"model": "m", "batch_s3_bucket": "b", "batch_role_arn": "r"})
            results = runner.run()
        assert mock_bedrock.get_model_invocation_job.call_count == 3
        assert results["k0"] == "done"

    def test_run_passes_role_arn_to_create_job(self):
        output_lines = [_make_bedrock_output_line("r0", "text")]
        mock_b3 = self._build_full_mock_boto3(output_lines)
        with patch.dict(sys.modules, {"boto3": mock_b3}):
            runner = _bedrock_runner(
                batch_s3_bucket="b", batch_role_arn="arn:aws:iam::999:role/MyRole"
            )
            runner.add("k0", "p0", {
                "model": "m",
                "batch_s3_bucket": "b",
                "batch_role_arn": "arn:aws:iam::999:role/MyRole",
            })
            runner.run()
        mock_session = mock_b3.Session.return_value
        mock_bedrock = mock_session.client.return_value
        create_kwargs = mock_bedrock.create_model_invocation_job.call_args.kwargs
        assert create_kwargs.get("roleArn") == "arn:aws:iam::999:role/MyRole"


# ===========================================================================
# VertexBatchRunner -- add()
# ===========================================================================

class TestVertexAdd:
    """Tests for VertexBatchRunner.add()."""

    def test_add_captures_model_name(self):
        runner = _vertex_runner()
        runner.add("k1", "hello", {
            "model": "gemini-2.0-flash-001",
            "batch_gcs_bucket": "gs://b",
            "project": "p",
        })
        assert runner._model_name == "gemini-2.0-flash-001"

    def test_add_captures_project(self):
        runner = _vertex_runner()
        runner.add("k1", "hi", {"model": "m", "batch_gcs_bucket": "gs://b", "project": "my-project"})
        assert runner._project == "my-project"

    def test_add_captures_location(self):
        runner = _vertex_runner()
        runner.add("k1", "hi", {
            "model": "m",
            "batch_gcs_bucket": "gs://b",
            "project": "p",
            "location": "europe-west4",
        })
        assert runner._location == "europe-west4"

    def test_add_strips_gs_prefix_from_bucket(self):
        runner = _vertex_runner()
        runner.add("k1", "hi", {"model": "m", "batch_gcs_bucket": "gs://my-bucket", "project": "p"})
        assert runner._gcs_bucket == "my-bucket"

    def test_add_handles_bucket_without_gs_prefix(self):
        runner = _vertex_runner()
        runner.add("k1", "hi", {"model": "m", "batch_gcs_bucket": "my-bucket", "project": "p"})
        assert runner._gcs_bucket == "my-bucket"

    def test_add_builds_correct_contents(self):
        runner = _vertex_runner()
        runner.add("k1", "Tell me a joke", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
        req_body = runner._requests[0]["request"]
        assert req_body["contents"] == [
            {"role": "user", "parts": [{"text": "Tell me a joke"}]}
        ]

    def test_add_builds_generation_config(self):
        runner = _vertex_runner()
        runner.add("k1", "p", {
            "model": "m",
            "batch_gcs_bucket": "b",
            "project": "proj",
            "temperature": 0.3,
            "max_tokens": 1024,
        })
        gc = runner._requests[0]["request"]["generationConfig"]
        assert gc["temperature"] == 0.3
        assert gc["maxOutputTokens"] == 1024

    def test_add_embeds_custom_id(self):
        runner = _vertex_runner()
        runner.add("my-key", "prompt", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
        assert runner._requests[0]["custom_id"] == "r0"

    def test_add_sequential_custom_ids(self):
        runner = _vertex_runner()
        params = {"model": "m", "batch_gcs_bucket": "b", "project": "p"}
        runner.add("k0", "p0", params)
        runner.add("k1", "p1", params)
        runner.add("k2", "p2", params)
        assert [r["custom_id"] for r in runner._requests] == ["r0", "r1", "r2"]

    def test_add_maps_custom_id_to_user_key(self):
        runner = _vertex_runner()
        runner.add("user-key-xyz", "prompt", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
        assert runner._id_to_key["r0"] == "user-key-xyz"

    def test_add_system_instruction_when_system_prompt_present(self):
        runner = _vertex_runner()
        runner.add("k1", "Hello", {
            "model": "m",
            "batch_gcs_bucket": "b",
            "project": "p",
            "system_prompt": "You are a helpful assistant.",
        })
        req_body = runner._requests[0]["request"]
        assert "system_instruction" in req_body
        assert req_body["system_instruction"] == {
            "parts": [{"text": "You are a helpful assistant."}]
        }

    def test_add_no_system_instruction_when_absent(self):
        runner = _vertex_runner()
        runner.add("k1", "Hello", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
        req_body = runner._requests[0]["request"]
        assert "system_instruction" not in req_body

    def test_add_captures_gcs_prefix(self):
        runner = _vertex_runner()
        runner.add("k1", "hi", {
            "model": "m",
            "batch_gcs_bucket": "b",
            "project": "p",
            "batch_gcs_prefix": "runs/phase2",
        })
        assert runner._gcs_prefix == "runs/phase2"

    def test_add_model_name_captured_only_from_first_call(self):
        runner = _vertex_runner()
        params = {"model": "first-model", "batch_gcs_bucket": "b", "project": "p"}
        runner.add("k1", "p1", params)
        runner.add("k2", "p2", {**params, "model": "second-model"})
        assert runner._model_name == "first-model"


# ===========================================================================
# VertexBatchRunner -- len() and clear()
# ===========================================================================

class TestVertexLenClear:
    """Tests for VertexBatchRunner.__len__() and .clear()."""

    def test_len_zero_initially(self):
        runner = _vertex_runner()
        assert len(runner) == 0

    def test_len_increments_on_add(self):
        runner = _vertex_runner()
        params = {"model": "m", "batch_gcs_bucket": "b", "project": "p"}
        runner.add("k0", "p0", params)
        runner.add("k1", "p1", params)
        assert len(runner) == 2

    def test_clear_resets_len(self):
        runner = _vertex_runner()
        runner.add("k0", "p0", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
        runner.clear()
        assert len(runner) == 0

    def test_clear_empties_id_map(self):
        runner = _vertex_runner()
        runner.add("k0", "p0", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
        runner.clear()
        assert runner._id_to_key == {}

    def test_clear_empties_requests_list(self):
        runner = _vertex_runner()
        runner.add("k0", "p0", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
        runner.clear()
        assert runner._requests == []


# ===========================================================================
# VertexBatchRunner -- _validate_config()
# ===========================================================================

class TestVertexValidateConfig:
    """Tests for VertexBatchRunner._validate_config()."""

    def test_raises_if_gcs_bucket_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        runner = _vertex_runner(project="my-proj")
        with pytest.raises(ValueError, match="batch_gcs_bucket"):
            runner._validate_config()

    def test_raises_if_project_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        runner = _vertex_runner(batch_gcs_bucket="my-bucket")
        with pytest.raises(ValueError, match="project"):
            runner._validate_config()

    def test_raises_both_messages_when_both_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        runner = _vertex_runner()
        with pytest.raises(ValueError) as exc_info:
            runner._validate_config()
        msg = str(exc_info.value)
        assert "batch_gcs_bucket" in msg
        assert "project" in msg

    def test_passes_when_both_configured(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        runner = _vertex_runner(batch_gcs_bucket="my-bucket", project="my-proj")
        runner._validate_config()

    def test_raises_value_error_type(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        runner = _vertex_runner()
        with pytest.raises(ValueError):
            runner._validate_config()


# ===========================================================================
# VertexBatchRunner -- run()
# ===========================================================================

class TestVertexRun:
    """Tests for VertexBatchRunner.run()."""

    def test_run_returns_empty_dict_when_no_requests(self):
        runner = _vertex_runner()
        assert runner.run() == {}

    def test_run_raises_import_error_without_google_cloud_aiplatform(self):
        runner = _vertex_runner(batch_gcs_bucket="b", project="p")
        runner.add("k1", "hello", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
        with patch.dict(sys.modules, {
            "google": None,
            "google.cloud": None,
            "google.cloud.aiplatform": None,
            "google.cloud.storage": None,
        }):
            with pytest.raises(ImportError, match="google-cloud-aiplatform"):
                runner.run()

    def _build_vertex_mocks(self, output_lines: list):
        """Return (mock_aip, mock_gcs) wired for a successful batch job."""
        mock_aip = MagicMock()
        mock_gcs = MagicMock()
        mock_input_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_input_blob
        mock_storage_client = MagicMock()
        mock_storage_client.bucket.return_value = mock_bucket
        mock_output_blob = MagicMock()
        mock_output_blob.name = "coeval/output/job/predictions.jsonl"
        mock_output_blob.download_as_text.return_value = "\n".join(output_lines)
        mock_storage_client.list_blobs.return_value = [mock_output_blob]
        mock_gcs.Client.return_value = mock_storage_client
        mock_job = MagicMock()
        mock_job.resource_name = "projects/p/locations/us-central1/batchPredictionJobs/123"
        mock_job.state.name = "JOB_STATE_SUCCEEDED"
        mock_aip.BatchPredictionJob.create.return_value = mock_job
        return mock_aip, mock_gcs

    def test_run_full_flow_returns_results(self):
        output_lines = [
            _make_vertex_output_line("r0", "Hello world"),
            _make_vertex_output_line("r1", "Goodbye world"),
        ]
        mock_aip, mock_gcs = self._build_vertex_mocks(output_lines)
        with patch.dict(sys.modules, {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_aip,
            "google.cloud.storage": mock_gcs,
        }):
            runner = _vertex_runner(batch_gcs_bucket="gs://b", project="my-proj")
            params = {"model": "gemini-2.0-flash", "batch_gcs_bucket": "gs://b", "project": "my-proj"}
            runner.add("key-0", "prompt 0", params)
            runner.add("key-1", "prompt 1", params)
            results = runner.run()
        del mock_aip, mock_gcs
        assert results["key-0"] == "Hello world"
        assert results["key-1"] == "Goodbye world"

    def test_run_correlates_results_via_custom_id(self):
        output_lines = [_make_vertex_output_line("r0", "text for r0")]
        mock_aip, mock_gcs = self._build_vertex_mocks(output_lines)
        with patch.dict(sys.modules, {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_aip,
            "google.cloud.storage": mock_gcs,
        }):
            runner = _vertex_runner(batch_gcs_bucket="b", project="p")
            runner.add("my-special-key", "some prompt", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
            results = runner.run()
        del mock_aip, mock_gcs
        assert "my-special-key" in results
        assert results["my-special-key"] == "text for r0"

    def test_run_handles_failed_requests(self):
        output_lines = [
            _make_vertex_output_line("r0", "OK"),
            _make_vertex_failed_line("r1"),
        ]
        mock_aip, mock_gcs = self._build_vertex_mocks(output_lines)
        with patch.dict(sys.modules, {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_aip,
            "google.cloud.storage": mock_gcs,
        }):
            runner = _vertex_runner(batch_gcs_bucket="b", project="p")
            params = {"model": "m", "batch_gcs_bucket": "b", "project": "p"}
            runner.add("k0", "p0", params)
            runner.add("k1", "p1", params)
            results = runner.run()
        del mock_aip, mock_gcs
        assert results["k0"] == "OK"
        assert results["k1"] == ""

    def test_run_calls_clear_after_completion(self):
        output_lines = [_make_vertex_output_line("r0", "hi")]
        mock_aip, mock_gcs = self._build_vertex_mocks(output_lines)
        with patch.dict(sys.modules, {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_aip,
            "google.cloud.storage": mock_gcs,
        }):
            runner = _vertex_runner(batch_gcs_bucket="b", project="p")
            runner.add("k0", "p0", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
            runner.run()
        del mock_aip, mock_gcs
        assert len(runner) == 0

    def test_run_raises_runtime_error_on_failed_state(self):
        mock_aip = MagicMock()
        mock_gcs = MagicMock()
        mock_storage_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = MagicMock()
        mock_storage_client.bucket.return_value = mock_bucket
        mock_gcs.Client.return_value = mock_storage_client
        mock_job = MagicMock()
        mock_job.resource_name = "projects/p/batchJobs/fail123"
        mock_job.state.name = "JOB_STATE_FAILED"
        mock_aip.BatchPredictionJob.create.return_value = mock_job
        with patch.dict(sys.modules, {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_aip,
            "google.cloud.storage": mock_gcs,
        }):
            runner = _vertex_runner(batch_gcs_bucket="b", project="p")
            runner.add("k0", "p0", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
            with pytest.raises(RuntimeError, match="JOB_STATE_FAILED"):
                runner.run()

    def test_run_uploads_input_to_gcs(self):
        output_lines = [_make_vertex_output_line("r0", "result")]
        mock_aip, mock_gcs = self._build_vertex_mocks(output_lines)
        with patch.dict(sys.modules, {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_aip,
            "google.cloud.storage": mock_gcs,
        }):
            runner = _vertex_runner(batch_gcs_bucket="my-bucket", project="p")
            runner.add("k0", "p0", {"model": "m", "batch_gcs_bucket": "my-bucket", "project": "p"})
            runner.run()
        mock_storage_client = mock_gcs.Client.return_value
        assert mock_storage_client.bucket.called
        bucket_arg = mock_storage_client.bucket.call_args.args[0]
        assert bucket_arg == "my-bucket"

    def test_run_creates_batch_prediction_job(self):
        output_lines = [_make_vertex_output_line("r0", "result")]
        mock_aip, mock_gcs = self._build_vertex_mocks(output_lines)
        with patch.dict(sys.modules, {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_aip,
            "google.cloud.storage": mock_gcs,
        }):
            runner = _vertex_runner(batch_gcs_bucket="b", project="p")
            runner.add("k0", "p0", {"model": "gemini-2.0-flash", "batch_gcs_bucket": "b", "project": "p"})
            runner.run()
        assert mock_aip.BatchPredictionJob.create.called

    def test_run_polls_until_terminal_state(self):
        mock_aip = MagicMock()
        mock_gcs = MagicMock()
        output_lines = [_make_vertex_output_line("r0", "final")]
        mock_storage_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = MagicMock()
        mock_storage_client.bucket.return_value = mock_bucket
        mock_output_blob = MagicMock()
        mock_output_blob.name = "coeval/output/job/predictions.jsonl"
        mock_output_blob.download_as_text.return_value = "\n".join(output_lines)
        mock_storage_client.list_blobs.return_value = [mock_output_blob]
        mock_gcs.Client.return_value = mock_storage_client
        mock_job = MagicMock()
        mock_job.resource_name = "projects/p/batchJobs/poll123"
        mock_job.state.name = "JOB_STATE_RUNNING"

        def do_refresh():
            mock_job.state.name = "JOB_STATE_SUCCEEDED"

        mock_job.refresh.side_effect = do_refresh
        mock_aip.BatchPredictionJob.create.return_value = mock_job
        with patch.dict(sys.modules, {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_aip,
            "google.cloud.storage": mock_gcs,
        }):
            runner = _vertex_runner(batch_gcs_bucket="b", project="p")
            runner.add("k0", "p0", {"model": "m", "batch_gcs_bucket": "b", "project": "p"})
            results = runner.run()
        assert mock_job.refresh.call_count == 1
        assert results["k0"] == "final"

    def test_run_normalizes_short_model_id_to_publisher_resource(self):
        output_lines = [_make_vertex_output_line("r0", "ok")]
        mock_aip, mock_gcs = self._build_vertex_mocks(output_lines)
        with patch.dict(sys.modules, {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_aip,
            "google.cloud.storage": mock_gcs,
        }):
            runner = _vertex_runner(batch_gcs_bucket="b", project="p")
            runner.add("k0", "p0", {
                "model": "gemini-2.0-flash-001", "batch_gcs_bucket": "b", "project": "p"
            })
            runner.run()
        create_kwargs = mock_aip.BatchPredictionJob.create.call_args.kwargs
        model_name_arg = create_kwargs.get("model_name", "")
        assert "gemini-2.0-flash-001" in model_name_arg


# ===========================================================================
# create_batch_runner() factory
# ===========================================================================

class TestCreateBatchRunnerFactory:
    """Tests for the create_batch_runner() factory in experiments/interfaces/__init__.py."""

    def test_returns_bedrock_batch_runner_for_bedrock(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.bedrock_batch import BedrockBatchRunner
        runner = create_batch_runner("bedrock")
        assert isinstance(runner, BedrockBatchRunner)

    def test_returns_vertex_batch_runner_for_vertex(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.vertex_batch import VertexBatchRunner
        runner = create_batch_runner("vertex")
        assert isinstance(runner, VertexBatchRunner)

    def test_raises_value_error_for_unsupported_interface(self):
        from runner.interfaces import create_batch_runner
        with pytest.raises(ValueError, match="No batch runner available"):
            create_batch_runner("unsupported_interface")

    def test_raises_value_error_for_huggingface(self):
        from runner.interfaces import create_batch_runner
        with pytest.raises(ValueError):
            create_batch_runner("huggingface")

    def test_raises_value_error_for_empty_string(self):
        from runner.interfaces import create_batch_runner
        with pytest.raises(ValueError):
            create_batch_runner("")

    def test_raises_value_error_for_unknown_provider(self):
        from runner.interfaces import create_batch_runner
        with pytest.raises(ValueError):
            create_batch_runner("my_custom_llm")

    def test_bedrock_runner_passes_access_key(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.bedrock_batch import BedrockBatchRunner
        runner = create_batch_runner("bedrock", access_key="test-key")
        assert isinstance(runner, BedrockBatchRunner)

    def test_vertex_runner_passes_access_key(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.vertex_batch import VertexBatchRunner
        runner = create_batch_runner("vertex", access_key="test-key")
        assert isinstance(runner, VertexBatchRunner)

    def test_bedrock_runner_passes_kwargs(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.bedrock_batch import BedrockBatchRunner
        runner = create_batch_runner("bedrock", batch_s3_bucket="my-bucket", batch_role_arn="arn:r")
        assert isinstance(runner, BedrockBatchRunner)
        assert runner._s3_bucket == "my-bucket"
        assert runner._role_arn == "arn:r"

    def test_vertex_runner_passes_project_kwarg(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.vertex_batch import VertexBatchRunner
        runner = create_batch_runner("vertex", project="proj")
        assert isinstance(runner, VertexBatchRunner)
        assert runner._project == "proj"

    def test_openai_runner_returned_for_openai(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.openai_batch import OpenAIBatchRunner
        runner = create_batch_runner("openai")
        assert isinstance(runner, OpenAIBatchRunner)

    def test_anthropic_runner_returned_for_anthropic(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.anthropic_batch import AnthropicBatchRunner
        runner = create_batch_runner("anthropic")
        assert isinstance(runner, AnthropicBatchRunner)

    def test_gemini_runner_returned_for_gemini(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.gemini_batch import GeminiBatchRunner
        runner = create_batch_runner("gemini")
        assert isinstance(runner, GeminiBatchRunner)

    def test_azure_runner_returned_for_azure_openai(self):
        from runner.interfaces import create_batch_runner
        from runner.interfaces.azure_batch import AzureBatchRunner
        runner = create_batch_runner("azure_openai")
        assert isinstance(runner, AzureBatchRunner)

    def test_error_message_lists_supported_interfaces(self):
        from runner.interfaces import create_batch_runner
        with pytest.raises(ValueError) as exc_info:
            create_batch_runner("bad_iface")
        msg = str(exc_info.value)
        assert "bedrock" in msg
        assert "vertex" in msg
        assert "openai" in msg

    def test_bedrock_runner_has_add_method(self):
        from runner.interfaces import create_batch_runner
        runner = create_batch_runner("bedrock")
        assert callable(getattr(runner, "add", None))

    def test_vertex_runner_has_run_method(self):
        from runner.interfaces import create_batch_runner
        runner = create_batch_runner("vertex")
        assert callable(getattr(runner, "run", None))

    def test_bedrock_runner_len_is_zero_initially(self):
        from runner.interfaces import create_batch_runner
        runner = create_batch_runner("bedrock")
        assert len(runner) == 0

    def test_vertex_runner_len_is_zero_initially(self):
        from runner.interfaces import create_batch_runner
        runner = create_batch_runner("vertex")
        assert len(runner) == 0
