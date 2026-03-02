"""Root pytest configuration — shared fixtures and session-level setup."""
import gc
import pytest


@pytest.fixture(autouse=True)
def _gc_after_test():
    """Force a GC cycle after every test to reclaim MagicMock trees promptly.

    On Windows, CPython's cyclic GC does not run between tests by default,
    so large MagicMock hierarchies (e.g. mock boto3 / vertexai trees built in
    test_batch_runners.py) accumulate in memory and can trigger swap.
    """
    yield
    gc.collect()
