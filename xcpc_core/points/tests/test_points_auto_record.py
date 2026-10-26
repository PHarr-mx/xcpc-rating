"""P4 免认证直录。

P5「赛年最好 N 场」曾实现后移除（2026-10-26 决策）：积分制是投入度的度量，
多参赛本身就是水平与意愿的体现，用场次上限压制它与设计意图冲突。
榜单回到「全部流水直加」。
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import select

from xcpc_core.contest import api as contest_api
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.tables import AuditLog, Player, PointsClaim, PointsEntry, Team, TeamMember
from xcpc_core.points import api as points_api
from xcpc_core.points.exceptions import ClaimNotFoundError, InvalidClaimError
from xcpc_core.points.formula import compute_points

_NAMES = {"p1": "张三", "p2": "李四", "p3": "王五", "p4": "赵六"}


def _add_player(session, pid: str) -> None:
    session.add(Player(id=pid, name=_NAMES.get(pid, pid)))
    session.commit()


def _add_team(session, team_id: str, member_ids: list[str]) -> None:
    session.add(Team(id=team_id, member_key="|".join(member_ids), size=len(member_ids)))
    for seat, pid in enumerate(member_ids, start=1):
        session.add(TeamMember(team_id=team_id, player_id=pid, seat=seat))
    session.commit()


def _contest_with_standings(
    session,
    *,
    contest_id: str,
    day: date,
    entity: str = "player",
    rows: list[dict] | None = None,
    max_value: int = 12,
    n_teams: int = 10,
    counts_for_points: bool = True,
) -> str:
    """带成绩行的可计分比赛（P4 直录从 standings 生成）。"""
    contest_api.configure_store(ContestStore(session))
    saved = contest_api.save_contest(ContestCreate(
        id=contest_id,
        title=f"直录场 {contest_id}",
        date=day,
        format="icpc",
        entity=entity,  # type: ignore[arg-type]
        max_value=max_value,
        n_teams=n_teams,
        counts_for_points=counts_for_points,
        counts_for_ranking=False,
        standings=[
            Standing(**row) for row in (rows or [])
        ],
    ))
    return saved.id


# ---- P4 直录 ---------------------------------------------------------------


def test_auto_record_player_contest(db_session):
    _add_player(db_session, "p1")
    _contest_with_standings(
        db_session,
        contest_id="auto_p",
        day=date(2025, 9, 10),
        rows=[{"team_name": "张三", "rank": 1, "solved": 8, "player_ids": ["p1"]}],
    )

    views = points_api.auto_record_contest_points(
        contest_id="auto_p", created_by=1, session=db_session
    )

    assert len(views) == 1
    assert views[0].status == "approved"
    entries = db_session.scalars(select(PointsEntry)).all()
    assert len(entries) == 1
    assert entries[0].owner_type == "player"
    expected = compute_points(value=8, rank=1, max_value=12, n_teams=10)
    assert entries[0].points == pytest.approx(expected)


def test_auto_record_team_contest_writes_double_ledger(db_session):
    for pid in ("p1", "p2", "p3"):
        _add_player(db_session, pid)
    _add_team(db_session, "t1", ["p1", "p2", "p3"])
    _contest_with_standings(
        db_session,
        contest_id="auto_t",
        day=date(2025, 9, 10),
        entity="team",
        rows=[{"team_id": "t1", "team_name": "一队", "rank": 2, "solved": 7,
               "player_ids": ["p1", "p2", "p3"]}],
    )

    points_api.auto_record_contest_points(contest_id="auto_t", created_by=1, session=db_session)

    entries = db_session.scalars(select(PointsEntry)).all()
    assert len(entries) == 4, "1 条 team + 3 条 player 双账本"
    assert sum(1 for e in entries if e.owner_type == "team") == 1
    assert all(e.team_context == "t1" for e in entries if e.owner_type == "player")


def test_auto_record_is_idempotent(db_session):
    _add_player(db_session, "p1")
    _contest_with_standings(
        db_session,
        contest_id="auto_idem",
        day=date(2025, 9, 10),
        rows=[{"team_name": "张三", "rank": 1, "solved": 8, "player_ids": ["p1"]}],
    )

    points_api.auto_record_contest_points(contest_id="auto_idem", created_by=1, session=db_session)
    first = db_session.scalars(select(PointsEntry)).all()
    assert len(first) == 1

    points_api.auto_record_contest_points(contest_id="auto_idem", created_by=1, session=db_session)
    second = db_session.scalars(select(PointsEntry)).all()
    assert len(second) == 1, "重复直录应替换而非累加"
    assert len(db_session.scalars(select(PointsClaim)).all()) == 1


def test_auto_record_writes_audit(db_session):
    _add_player(db_session, "p1")
    _contest_with_standings(
        db_session,
        contest_id="auto_audit",
        day=date(2025, 9, 10),
        rows=[{"team_name": "张三", "rank": 1, "solved": 8, "player_ids": ["p1"]}],
    )
    points_api.auto_record_contest_points(contest_id="auto_audit", created_by=42, session=db_session)

    logs = db_session.scalars(select(AuditLog).where(AuditLog.action == "points.auto_record")).all()
    assert len(logs) == 1
    assert logs[0].user_id == 42


def test_auto_record_requires_points_capable_contest(db_session):
    _contest_with_standings(
        db_session,
        contest_id="auto_nopts",
        day=date(2025, 9, 10),
        rows=[{"team_name": "张三", "rank": 1, "solved": 8}],
        counts_for_points=False,
    )
    with pytest.raises(InvalidClaimError, match="未开启记积分"):
        points_api.auto_record_contest_points(
            contest_id="auto_nopts", created_by=1, session=db_session
        )


def test_auto_record_requires_standings(db_session):
    _contest_with_standings(db_session, contest_id="auto_empty", day=date(2025, 9, 10), rows=[])
    with pytest.raises(InvalidClaimError, match="没有成绩行"):
        points_api.auto_record_contest_points(
            contest_id="auto_empty", created_by=1, session=db_session
        )


def test_auto_record_unknown_contest(db_session):
    with pytest.raises(ClaimNotFoundError):
        points_api.auto_record_contest_points(
            contest_id="nope", created_by=1, session=db_session
        )


def test_auto_record_does_not_touch_manual_claims(db_session):
    """直录的 replace 只能清系统生成的 claim，不能动选手手工提交的。"""
    _add_player(db_session, "p1")
    _add_player(db_session, "p2")
    _contest_with_standings(
        db_session,
        contest_id="auto_mixed",
        day=date(2025, 9, 10),
        rows=[{"team_name": "张三", "rank": 1, "solved": 8, "player_ids": ["p1"]}],
    )
    # 手工提交一条（staged）
    from xcpc_core.points.models import PointsClaimCreate

    points_api.submit_claim(
        params=PointsClaimCreate(contest_id="auto_mixed", value=5, rank=2),
        submitted_by=9,
        submitter_player_id="p2",
        session=db_session,
    )
    points_api.auto_record_contest_points(
        contest_id="auto_mixed", created_by=1, session=db_session
    )

    claims = db_session.scalars(select(PointsClaim)).all()
    notes = {claim.note for claim in claims}
    assert "系统直录（免认证）" in notes
    assert any(claim.status == "staged" for claim in claims), "手工 claim 应保留"
