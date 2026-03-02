
import pathlib

dest = pathlib.Path(r"E:/Projects/CoEval/main/experiments/tests/test_batch_runners.py")
existing = dest.read_text(encoding="utf-8")

bedrock_run = """\n\n# ===========================================================================\n# BedrockBatchRunner -- run()\n# ===========================================================================\n\nclass TestBedrockRun:\n    DOCQ = "Tests for BedrockBatchRunner.run()."\n\n    def test_run_returns_empty_dict_when_no_requests(self):\n        runner = _bedrock_runner()\n        assert runner.run() == {}\n"""

print(len(existing + bedrock_run))
