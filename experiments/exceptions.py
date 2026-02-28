"""CoEval pipeline exception types."""
from __future__ import annotations


class PartialPhaseFailure(Exception):
    """Raised when a phase completes but with some items/slots failing.

    Unlike a total phase failure (which raises RuntimeError and stops the
    pipeline), a partial failure means the phase produced *some* output and
    the pipeline can continue to subsequent phases.  The runner logs the
    failure prominently and sets exit_code=1 but does NOT break the loop.

    Attributes:
        n_failures: Number of individual failures within the phase.
        n_successes: Number of items/slots that completed successfully.
        errors: List of human-readable error messages.
    """

    def __init__(self, n_failures: int, n_successes: int, errors: list[str]) -> None:
        self.n_failures = n_failures
        self.n_successes = n_successes
        self.errors = errors
        super().__init__(
            f"{n_failures} failure(s), {n_successes} success(es):\n"
            + "\n".join(f"  • {e}" for e in errors[:10])
            + (f"\n  ... and {len(errors) - 10} more" if len(errors) > 10 else "")
        )
