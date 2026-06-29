from __future__ import annotations

import pytest

from player.service import PlayerService
from player.store import PlayerStore


@pytest.fixture
def temp_store(tmp_path):
    raw_path = tmp_path / "raw" / "roster.json"
    processed_path = tmp_path / "processed" / "players.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text("[]\n", encoding="utf-8")
    store = PlayerStore(raw_path=raw_path, processed_path=processed_path, repo_root=tmp_path)
    return store


@pytest.fixture
def service(temp_store):
    return PlayerService(temp_store)
