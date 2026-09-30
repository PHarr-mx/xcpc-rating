"""points 模块测试：公式 / 认证工作流 / 双账本与队伍复合分（RATING_FORMULA_PLAN §9）。"""

import json
from datetime import date

import pytest
from sqlalchemy import select

from xcpc_core.db.tables import AuditLog, Player, PointsEntry, Team, TeamAlias, TeamMember
from xcpc_core.points import api as points_api
from xcpc_core.points.exceptions import (
    ClaimNotFoundError,
    ClaimStateError,
    DuplicateClaimError,
    EventNotFoundError,
    InvalidClaimError,
    NotTeamMemberError,
    PointsError,
)
from xcpc_core.points.formula import compute_points
from xcpc_core.points.models import PointsClaimCreate, PointsEventCreate, PointsEventUpdate

D1 = date(2025, 9, 10)
D2 = date(2025, 10, 8)

_NAMES = {"p1": "张三", "p2": "李四", "p3": "王五", "p9": "刘六"}


def _add_player(session, pid: str) -> None:
    session.add(Player(id=pid, name=_NAMES.get(pid, pid)))
    session.commit()


def _add_team(session, team_id: str, member_ids: list[str], alias: str = "一队") -> None:
    session.add(Team(id=team_id, member_key="|".join(member_ids), size=len(member_ids)))
    for seat, pid in enumerate(member_ids, start=1):
        session.add(TeamMember(team_id=team_id, player_id=pid, seat=seat))
    session.add(TeamAlias(team_id=team_id, alias=alias))
    session.commit()


def _event_params(entity: str = "player", **overrides) -> PointsEventCreate:
    base = dict(title="省赛积分场", date=D1, entity=entity, kind="solved", max_value=12, n_teams=10)
    base.update(overrides)
    return PointsEventCreate(**base)


# ---- 公式 ------------------------------------------------------------------


def test_compute_points_known_values():
    assert compute_points(value=12, rank=1, max_value=12, n_teams=12) == pytest.approx(100.0)
    assert compute_points(value=6, rank=6, max_value=12, n_teams=12) == pytest.approx(100 * 0.5 * 7 / 12)
    assert compute_points(value=1, rank=12, max_value=12, n_teams=12) == pytest.approx(100 / 144)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"value": 0, "rank": 1, "max_value": 12, "n_teams": 12},  # 资格线
        {"value": 5, "rank": 0, "max_value": 12, "n_teams": 12},
        {"value": 5, "rank": 13, "max_value": 12, "n_teams": 12},
        {"value": 5, "rank": 1, "max_value": 0, "n_teams": 12},
        {"value": 5, "rank": 1, "max_value": 12, "n_teams": 0},
    ],
)
def test_compute_points_rejects_invalid(kwargs):
    with pytest.raises(ValueError):
        compute_points(**kwargs)


# ---- 场次 ------------------------------------------------------------------


def test_create_and_list_event(db_session):
    view = points_api.create_event(session=db_session, params=_event_params(), created_by=1)
    assert view.id > 0 and view.claims_total == 0
    assert [e.id for e in points_api.list_events(session=db_session)] == [view.id]


def test_event_create_validation(db_session):
    with pytest.raises(ValueError, match="title"):
        points_api.create_event(session=db_session, params=_event_params(title="  "), created_by=1)
    with pytest.raises(ValueError):
        points_api.create_event(session=db_session, params=_event_params(max_value=0), created_by=1)


def test_update_event(db_session):
    view = points_api.create_event(session=db_session, params=_event_params(), created_by=1)
    updated = points_api.update_event(
        session=db_session, event_id=view.id, params=PointsEventUpdate(max_value=15, title="  改名  ")
    )
    assert updated.max_value == 15 and updated.title == "改名"
    with pytest.raises(EventNotFoundError):
        points_api.update_event(session=db_session, event_id=999, params=PointsEventUpdate(max_value=15))
    with pytest.raises(InvalidClaimError, match="没有需要更新"):
        points_api.update_event(session=db_session, event_id=view.id, params=PointsEventUpdate())


# ---- 认证提交 --------------------------------------------------------------


def test_player_claim_flow(db_session):
    _add_player(db_session, "p1")
    event = points_api.create_event(session=db_session, params=_event_params(), created_by=1)

    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(event_id=event.id, value=8, rank=2),
        submitted_by=10,
        submitter_player_id="p1",
    )
    assert claim.status == "staged" and claim.player_name == "张三" and claim.entity == "player"
    assert claim.player_id == "p1"  # 认证主体即服务端传入的绑定选手，无“代他人提交”路径

    with pytest.raises(DuplicateClaimError):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(event_id=event.id, value=5, rank=3),
            submitted_by=10,
            submitter_player_id="p1",
        )
    with pytest.raises(InvalidClaimError, match="max_value"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(event_id=event.id, value=13, rank=3),
            submitted_by=10,
            submitter_player_id="p1",
        )
    with pytest.raises(InvalidClaimError, match="n_teams"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(event_id=event.id, value=5, rank=11),
            submitted_by=10,
            submitter_player_id="p1",
        )


