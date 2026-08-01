from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from xcpc_core.db.base import Base
from xcpc_core.db import tables  # noqa: F401
from xcpc_core.player import api, create_player, list_players
from xcpc_core.player.models import PlayerCreate, PlayerStatus
from xcpc_core.player.store import PlayerStore


def test_api_functions_delegate_to_service(temp_store):
    api.configure_store(temp_store)

    created = create_player(
        PlayerCreate(name="API 测试", grade=2025, handle="api"),
        today=date(2026, 6, 29),
    )
    players = list_players(include_left=False)
    assert any(player.id == created.id for player in players)
    assert api.get_player(created.id).name == "API 测试"


def test_api_accepts_per_call_store(db_session):
    # 第二个独立内存库，验证 per-call store 隔离
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    other_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    other_store = PlayerStore(other_session)

    created = create_player(
        PlayerCreate(name="隔离存储", grade=2024),
        store=other_store,
        today=date(2026, 1, 1),
    )
    assert created.id == "p001"
    assert list_players(store=other_store)[0].id == created.id
    assert list_players(store=PlayerStore(db_session)) == []

    other_session.close()
