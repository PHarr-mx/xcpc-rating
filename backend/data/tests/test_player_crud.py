from __future__ import annotations

import json
from datetime import date

import pytest

from player.exceptions import PlayerAlreadyExistsError, PlayerNotFoundError, PlayerValidationError
from player.models import OJAccount, PlayerCreate, PlayerStatus, PlayerUpdate

def test_create_and_get(service):
    created = service.create_player(
        PlayerCreate(name="测试甲", handle="csj", grade=2025, status=PlayerStatus.active),
        today=date(2026, 6, 29),
    )
    assert created.id == "p001"
    assert created.grade_label == "2025级"
    assert created.status_label == "现役"

    fetched = service.get_player(created.id)
    assert fetched.name == "测试甲"


def test_list_filters(service):
    service.create_player(PlayerCreate(name="A", grade=2024), today=date(2026, 1, 1))
    left = service.create_player(PlayerCreate(name="B", grade=2024, status=PlayerStatus.left), today=date(2026, 1, 1))
    assert len(service.list_players()) == 2
    assert len(service.list_players(include_left=False)) == 1
    assert service.list_players(status=PlayerStatus.left)[0].id == left.id


def test_update_player(service):
    created = service.create_player(PlayerCreate(name="原姓名", grade=2023), today=date(2026, 1, 1))
    updated = service.update_player(
        created.id,
        PlayerUpdate(name="新姓名", status=PlayerStatus.retired),
        today=date(2026, 6, 29),
    )
    assert updated.name == "新姓名"
    assert updated.status == PlayerStatus.retired
    assert updated.status_label == "退役"
    assert updated.updated_at == date(2026, 6, 29)


def test_delete_player(service):
    created = service.create_player(PlayerCreate(name="待删", grade=2023), today=date(2026, 1, 1))
    removed = service.delete_player(created.id, today=date(2026, 6, 29))
    assert removed.id == created.id
    with pytest.raises(PlayerNotFoundError):
        service.get_player(created.id)


def test_duplicate_oj_account(service):
    service.create_player(
        PlayerCreate(
            name="甲",
            grade=2023,
            oj_accounts=[OJAccount(platform="codeforces", handle="dup_cf")],
        ),
        today=date(2026, 1, 1),
    )
    with pytest.raises(PlayerValidationError):
        service.create_player(
            PlayerCreate(
                name="乙",
                grade=2024,
                oj_accounts=[OJAccount(platform="codeforces", handle="dup_cf")],
            ),
            today=date(2026, 1, 1),
        )


def test_find_by_name_and_oj(service):
    player = service.create_player(
        PlayerCreate(name="查找", grade=2023, aliases=["别名"], handle="cz"),
        today=date(2026, 1, 1),
    )
    assert service.find_by_name("别名")[0].id == player.id
    assert service.find_by_oj("codeforces", "missing") is None


def test_persists_raw(temp_store, service):
    service.create_player(PlayerCreate(name="持久化", grade=2023, handle="cch"), today=date(2026, 6, 29))

    raw = json.loads(temp_store.raw_path.read_text(encoding="utf-8"))

    assert raw[0]["name"] == "持久化"
    assert "grade_label" not in raw[0]
