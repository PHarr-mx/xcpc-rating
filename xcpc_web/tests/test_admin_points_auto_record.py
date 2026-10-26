"""P4 免认证直录的 Web 入口（/admin/points 批量直录卡片）。"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from xcpc_core.contest import api as contest_api
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.db.tables import AuditLog, Player, PointsClaim, PointsEntry, Team, TeamMember

from xcpc_web.states.admin.points import AdminPointsState


@pytest.fixture
def seeded(core_store):
    s = core_store
    s.add_all([Player(id="p1", name="张三"), Player(id="p2", name="李四"), Player(id="p3", name="王五")])
    s.add(Team(id="t1", member_key="p1|p2", size=2))
    s.add(TeamMember(team_id="t1", player_id="p1", seat=1))
    s.add(TeamMember(team_id="t1", player_id="p2", seat=2))
    s.commit()

    contest_api.save_contest(ContestCreate(
        id="auto_c1",
        title="省赛直录场",
        date=date(2025, 9, 10),
        format="icpc",
        entity="team",
        max_value=10,
        n_teams=5,
        counts_for_points=True,
        counts_for_ranking=False,
        standings=[
            Standing(team_id="t1", team_name="一队", rank=1, solved=9,
                     player_ids=["p1", "p2"]),
        ],
    ))
    return s


def test_non_admin_cannot_auto_record(build_state, make_user, seeded):
    st = build_state(AdminPointsState, make_user("alice"))
    assert st.auto_record() is not None
    assert st.points_contests == []


def test_points_contests_lists_only_points_capable(build_state, make_user, seeded):
    contest_api.save_contest(ContestCreate(
        id="rank_only",
        title="只计排名",
        date=date(2025, 10, 1),
        format="icpc",
        entity="player",
        counts_for_points=False,
        counts_for_ranking=True,
    ))
    st = build_state(AdminPointsState, make_user("root", role="admin"))
    ids = [item["id"] for item in st.points_contests]
    assert "auto_c1" in ids
    assert "rank_only" not in ids


def test_auto_record_creates_approved_entries(build_state, make_user, seeded):
    st = build_state(AdminPointsState, make_user("root", role="admin"))
    st.set_auto_contest_id("auto_c1")
    assert st.auto_record() is None

    assert "已直录" in st.admin_feedback
    claims = seeded.scalars(select(PointsClaim)).all()
    assert len(claims) == 1
    assert claims[0].status == "approved"
    # team + 2 player
    assert len(seeded.scalars(select(PointsEntry)).all()) == 3


def test_auto_record_requires_selection(build_state, make_user, seeded):
    st = build_state(AdminPointsState, make_user("root", role="admin"))
    st.auto_record()
    assert "请先选择" in st.admin_error


def test_auto_record_surfaces_core_error(build_state, make_user, seeded):
    st = build_state(AdminPointsState, make_user("root", role="admin"))
    st.set_auto_contest_id("no_such_contest")
    st.auto_record()
    assert st.admin_error != ""
    assert "不存在" in st.admin_error


def test_auto_record_respects_replace_flag(build_state, make_user, seeded):
    st = build_state(AdminPointsState, make_user("root", role="admin"))
    st.set_auto_contest_id("auto_c1")

    st.auto_record()
    assert len(seeded.scalars(select(PointsEntry)).all()) == 3

    # 关掉覆盖 → 再录一次会与既有 approved 认证冲突（唯一索引/前置校验）
    st.set_auto_replace(False)
    st.auto_record()
    assert st.admin_error != "", "不覆盖时应报重复，而不是静默累加"