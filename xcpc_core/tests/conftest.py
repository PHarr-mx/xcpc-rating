from __future__ import annotations

import pytest

from xcpc_core.player.service import PlayerService
from xcpc_core.player.store import PlayerStore
from xcpc_core.team.service import TeamService
from xcpc_core.team.store import TeamStore


@pytest.fixture
def temp_store(db_session):
    return PlayerStore(db_session)


@pytest.fixture
def service(temp_store):
    return PlayerService(temp_store)


@pytest.fixture
def temp_team_store(db_session):
    return TeamStore(db_session)


@pytest.fixture
def team_service(temp_team_store):
    return TeamService(temp_team_store)
