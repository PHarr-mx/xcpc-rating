"""P4b admin 队伍 CRUD 回归。"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from xcpc_core.audit import api as audit_api
from xcpc_core.db.tables import AuditLog
from xcpc_core.player import api as player_api
from xcpc_core.player.models import PlayerCreate
from xcpc_core.team import api as team_api
from xcpc_core.team.exceptions import TeamAlreadyExistsError
from xcpc_core.team.models import TeamCreate

from xcpc_web.states.admin.teams import AdminTeamsState


@pytest.fixture
def players(core_store):
    return [
        player_api.create_player(PlayerCreate(name="甲同学", handle="jia", grade=2023)),
        player_api.create_player(PlayerCreate(name="乙同学", handle="yi", grade=2024)),
        player_api.create_player(PlayerCreate(name="丙同学", handle="bing", grade=2025)),
    ]


def test_non_admin_is_guarded_and_sees_no_teams(build_state, make_user, core_store, players):
    team_api.create_team(TeamCreate(members=[players[0].id], aliases=["甲队"]))
    state = build_state(AdminTeamsState, make_user("member"))

    assert state.teams == []
    assert state.on_load() is not None


def test_admin_can_search_teams_by_member_or_alias(build_state, make_user, core_store, players):
    first = team_api.create_team(
        TeamCreate(members=[players[0].id, players[1].id], aliases=["Alpha"])
    )
    second = team_api.create_team(TeamCreate(members=[players[2].id], aliases=["Beta"]))
    state = build_state(AdminTeamsState, make_user("root", role="admin"))

    assert [item["id"] for item in state.teams] == [first.id, second.id]
    state.set_search("乙同学")
    assert [item["id"] for item in state.teams] == [first.id]
    state.set_search(first.member_key)
    assert [item["id"] for item in state.teams] == [first.id]
    state.set_search("beta")
    assert [item["id"] for item in state.teams] == [second.id]


def test_admin_create_team_and_audit(build_state, make_user, core_store, players):
    admin = make_user("root", role="admin")
    audit_api.configure_session(core_store)
    state = build_state(AdminTeamsState, admin)
    state.form_id = ""
    state.form_members_text = f"{players[1].id}, {players[0].id}"
    state.form_aliases_text = "校赛队，Alpha"

    state.save_team()

    created = team_api.get_team("t001")
    assert created.members == [players[1].id, players[0].id]
    assert created.member_key == f"{players[0].id}|{players[1].id}"
    assert created.aliases == ["校赛队", "Alpha"]
    assert state.form_open is False
    assert state.admin_feedback == "已创建队伍：t001（校赛队、Alpha）"
    logs = core_store.execute(select(AuditLog)).scalars().all()
    assert [(log.action, log.target) for log in logs] == [("team.create", "t001")]


def test_unknown_member_is_shown_on_members_field(build_state, make_user, core_store, players):
    state = build_state(AdminTeamsState, make_user("root", role="admin"))
    state.form_members_text = f"{players[0].id},p999"
    state.save_team()

    assert state.admin_error == "请修正表单中的错误"
    assert "p999" in state.members_error
    assert team_api.list_teams() == []


def test_duplicate_member_key_is_prechecked(build_state, make_user, core_store, players):
    existing = team_api.create_team(
        TeamCreate(members=[players[0].id, players[1].id], aliases=["已有队名"])
    )
    state = build_state(AdminTeamsState, make_user("root", role="admin"))
    state.form_members_text = f"{players[1].id},{players[0].id}"
    state.form_aliases_text = "另一个队名"

    state.save_team()

    assert state.admin_error == f"队员组合已存在：{existing.member_key}"
    assert existing.id in state.members_error
    assert len(team_api.list_teams()) == 1


def test_duplicate_members_are_validation_error(build_state, make_user, core_store, players):
    state = build_state(AdminTeamsState, make_user("root", role="admin"))
    state.form_members_text = f"{players[0].id},{players[0].id}"
    state.save_team()

    assert state.admin_error == "请修正表单中的错误"
    assert state.members_error
    assert team_api.list_teams() == []


def test_admin_update_alias_and_audit(build_state, make_user, core_store, players):
    team = team_api.create_team(TeamCreate(members=[players[0].id], aliases=["初始队名"]))
    admin = make_user("root", role="admin")
    audit_api.configure_session(core_store)
    state = build_state(AdminTeamsState, admin)
    state.open_edit(team.id)
    assert state.form_members_text == players[0].id
    assert state.form_aliases_text == "初始队名"
    state.form_aliases_text = "初始队名\n新队名"

    state.save_team()

    assert team_api.get_team(team.id).aliases == ["初始队名", "新队名"]
    assert state.admin_feedback == f"已更新队伍别名：{team.id}"
    logs = core_store.execute(select(AuditLog)).scalars().all()
    assert [(log.action, log.target) for log in logs] == [("team.update", team.id)]


def test_admin_delete_team_and_audit(build_state, make_user, core_store, players):
    team = team_api.create_team(TeamCreate(members=[players[0].id], aliases=["待删除"]))
    admin = make_user("root", role="admin")
    audit_api.configure_session(core_store)
    state = build_state(AdminTeamsState, admin)

    state.delete_team(team.id)

    assert team_api.list_teams() == []
    assert state.admin_feedback == f"已删除队伍：{team.id}"
    logs = core_store.execute(select(AuditLog)).scalars().all()
    assert [(log.action, log.target) for log in logs] == [("team.delete", team.id)]
