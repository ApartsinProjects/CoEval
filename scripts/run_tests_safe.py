"""Run pytest with a memory cap.

Monitors the pytest process every 2 seconds.  If RSS memory exceeds
MEMORY_LIMIT_MB the process tree is killed and a clear error is printed.

Usage:
    python scripts/run_tests_safe.py [pytest args...]

Examples:
    python scripts/run_tests_safe.py Tests/runner Tests/benchmark -q
    python scripts/run_tests_safe.py Tests/ -q --tb=short
    python scripts/run_tests_safe.py Tests/ -q --tb=short --limit 4096
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time

try:
    import psutil
except ImportError:
    sys.exit("psutil is required: pip install psutil")

DEFAULT_LIMIT_MB = 3072  # 3 GB — adjust if your machine has less RAM


def _monitor(proc: subprocess.Popen, limit_mb: int, stop: threading.Event) -> None:
    """Background thread: kill proc if its RSS exceeds limit_mb."""
    try:
        ps = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        return

    while not stop.is_set():
        try:
            # Sum RSS of pytest + all child processes (spawned workers etc.)
            children = ps.children(recursive=True)
            total_rss = ps.memory_info().rss
            for child in children:
                try:
                    total_rss += child.memory_info().rss
                except psutil.NoSuchProcess:
                    pass

            total_mb = total_rss / (1024 * 1024)
            if total_mb > limit_mb:
                print(
                    f"\n{'='*70}\n"
                    f"  MEMORY LIMIT EXCEEDED: {total_mb:.0f} MB > {limit_mb} MB\n"
                    f"  Killing pytest process tree ...\n"
                    f"{'='*70}\n",
                    flush=True,
                )
                # Kill process tree
                try:
                    for child in ps.children(recursive=True):
                        child.kill()
                    ps.kill()
                except psutil.NoSuchProcess:
                    pass
                return

        except psutil.NoSuchProcess:
            return

        time.sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run pytest with a memory cap (kills process if RSS exceeds limit).",
        add_help=True,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT_MB,
        metavar="MB",
        help=f"Memory limit in MB (default: {DEFAULT_LIMIT_MB})",
    )
    # Unknown args are forwarded to pytest
    args, pytest_args = parser.parse_known_args()

    cmd = [sys.executable, "-m", "pytest"] + pytest_args
    print(
        f"Running: {' '.join(cmd)}\n"
        f"Memory limit: {args.limit} MB\n"
    )

    stop_event = threading.Event()
    proc = subprocess.Popen(cmd)

    monitor_thread = threading.Thread(
        target=_monitor, args=(proc, args.limit, stop_event), daemon=True
    )
    monitor_thread.start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nInterrupted — killing pytest ...", flush=True)
        try:
            ps = psutil.Process(proc.pid)
            for child in ps.children(recursive=True):
                child.kill()
            ps.kill()
        except psutil.NoSuchProcess:
            pass
    finally:
        stop_event.set()
        monitor_thread.join(timeout=5)

    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
