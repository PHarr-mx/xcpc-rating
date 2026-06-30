from __future__ import annotations

import pytest

from player.service import PlayerService
from player.store import PlayerStore
from team.service import TeamService
from team.store import TeamStore


@pytest.fixture
def temp_store(tmp_path):
    raw_path = tmp_path / "raw" / "roster.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text("[]\n", encoding="utf-8")
    store = PlayerStore(raw_path=raw_path, repo_root=tmp_path)
    return store


@pytest.fixture
def service(temp_store):
    return PlayerService(temp_store)


@pytest.fixture
def temp_team_store(tmp_path):
    raw_path = tmp_path / "raw" / "teams" / "roster.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text("[]\n", encoding="utf-8")
    store = TeamStore(raw_path=raw_path, repo_root=tmp_path)
    return store


@pytest.fixture
def team_service(temp_team_store):
    return TeamService(temp_team_store)
