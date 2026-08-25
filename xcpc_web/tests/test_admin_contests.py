"""P4c admin 比赛管理回归。"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from xcpc_core.audit import api as audit_api
from xcpc_core.contest import api as contest_api
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.db.tables import AuditLog, RatingEvent

from xcpc_web.states.admin.contests import AdminContestsState


def make_contest(
    contest_id: str,
    *,
    source_type: str = "formal",
    title: str = "测试正式赛",
) -> ContestCreate:
    return ContestCreate(
        id=contest_id,
        title=title,
        date=date(2026, 5, 18),
        source_type=source_type,
        contest_type="icpc_provincial" if source_type == "formal" else None,
        division="校内训练" if source_type == "training" else None,
        format="team_xcpc",
        total_teams=20,
        school_teams_count=3,
        weight=70,
        standings=[
            Standing(
                team_id="t001",
                team_name="一队",
                rank=1,
                award="gold",
                solved=8,
                penalty=600,
                player_ids=["p001", "p002"],
            )
        ],
    )


def test_non_admin_is_guarded_and_sees_no_contests(build_state, make_user, core_store):
    contest_api.save_contest(make_contest("c1"))
    state = build_state(AdminContestsState, make_user("member"))

    assert state.contests == []
    assert state.on_load() is not None


def test_admin_can_filter_contests_by_source_and_text(build_state, make_user, core_store):
    contest_api.save_contest(make_contest("formal_1", title="四川省赛"))
    contest_api.save_contest(
        make_contest("training_1", source_type="training", title="春季训练赛")
    )
    state = build_state(AdminContestsState, make_user("root", role="admin"))

    assert [item["id"] for item in state.contests] == ["formal_1", "training_1"]
    state.set_source_filter("formal")
    assert [item["id"] for item in state.contests] == ["formal_1"]
    state.set_source_filter("all")
    state.set_search("春季")
    assert [item["id"] for item in state.contests] == ["training_1"]


def test_admin_delete_contest_cascades_standings_and_audits(
    build_state, make_user, core_store
):
    contest = contest_api.save_contest(make_contest("c1", title="待删除比赛"))
    core_store.add(
        RatingEvent(
            event_id="c1#standing#p001",
            source_type="formal",
            player_id="p001",
            team_id="t001",
            date=date(2026, 5, 18),
            competition_year=2025,
            season="2026-春学期",
            contest_type="icpc_provincial",
            contest_format="team_xcpc",
            weight=70,
            payload_json="{}",
        )
    )
    core_store.commit()
    admin = make_user("root", role="admin")
    audit_api.configure_session(core_store)
    state = build_state(AdminContestsState, admin)

    state.delete_contest(contest.id)

    assert contest_api.list_contests() == []
    assert core_store.execute(select(RatingEvent)).scalars().all() == []
    with pytest.raises(Exception):
        contest_api.get_contest(contest.id)
    assert state.admin_feedback == "已删除比赛：待删除比赛（c1）"
    logs = core_store.execute(select(AuditLog)).scalars().all()
    assert [(log.action, log.target) for log in logs] == [("contest.delete", "c1")]
