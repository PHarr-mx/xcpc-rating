"""P4c admin 比赛管理回归（统一比赛模型）。"""

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
    title: str = "测试正式赛",
) -> ContestCreate:
    return ContestCreate(
        id=contest_id,
        title=title,
        date=date(2026, 5, 18),
        format="icpc",
        entity="team",
        n_teams=20,
        school_teams_count=3,
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


def test_admin_can_search_contests_by_text(build_state, make_user, core_store):
    contest_api.save_contest(make_contest("formal_1", title="四川省赛"))
    contest_api.save_contest(make_contest("training_1", title="春季训练赛"))
    state = build_state(AdminContestsState, make_user("root", role="admin"))

    assert [item["id"] for item in state.contests] == ["formal_1", "training_1"]
    state.set_search("春季")
    assert [item["id"] for item in state.contests] == ["training_1"]


def test_admin_create_contest_via_unified_form(build_state, make_user, core_store):
    from xcpc_core.tier import api as tier_api
    from xcpc_core.tier.models import TierCreate

    tier = tier_api.create_tier(TierCreate(name="ICPC 省赛", coefficient=0.7))
    state = build_state(AdminContestsState, make_user("root", role="admin"))
    state.set_form_contest_id("new_c1")
    state.set_form_title("新比赛")
    state.set_form_date("2026-05-18")
    state.set_form_tier(f"{tier.id}. ICPC 省赛")
    state.set_form_n_teams("12")
    state.set_form_max_value("9")
    state.set_form_counts_for_points(True)
    state.set_form_counts_for_ranking(False)
    state.create_contest()

    assert state.admin_error == "" and state.admin_feedback != ""
    saved = contest_api.get_contest("new_c1").contest
    assert saved.tier_id == tier.id
    assert saved.counts_for_points is True and saved.counts_for_ranking is False
    assert saved.max_value == 9 and saved.n_teams == 12


def test_admin_delete_contest_cascades_standings_and_audits(
    build_state, make_user, core_store
):
    contest = contest_api.save_contest(make_contest("c1", title="待删除比赛"))
    core_store.add(
        RatingEvent(
            event_id="c1#standing#p001",
            source_type="contest",
            player_id="p001",
            team_id="t001",
            date=date(2026, 5, 18),
            competition_year=2025,
            season="2026-春学期",
            contest_type="测试等级",
            contest_format="icpc",
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
