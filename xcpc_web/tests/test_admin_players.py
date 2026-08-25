"""P4a admin 选手 CRUD 回归。"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from xcpc_core.audit import api as audit_api
from xcpc_core.db.tables import AuditLog
from xcpc_core.player import api as player_api
from xcpc_core.player.models import OJAccount, PlayerCreate, PlayerStatus, PlayerUpdate

from xcpc_web.states.admin.players import AdminPlayersState


@pytest.fixture
def player(core_store):
    return player_api.create_player(
        PlayerCreate(
            name="甲同学",
            handle="jia",
            grade=2023,
            aliases=["Jia"],
            oj_accounts=[OJAccount(platform="codeforces", handle="tourist")],
        )
    )


def test_non_admin_is_guarded_and_sees_no_players(build_state, make_user, core_store, player):
    state = build_state(AdminPlayersState, make_user("member"))
    assert state.players == []
    assert state.on_load() is not None


def test_admin_can_filter_players(build_state, make_user, core_store, player):
    player_api.create_player(PlayerCreate(name="乙同学", grade=2024, status=PlayerStatus.retired))
    player_api.create_player(PlayerCreate(name="丙同学", grade=2025, status=PlayerStatus.left))
    state = build_state(AdminPlayersState, make_user("root", role="admin"))

    assert [item["id"] for item in state.players] == ["p001", "p002", "p003"]
    state.set_search("tourist")
    assert [item["id"] for item in state.players] == ["p001"]
    state.set_search("")
    state.set_status_filter("retired")
    assert [item["name"] for item in state.players] == ["乙同学"]
    state.set_status_filter("all")
    state.set_grade_filter("2023")
    assert [item["id"] for item in state.players] == ["p001"]


def test_admin_create_player_and_audit(build_state, make_user, core_store):
    admin = make_user("root", role="admin")
    audit_api.configure_session(core_store)
    state = build_state(AdminPlayersState, admin)
    state.form_name = "新选手"
    state.form_grade = "2025"
    state.form_handle = "new"
    state.form_aliases = "New Name，N"
    state.form_oj_accounts = "codeforces:new_cf\natcoder:new_atcoder"

    state.save_player()

    created = player_api.get_player("p001")
    assert created.name == "新选手"
    assert created.aliases == ["New Name", "N"]
    assert [(a.platform, a.handle) for a in created.oj_accounts] == [
        ("codeforces", "new_cf"),
        ("atcoder", "new_atcoder"),
    ]
    assert state.form_open is False
    assert state.admin_feedback == "已创建选手：新选手（p001）"
    logs = core_store.execute(select(AuditLog)).scalars().all()
    assert [(log.action, log.target) for log in logs] == [("player.create", "p001")]


def test_admin_update_player_and_audit(build_state, make_user, core_store, player):
    admin = make_user("root", role="admin")
    audit_api.configure_session(core_store)
    state = build_state(AdminPlayersState, admin)
    state.open_edit(player.id)
    assert state.form_name == "甲同学"
    assert state.form_oj_accounts == "codeforces:tourist"
    state.form_name = "甲同学（改）"
    state.form_grade = "2024"
    state.form_status = "retired"
    state.form_oj_accounts = "codeforces:tourist\nluogu:jia"

    state.save_player()

    updated = player_api.get_player(player.id)
    assert updated.name == "甲同学（改）"
    assert updated.grade == 2024
    assert updated.status == PlayerStatus.retired
    assert [(a.platform, a.handle) for a in updated.oj_accounts] == [
        ("codeforces", "tourist"),
        ("luogu", "jia"),
    ]
    logs = core_store.execute(select(AuditLog)).scalars().all()
    assert [(log.action, log.target) for log in logs] == [("player.update", player.id)]


def test_admin_mark_left_is_soft_delete(build_state, make_user, core_store, player):
    admin = make_user("root", role="admin")
    audit_api.configure_session(core_store)
    state = build_state(AdminPlayersState, admin)

    state.mark_player_left(player.id)

    assert player_api.get_player(player.id).status == PlayerStatus.left
    assert state.admin_feedback == f"已将选手标记为离队：甲同学（{player.id}）"
    logs = core_store.execute(select(AuditLog)).scalars().all()
    assert [(log.action, log.target) for log in logs] == [("player.delete", player.id)]


def test_validation_error_is_shown_by_field(build_state, make_user, core_store):
    state = build_state(AdminPlayersState, make_user("root", role="admin"))
    state.form_name = ""
    state.form_grade = "2024"
    state.save_player()

    assert state.admin_error == "请修正表单中的错误"
    assert state.name_error
    assert state.form_open is False


def test_duplicate_oj_account_is_shown(build_state, make_user, core_store):
    player_api.create_player(
        PlayerCreate(
            name="甲",
            grade=2023,
            oj_accounts=[OJAccount(platform="codeforces", handle="same")],
        )
    )
    player_api.create_player(PlayerCreate(name="乙", grade=2024))
    state = build_state(AdminPlayersState, make_user("root", role="admin"))
    state.editing_player_id = "p002"
    state.form_name = "乙"
    state.form_grade = "2024"
    state.form_oj_accounts = "codeforces:same"

    state.save_player()

    assert state.admin_error == "校内 handle 或 OJ 账号与他人重复"
    assert state.general_error == state.admin_error
    assert state.handle_error == state.admin_error
    assert state.oj_accounts_error == state.admin_error
