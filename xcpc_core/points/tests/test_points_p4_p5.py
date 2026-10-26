"""P4 免认证直录 + P5 防刷上限（赛年最好 N 场）。"""

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


# ---- P5 防刷上限 -----------------------------------------------------------


def _seed_many_entries(db_session, *, player_id: str = "p1", points_list: list[tuple[date, float]]):
    """直接写流水（避开赛程构造），用于验证聚合规则。"""
    for index, (day, value) in enumerate(points_list):
        db_session.add(
            PointsEntry(
                owner_type="player",
                owner_id=player_id,
                points=value,
                contest_id=f"seed_{player_id}_{index}",
                claim_id=None,
                team_context=None,
                payload_json=json.dumps({}),
                date=day,
            )
        )
    db_session.commit()


def test_best_n_none_keeps_full_sum(db_session):
    _add_player(db_session, "p1")
    _seed_many_entries(db_session, points_list=[(date(2025, 10, 1), 50.0), (date(2025, 11, 1), 30.0)])

    rows = points_api.individual_leaderboard(session=db_session)
    assert rows[0].points == pytest.approx(80.0)


def test_best_n_takes_top_scores_not_earliest(db_session):
    """UCup 降序哲学：取分值最高的 N 场，而非最早报名的 N 场。"""
    _add_player(db_session, "p1")
    _seed_many_entries(
        db_session,
        points_list=[(date(2025, 9, 1), 10.0), (date(2025, 10, 1), 90.0), (date(2025, 11, 1), 50.0)],
    )

    rows = points_api.individual_leaderboard(session=db_session, best_n=2)
    assert rows[0].points == pytest.approx(140.0), "90 + 50，而非 10 + 90"


def test_best_n_applies_per_competition_year(db_session):
    """赛年独立择优：2025 赛年取 2 场，2026 赛年也取 2 场，两赛年相加。"""
    _add_player(db_session, "p1")
    _seed_many_entries(
        db_session,
        points_list=[
            (date(2025, 9, 1), 10.0),   # 2025 赛年
            (date(2025, 10, 1), 90.0),  # 2025 赛年
            (date(2025, 11, 1), 50.0),  # 2025 赛年
            (date(2026, 10, 1), 70.0),  # 2026 赛年（9 月起）
            (date(2026, 11, 1), 20.0),  # 2026 赛年
        ],
    )

    rows = points_api.individual_leaderboard(session=db_session, best_n=2)
    # 2025 赛年 top2 = 90 + 50 = 140；2026 赛年 top2 = 70 + 20 = 90 → 230
    assert rows[0].points == pytest.approx(230.0)


def test_best_n_does_not_change_order_when_none(db_session):
    for pid in ("p1", "p2"):
        _add_player(db_session, pid)
    _seed_many_entries(db_session, player_id="p1", points_list=[(date(2025, 10, 1), 40.0)])
    _seed_many_entries(db_session, player_id="p2", points_list=[(date(2025, 10, 1), 60.0)])

    rows = points_api.individual_leaderboard(session=db_session, best_n=None)
    assert [row.player_id for row in rows] == ["p2", "p1"]


def test_best_n_can_change_ranking(db_session):
    """择优会改变排序：场次多但单场低的人，可能被场次少但高分的人反超。"""
    for pid in ("p1", "p2"):
        _add_player(db_session, pid)
    # p1：三场各 30 → 总和 90；best_n=1 时 30
    _seed_many_entries(
        db_session, player_id="p1",
        points_list=[(date(2025, 9, 1), 30.0), (date(2025, 10, 1), 30.0), (date(2025, 11, 1), 30.0)],
    )
    # p2：一场 50 → 总和 50；best_n=1 时 50
    _seed_many_entries(db_session, player_id="p2", points_list=[(date(2025, 10, 1), 50.0)])

    unlimited = points_api.individual_leaderboard(session=db_session)
    assert [row.player_id for row in unlimited] == ["p1", "p2"], "不设限时 p1 靠数量领先"

    capped = points_api.individual_leaderboard(session=db_session, best_n=1)
    assert [row.player_id for row in capped] == ["p2", "p1"], "择优后 p2 单场更高领先"


def test_team_leaderboard_accepts_best_n(db_session):
    for pid in ("p1", "p2"):
        _add_player(db_session, pid)
    _add_team(db_session, "t1", ["p1", "p2"])
    db_session.add(
        PointsEntry(
            owner_type="team",
            owner_id="t1",
            points=100.0,
            contest_id="seed_t1",
            claim_id=None,
            team_context="t1",
            payload_json=json.dumps({}),
            date=date(2025, 10, 1),
        )
    )
    db_session.commit()

    rows = points_api.team_leaderboard(session=db_session, best_n=3)
    assert len(rows) == 1
    assert rows[0].team_points == pytest.approx(100.0)

# ---- best_n 配置读取 --------------------------------------------------------


def test_load_best_n_returns_none_when_unset(db_session, tmp_path, monkeypatch):
    from xcpc_core.points import service as points_service

    assert points_service.load_best_n(repo_root=tmp_path) is None


def test_load_best_n_reads_yaml(tmp_path):
    from xcpc_core.points import service as points_service

    (tmp_path / "data/config").mkdir(parents=True)
    (tmp_path / "data/config/points.yaml").write_text("best_n: 8\n", encoding="utf-8")
    assert points_service.load_best_n(repo_root=tmp_path) == 8


def test_load_best_n_rejects_invalid(tmp_path):
    from xcpc_core.points import service as points_service

    (tmp_path / "data/config").mkdir(parents=True)
    (tmp_path / "data/config/points.yaml").write_text("best_n: 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="best_n"):
        points_service.load_best_n(repo_root=tmp_path)