def test_team_claim_requires_membership(db_session):
    for pid in ("p1", "p2", "p3", "p9"):
        _add_player(db_session, pid)
    _add_team(db_session, "t1", ["p1", "p2", "p3"])
    event = points_api.create_event(session=db_session, params=_event_params(entity="team", max_value=10, n_teams=5), created_by=1)

    with pytest.raises(NotTeamMemberError):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(event_id=event.id, value=7, rank=1, team_id="t1"),
            submitted_by=10,
            submitter_player_id="p9",
        )
    with pytest.raises(InvalidClaimError, match="队伍"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(event_id=event.id, value=7, rank=1, team_id="t999"),
            submitted_by=10,
            submitter_player_id="p1",
        )

    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(event_id=event.id, value=7, rank=1, team_id="t1"),
        submitted_by=10,
        submitter_player_id="p1",
    )
    assert claim.team_name == "一队" and claim.entity == "team"
    with pytest.raises(DuplicateClaimError):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(event_id=event.id, value=6, rank=2, team_id="t1"),
            submitted_by=10,
            submitter_player_id="p2",
        )


def test_solo_event_rejects_team_field(db_session):
    event = points_api.create_event(session=db_session, params=_event_params(), created_by=1)
    with pytest.raises(InvalidClaimError, match="个人赛"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(event_id=event.id, value=5, rank=1, team_id="t1"),
            submitted_by=10,
            submitter_player_id="p1",
        )


# ---- 审核 ------------------------------------------------------------------


def test_review_player_claim_writes_entry_and_audit(db_session):
    _add_player(db_session, "p1")
    event = points_api.create_event(session=db_session, params=_event_params(), created_by=1)
    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(event_id=event.id, value=8, rank=2),
        submitted_by=10,
        submitter_player_id="p1",
    )

    reviewed = points_api.review_claim(session=db_session, claim_id=claim.id, decision="approved", decided_by=99)
    assert reviewed.status == "approved" and reviewed.decided_by == 99

    entries = db_session.scalars(select(PointsEntry)).all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.owner_type == "player" and entry.owner_id == "p1" and entry.team_context is None
    assert entry.points == pytest.approx(compute_points(value=8, rank=2, max_value=12, n_teams=10))
    snapshot = json.loads(entry.payload_json)
    assert snapshot == {"value": 8, "rank": 2, "max_value": 12, "n_teams": 10}

    audit = db_session.scalars(select(AuditLog)).all()
    assert len(audit) == 1 and audit[0].action == "points.approve" and audit[0].user_id == 99

    with pytest.raises(ClaimStateError):
        points_api.review_claim(session=db_session, claim_id=claim.id, decision="rejected", decided_by=99)


def test_review_team_claim_shared_three(db_session):
    for pid in ("p1", "p2", "p3"):
        _add_player(db_session, pid)
    _add_team(db_session, "t1", ["p1", "p2", "p3"])
    event = points_api.create_event(session=db_session, params=_event_params(entity="team", max_value=10, n_teams=5), created_by=1)
    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(event_id=event.id, value=7, rank=1, team_id="t1"),
        submitted_by=10,
        submitter_player_id="p1",
    )

    points_api.review_claim(session=db_session, claim_id=claim.id, decision="approved", decided_by=99)

    entries = db_session.scalars(select(PointsEntry)).all()
    assert len(entries) == 4  # 1 team + 3 player（三人共享全额）
    team_rows = [e for e in entries if e.owner_type == "team"]
    player_rows = [e for e in entries if e.owner_type == "player"]
    assert len(team_rows) == 1 and team_rows[0].owner_id == "t1"
    assert {row.owner_id for row in player_rows} == {"p1", "p2", "p3"}
    assert all(row.team_context == "t1" for row in entries)
    assert all(row.points == pytest.approx(70.0) for row in entries)  # 100×(7/10)×(5/5)


def test_reject_writes_no_entries_and_allows_resubmit(db_session):
    _add_player(db_session, "p1")
    event = points_api.create_event(session=db_session, params=_event_params(), created_by=1)
    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(event_id=event.id, value=3, rank=5),
        submitted_by=10,
        submitter_player_id="p1",
    )
    reviewed = points_api.review_claim(session=db_session, claim_id=claim.id, decision="rejected", decided_by=99)
    assert reviewed.status == "rejected"
    assert db_session.scalars(select(PointsEntry)).all() == []
    assert db_session.scalars(select(AuditLog)).all()[0].action == "points.reject"

    resubmitted = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(event_id=event.id, value=8, rank=2),
        submitted_by=10,
        submitter_player_id="p1",
    )
    assert resubmitted.status == "staged"


def test_review_unknown_claim(db_session):
    with pytest.raises(ClaimNotFoundError):
        points_api.review_claim(session=db_session, claim_id=999, decision="approved", decided_by=99)


# ---- 榜单 ------------------------------------------------------------------


