from __future__ import annotations

import json
from datetime import datetime

import pytest

from utils.plog import Plog, find_repo_root


@pytest.fixture
def log_dir(tmp_path):
    return tmp_path / "logs"


def test_plog_writes_jsonl_and_uses_created_at_filename(log_dir):
    created_at = datetime(2026, 6, 29, 14, 30, 52)
    plog = Plog(name="test", log_dir=log_dir, created_at=created_at)

    assert plog.log_file == log_dir / "2026-06-29_143052.jsonl"

    plog.info("hello", player_id="p1")
    plog.warning("careful")
    plog.error("failed", code=500)
    plog.close()

    lines = plog.log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3

    first = json.loads(lines[0])
    assert first["level"] == "info"
    assert first["message"] == "hello"
    assert first["logger"] == "test"
    assert first["extra"] == {"player_id": "p1"}

    assert json.loads(lines[2])["level"] == "error"


def test_plog_close(log_dir):
    plog = Plog(log_dir=log_dir, created_at=datetime(2026, 1, 1, 0, 0, 0))
    plog.info("inside")
    plog.close()

    assert plog.log_file.exists()
    assert plog._file.closed


def test_default_log_dir_is_repo_logs():
    plog = Plog(created_at=datetime(2099, 1, 1, 12, 0, 0))
    try:
        assert plog.log_dir == find_repo_root() / "logs"
        assert plog.log_file.name == "2099-01-01_120000.jsonl"
    finally:
        plog.close()
        if plog.log_file.exists():
            plog.log_file.unlink()
