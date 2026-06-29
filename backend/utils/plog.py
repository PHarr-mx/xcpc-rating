from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

LogLevel = str

_LEVEL_LABELS: dict[LogLevel, str] = {
    "info": "INFO",
    "warning": "WARNING",
    "error": "ERROR",
}


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for parent in [current, *current.parents]:
        if (parent / "data" / "raw").is_dir():
            return parent
    raise FileNotFoundError("无法定位仓库根目录（缺少 data/raw）")


class Plog:
    """同时向终端与 JSONL 文件写入日志。

    每个实例对应一个日志文件，文件名为实例化时刻的时间戳，例如 ``2026-06-29_143052.jsonl``。
    默认写入仓库根目录下的 ``logs/``。在 CLI 入口实例化后，将实例作为参数传给后续函数。
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        log_dir: Path | str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.name = name
        self.created_at = created_at or datetime.now()
        self.log_dir = Path(log_dir) if log_dir is not None else find_repo_root() / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        filename = self.created_at.strftime("%Y-%m-%d_%H%M%S")
        self.log_path = self.log_dir / f"{filename}.jsonl"
        self._file: TextIO = self.log_path.open("a", encoding="utf-8")

    @property
    def log_file(self) -> Path:
        return self.log_path

    def info(self, message: str, **extra: Any) -> None:
        self._log("info", message, extra=extra or None)

    def warning(self, message: str, **extra: Any) -> None:
        self._log("warning", message, extra=extra or None)

    def error(self, message: str, **extra: Any) -> None:
        self._log("error", message, extra=extra or None)

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def _log(self, level: LogLevel, message: str, *, extra: dict[str, Any] | None) -> None:
        timestamp = datetime.now()
        entry: dict[str, Any] = {
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "level": level,
            "message": message,
        }
        if self.name:
            entry["logger"] = self.name
        if extra:
            entry["extra"] = extra

        self._print_line(level, timestamp, message)
        self._write_jsonl(entry)

    def _print_line(self, level: LogLevel, timestamp: datetime, message: str) -> None:
        label = _LEVEL_LABELS[level]
        prefix = f"[{label}]"
        if self.name:
            prefix = f"{prefix} [{self.name}]"
        line = f"{prefix} {timestamp.strftime('%Y-%m-%d %H:%M:%S')} {message}"
        print(line, file=sys.stderr if level == "error" else sys.stdout)

    def _write_jsonl(self, entry: dict[str, Any]) -> None:
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()
