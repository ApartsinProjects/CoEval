"""Run logger: writes timestamped entries to run.log and optionally to console."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_LEVELS: dict[str, int] = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3}


class RunLogger:
    def __init__(
        self,
        log_path: str | Path,
        min_level: str = 'INFO',
        console: bool = True,
    ) -> None:
        self._path = Path(log_path)
        self._min = _LEVELS.get(min_level.upper(), 1)
        self._console = console

    def _write(self, level: str, message: str) -> None:
        if _LEVELS.get(level, 0) < self._min:
            return
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        line = f"{ts} [{level}] {message}"
        with open(self._path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        if self._console:
            stream = sys.stderr if level in ('WARNING', 'ERROR') else sys.stdout
            print(line, file=stream)

    def debug(self, msg: str) -> None:
        self._write('DEBUG', msg)

    def info(self, msg: str) -> None:
        self._write('INFO', msg)

    def warning(self, msg: str) -> None:
        self._write('WARNING', msg)

    def error(self, msg: str) -> None:
        self._write('ERROR', msg)
