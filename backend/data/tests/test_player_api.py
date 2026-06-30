from __future__ import annotations

from datetime import date

from player import api, create_player, list_players
from player.models import PlayerCreate, PlayerStatus
from player.store import PlayerStore


def test_api_functions_delegate_to_service(temp_store):
    api.configure_store(temp_store)

    created = create_player(
        PlayerCreate(name="API 测试", grade=2025, handle="api"),
        today=date(2026, 6, 29),
    )
    players = list_players(include_left=False)
    assert any(player.id == created.id for player in players)
    assert api.get_player(created.id).name == "API 测试"


def test_api_accepts_per_call_store(temp_store):
    other_store = PlayerStore(
        raw_path=temp_store.raw_path.parent / "other.json",
        repo_root=temp_store.raw_path.parent,
    )
    other_store.raw_path.parent.mkdir(parents=True, exist_ok=True)
    other_store.raw_path.write_text("[]\n", encoding="utf-8")

    created = create_player(
        PlayerCreate(name="隔离存储", grade=2024),
        store=other_store,
        today=date(2026, 1, 1),
    )
    assert created.id == "p001"
    assert list_players(store=other_store)[0].id == created.id
    assert list_players(store=temp_store) == []