def test_individual_leaderboard_excludes_left(db_session):
    for pid in ("p1", "p2", "p4"):
        _add_player(db_session, pid)
    p4 = db_session.get(Player, "p4")
    p4.status = "left"  # 离队：认证有效但不出榜
    db_session.commit()
    event = points_api.create_event(session=db_session, params=_event_params(), created_by=1)

    for pid, value, rank in (("p1", 8, 2), ("p2", 5, 5), ("p4", 10, 1)):
        claim = points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(event_id=event.id, value=value, rank=rank),
            submitted_by=10,
            submitter_player_id=pid,
        )
        points_api.review_claim(session=db_session, claim_id=claim.id, decision="approved", decided_by=99)

    board = points_api.individual_leaderboard(session=db_session)
    assert [row.player_id for row in board] == ["p1", "p2"]  # p4 已离队，不出榜
    assert board[0].points == pytest.approx(60.0)  # 100×(8/12)×(9/10)
    assert board[1].points == pytest.approx(25.0)  # 100×(5/12)×(6/10)
    assert all(row.rank == i + 1 for i, row in enumerate(board))


def test_team_composite_excludes_own_team_points(db_session):
    """§9.3 例：T1 三人团队赛 70 分/人 + p1 个人赛 50 分。

    团队积分 70；p1 队外 50、p2/p3 队外 0 → 复合分 = 0.6×70 + 0.4×50 = 62。
    """
    for pid in ("p1", "p2", "p3"):
        _add_player(db_session, pid)
    _add_team(db_session, "t1", ["p1", "p2", "p3"])
    team_event = points_api.create_event(
        session=db_session, params=_event_params(entity="team", max_value=10, n_teams=5), created_by=1
    )
    solo_event = points_api.create_event(
        session=db_session, params=_event_params(title="个人训练赛", entity="player", max_value=10, n_teams=5), created_by=1
    )

    team_claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(event_id=team_event.id, value=7, rank=1, team_id="t1"),
        submitted_by=10,
        submitter_player_id="p1",
    )
    points_api.review_claim(session=db_session, claim_id=team_claim.id, decision="approved", decided_by=99)
    solo_claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(event_id=solo_event.id, value=5, rank=1),
        submitted_by=10,
        submitter_player_id="p1",
    )
    points_api.review_claim(session=db_session, claim_id=solo_claim.id, decision="approved", decided_by=99)

    board = points_api.team_leaderboard(session=db_session)
    assert len(board) == 1
    row = board[0]
    assert row.name == "一队"
    assert row.team_points == pytest.approx(70.0)
    assert row.member_points == pytest.approx(50.0)  # p1 的 50 + p2/p3 的 0
    assert row.composite == pytest.approx(0.6 * 70 + 0.4 * 50)
    assert set(row.members) == {"张三", "李四", "王五"}

    individuals = points_api.individual_leaderboard(session=db_session)
    assert individuals[0].player_id == "p1" and individuals[0].points == pytest.approx(120.0)
    assert [row.player_id for row in individuals] == ["p1", "p2", "p3"]


def test_leaderboard_window_filter(db_session):
    _add_player(db_session, "p1")
    e1 = points_api.create_event(session=db_session, params=_event_params(title="九月场"), created_by=1)
    e2 = points_api.create_event(session=db_session, params=_event_params(title="十月场", date=D2), created_by=1)
    for event, value in ((e1, 8), (e2, 10)):
        claim = points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(event_id=event.id, value=value, rank=1),
            submitted_by=10,
            submitter_player_id="p1",
        )
        points_api.review_claim(session=db_session, claim_id=claim.id, decision="approved", decided_by=99)

    assert points_api.individual_leaderboard(session=db_session, start=D2)[0].points == pytest.approx(
        100 * 10 / 12
    )  # 十月场：value=10 rank=1 → 100×(10/12)×(10/10)
    assert points_api.individual_leaderboard(session=db_session, end=D1)[0].points == pytest.approx(
        compute_points(value=8, rank=1, max_value=12, n_teams=10)
    )
    assert points_api.individual_leaderboard(session=db_session, start=date(2026, 1, 1)) == []


def test_config_change_does_not_affect_recorded_points(db_session):
    """改配置不溯及：已记流水的分值不变，后续审核用新参数。"""
    _add_player(db_session, "p1")
    event = points_api.create_event(session=db_session, params=_event_params(), created_by=1)
    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(event_id=event.id, value=6, rank=1),
        submitted_by=10,
        submitter_player_id="p1",
    )
    points_api.review_claim(session=db_session, claim_id=claim.id, decision="approved", decided_by=99)
    before = db_session.scalars(select(PointsEntry)).all()[0].points

    points_api.update_event(session=db_session, event_id=event.id, params=PointsEventUpdate(max_value=24))

    entry = db_session.scalars(select(PointsEntry)).all()[0]
    assert entry.points == pytest.approx(before)  # 100×(6/12)×(10/10) = 50
    assert json.loads(entry.payload_json)["max_value"] == 12  # 快照保留旧参数
