from __future__ import annotations

import json
from datetime import date

import pytest

from xcpc_core.player.exceptions import PlayerAlreadyExistsError, PlayerNotFoundError, PlayerValidationError
from xcpc_core.player.models import OJAccount, PlayerCreate, PlayerStatus, PlayerUpdate
from xcpc_core.player.store import PlayerStore

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


def test_mark_retired_keeps_player_visible(service):
    """mark_retired 与 mark_left 语义对比：退役保留在 visible 列表，离队被排除。"""
    created = service.create_player(PlayerCreate(name="退役测试", grade=2023), today=date(2026, 1, 1))
    retired = service.mark_retired(created.id, today=date(2026, 6, 29))
    assert retired.status == PlayerStatus.retired
    assert retired.status_label == "退役"
    # 退役不是软删除：选手仍在默认列表中
    assert [p.id for p in service.list_players(include_left=False)] == [created.id]
    # 再标记离队后才会被排除
    service.mark_left(created.id, today=date(2026, 7, 1))
    assert service.list_players(include_left=False) == []


def test_mark_active_promotes_probation_only(service):
    """入队：预备队员转现役；其他状态被守卫拒绝。"""
    created = service.create_player(
        PlayerCreate(name="预备测试", grade=2026, status=PlayerStatus.probation),
        today=date(2026, 9, 1),
    )
    assert created.status_label == "预备队员"
    activated = service.mark_active(created.id, today=date(2026, 10, 1))
    assert activated.status == PlayerStatus.active
    assert activated.status_label == "现役"

    # 非预备队员不能借「入队」复活
    for status in (PlayerStatus.retired, PlayerStatus.left):
        player = service.create_player(
            PlayerCreate(name=f"守卫-{status.value}", grade=2025, status=status),
            today=date(2026, 9, 1),
        )
        with pytest.raises(PlayerValidationError):
            service.mark_active(player.id)


def test_update_player_oj_accounts(service):
    """oj_accounts 更新：嵌套 DTO 不能退化成 dict（model_dump+model_copy 坑）。"""
    created = service.create_player(
        PlayerCreate(name="oj 更新", grade=2023), today=date(2026, 1, 1)
    )
    updated = service.update_player(
        created.id,
        PlayerUpdate(oj_accounts=[OJAccount(platform="codeforces", handle="cf_1")]),
        today=date(2026, 6, 29),
    )
    assert [(a.platform, a.handle) for a in updated.oj_accounts] == [
        ("codeforces", "cf_1")
    ]
    # 从库里读回也一致（覆盖 store._write_nested 往返）
    fetched = service.get_player(created.id)
    assert [(a.platform, a.handle) for a in fetched.oj_accounts] == [
        ("codeforces", "cf_1")
    ]


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


def test_persists(temp_store, service):
    service.create_player(PlayerCreate(name="持久化", grade=2023, handle="cch"), today=date(2026, 6, 29))

    # 用同一 session 新建 store 重新读，验证已落库
    reloaded = PlayerStore(temp_store.session).list_all()

    assert len(reloaded) == 1
    assert reloaded[0].name == "持久化"
    assert reloaded[0].handle == "cch"
    assert reloaded[0].grade_label is None  # 派生字段不入库
