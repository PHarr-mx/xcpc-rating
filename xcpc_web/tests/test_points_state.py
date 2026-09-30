"""积分状态测试：守卫、认证工作流、双账本记分与榜单（积分制 v1）。"""

from datetime import date

import pytest
from sqlalchemy import select

from xcpc_core.db.tables import Player, PointsClaim, PointsEntry, Team, TeamAlias, TeamMember
from xcpc_core.points import api as points_api
from xcpc_core.points.models import PointsEventCreate

from xcpc_web.states.admin.points import AdminPointsState
from xcpc_web.states.points import PointsState


@pytest.fixture
def roster(core_store):
    """p1/p2/p3 + 队伍 t1（p1、p2 现役成员）。"""
    s = core_store
    s.add_all(
        [
            Player(id="p1", name="张三"),
            Player(id="p2", name="李四"),
            Player(id="p3", name="王五"),
        ]
    )
    s.add(Team(id="t1", member_key="p1|p2", size=2))
    s.add(TeamMember(team_id="t1", player_id="p1", seat=1))
    s.add(TeamMember(team_id="t1", player_id="p2", seat=2))
    s.add(TeamAlias(team_id="t1", alias="一队"))
    s.commit()
    return s


def _make_event(**overrides):
    params = dict(
        title="测试积分场", date=date(2025, 9, 10), entity="player",
        kind="solved", max_value=10, n_teams=5,
    )
    params.update(overrides)
    return points_api.create_event(params=PointsEventCreate(**params), created_by=1)


# ---- 守卫 ------------------------------------------------------------------


def test_admin_on_load_non_admin_redirects(build_state, make_user):
    st = build_state(AdminPointsState, make_user("alice"))
    assert st.on_load() is not None


def test_admin_on_load_admin_passes(build_state, make_user):
    st = build_state(AdminPointsState, make_user("root", role="admin"))
    assert st.on_load() is None


def test_admin_vars_empty_for_non_admin(build_state, make_user):
    st = build_state(AdminPointsState, make_user("alice"))
    assert st.events == [] and st.staged_claims == []


def test_approve_non_admin_redirects(build_state, make_user):
    st = build_state(AdminPointsState, make_user("alice"))
    assert st.approve(1) is not None


def test_points_on_load_unauthenticated_redirects(build_state):
    st = build_state(PointsState)
    assert st.on_load() is not None


# ---- 场次创建 ----------------------------------------------------------------


def test_admin_create_event(build_state, make_user, roster):
    st = build_state(AdminPointsState, make_user("root", role="admin"))
    st.set_form_title("九月团队赛")
    st.set_form_date("2025-09-10")
    st.set_form_entity("team")
    st.set_form_max_value("10")
    st.set_form_n_teams("5")
    st.create_event()
    assert st.admin_error == "" and st.admin_feedback != ""
    events = st.events
    assert len(events) == 1 and events[0]["entity_label"] == "队伍赛"


def test_admin_create_event_invalid_date(build_state, make_user, roster):
    st = build_state(AdminPointsState, make_user("root", role="admin"))
    st.set_form_title("坏日期")
    st.set_form_date("2025/09/10")
    st.set_form_max_value("10")
    st.set_form_n_teams("5")
    st.create_event()
    assert "YYYY-MM-DD" in st.admin_error
    assert st.events == []


# ---- 认证工作流 ----------------------------------------------------------------


def test_player_claim_and_approve(build_state, make_user, roster):
    event = _make_event()
    member = make_user("alice", bound_player_id="p1")
    st = build_state(PointsState, member)

    st.set_claim_event_id(f"{event.id}. 测试积分场")
    st.set_claim_value("8")
    st.set_claim_rank("2")
    st.submit_claim()
    assert st.claim_error == "" and st.claim_feedback != ""
    assert len(st.my_claims) == 1 and st.my_claims[0]["status"] == "staged"

    admin_user = make_user("root", role="admin")
    admin = build_state(AdminPointsState, admin_user)
    assert admin.pending_count == 1
    admin.approve(st.my_claims[0]["id"])
    assert admin.admin_error == ""
    assert admin.pending_count == 0

    entries = roster.scalars(select(PointsEntry)).all()
    assert len(entries) == 1
    assert entries[0].owner_id == "p1" and entries[0].points == pytest.approx(64.0)

    claims = roster.scalars(select(PointsClaim)).all()
    assert claims[0].status == "approved" and claims[0].decided_by == admin_user[0]


def test_submit_claim_unbound_error(build_state, make_user, roster):
    event = _make_event()
    st = build_state(PointsState, make_user("alice"))  # 未绑定
    st.set_claim_event_id(f"{event.id}. 测试积分场")
    st.set_claim_value("8")
    st.set_claim_rank("2")
    st.submit_claim()
    assert "绑定" in st.claim_error


def test_team_claim_shared_points(build_state, make_user, roster):
    event = _make_event(entity="team")
    member = make_user("alice", bound_player_id="p1")
    st = build_state(PointsState, member)

    st.set_claim_event_id(f"{event.id}. 测试积分场")
    st.set_claim_team_id("t1. 一队")
    st.set_claim_value("7")
    st.set_claim_rank("1")
    st.submit_claim()
    assert st.claim_error == ""

    admin = build_state(AdminPointsState, make_user("root", role="admin"))
    claim_id = admin.staged_claims[0]["id"]
    admin.approve(claim_id)
    assert admin.admin_error == ""

    entries = roster.scalars(select(PointsEntry)).all()
    assert len(entries) == 3  # 1 team（t1 两名成员）+ 2 player
    assert {e.owner_type for e in entries} == {"team", "player"}
    player_rows = [e for e in entries if e.owner_type == "player"]
    assert {row.owner_id for row in player_rows} == {"p1", "p2"}
    assert all(row.team_context == "t1" for row in entries)


def test_team_claim_rejected_for_non_member(build_state, make_user, roster):
    event = _make_event(entity="team")
    outsider = make_user("mallory", bound_player_id="p3")  # p3 不在 t1
    st = build_state(PointsState, outsider)
    st.set_claim_event_id(f"{event.id}. 测试积分场")
    st.set_claim_team_id("t1. 一队")
    st.set_claim_value("7")
    st.set_claim_rank("1")
    st.submit_claim()
    assert "现役成员" in st.claim_error


# ---- 榜单 ------------------------------------------------------------------


def test_leaderboard_vars(build_state, make_user, roster):
    event = _make_event()
    member = make_user("alice", bound_player_id="p1")
    st = build_state(PointsState, member)
    st.set_claim_event_id(f"{event.id}. 测试积分场")
    st.set_claim_value("8")
    st.set_claim_rank("2")
    st.submit_claim()
    admin = build_state(AdminPointsState, make_user("root", role="admin"))
    admin.approve(st.my_claims[0]["id"])

    individuals = st.individual_board
    assert len(individuals) == 1
    assert individuals[0]["name"] == "张三" and individuals[0]["points"] == "64.0"
    assert st.team_board == []  # 个人赛不产生团队积分
