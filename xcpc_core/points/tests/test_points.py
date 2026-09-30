"""points 模块测试：公式 / 认证工作流 / 双账本与队伍复合分（改挂统一比赛）。

场次即统一 contest（contest_api.save_contest 创建，counts_for_points=True +
max_value/n_teams 齐备 + allow_claims=True 才可申报）。
"""

import json
from datetime import date

import pytest
from sqlalchemy import select

from xcpc_core.contest import api as contest_api
from xcpc_core.contest.models import ContestCreate
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.tables import AuditLog, Player, PointsEntry, Team, TeamAlias, TeamMember
from xcpc_core.points import api as points_api
from xcpc_core.points.exceptions import (
    ClaimNotFoundError,
    ClaimStateError,
    DuplicateClaimError,
    InvalidClaimError,
    NotTeamMemberError,
    PointsError,
)
from xcpc_core.points.formula import compute_award_points, compute_points
from xcpc_core.points.models import PointsClaimCreate

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


def _contest(
    session,
    *,
    contest_id: str = "pts_001",
    entity: str = "player",
    scoring: str = "formula",
    max_value: int | None = 12,
    n_teams: int | None = 10,
    day: date = D1,
    title: str = "省赛积分场",
    allow_claims: bool = True,
    counts_for_points: bool = True,
    **kw,
) -> str:
    """创建可申报积分的比赛，返回 contest_id。"""
    if scoring == "formula" and counts_for_points and max_value is None:
        raise ValueError("formula 计分比赛必须提供 max_value")
    contest_api.configure_store(ContestStore(session))
    saved = contest_api.save_contest(ContestCreate(
        id=contest_id,
        title=title,
        date=day,
        format="icpc",
        entity=entity,  # type: ignore[arg-type]
        scoring=scoring,  # type: ignore[arg-type]
        max_value=max_value,
        n_teams=n_teams,
        allow_claims=allow_claims,
        counts_for_points=counts_for_points,
        counts_for_ranking=False,
        **kw,
    ))
    return saved.id


# ---- 公式 ------------------------------------------------------------------


def test_compute_points_known_values():
    assert compute_points(value=12, rank=1, max_value=12, n_teams=12) == pytest.approx(100.0)
    assert compute_points(value=6, rank=6, max_value=12, n_teams=12) == pytest.approx(100 * 0.5 * 7 / 12)
    assert compute_points(value=1, rank=12, max_value=12, n_teams=12) == pytest.approx(100 / 144)
    assert compute_points(value=12, rank=1, max_value=12, n_teams=12, coefficient=0.7) == pytest.approx(70.0)


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


def test_compute_award_points():
    assert compute_award_points(base_points=100.0, coefficient=0.7) == pytest.approx(70.0)
    assert compute_award_points(base_points=30.0) == pytest.approx(30.0)
    with pytest.raises(ValueError):
        compute_award_points(base_points=-1)
    with pytest.raises(ValueError):
        compute_award_points(base_points=10, coefficient=0)


# ---- 认证提交（formula 场次）------------------------------------------------


def test_player_claim_flow(db_session):
    _add_player(db_session, "p1")
    cid = _contest(db_session)

    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=cid, value=8, rank=2),
        submitted_by=10,
        submitter_player_id="p1",
    )
    assert claim.status == "staged" and claim.player_name == "张三" and claim.entity == "player"
    assert claim.player_id == "p1"  # 认证主体即服务端传入的绑定选手，无“代他人提交”路径
    assert claim.contest_title == "省赛积分场"

    with pytest.raises(DuplicateClaimError):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=5, rank=3),
            submitted_by=10,
            submitter_player_id="p1",
        )
    with pytest.raises(InvalidClaimError, match="max_value"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=13, rank=3),
            submitted_by=10,
            submitter_player_id="p1",
        )
    with pytest.raises(InvalidClaimError, match="n_teams"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=5, rank=11),
            submitted_by=10,
            submitter_player_id="p1",
        )


def test_claim_requires_points_capable_contest(db_session):
    """不计积分 / 不允许申报的比赛不可提交认证。"""
    _add_player(db_session, "p1")
    no_points = _contest(db_session, contest_id="pts_np", counts_for_points=False)
    with pytest.raises(InvalidClaimError, match="不计入积分"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=no_points, value=5, rank=1),
            submitted_by=10,
            submitter_player_id="p1",
        )
    no_claims = _contest(db_session, contest_id="pts_nc", allow_claims=False)
    with pytest.raises(InvalidClaimError, match="不接受选手申报"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=no_claims, value=5, rank=1),
            submitted_by=10,
            submitter_player_id="p1",
        )


def test_team_claim_requires_membership(db_session):
    for pid in ("p1", "p2", "p3", "p9"):
        _add_player(db_session, pid)
    _add_team(db_session, "t1", ["p1", "p2", "p3"])
    cid = _contest(db_session, contest_id="pts_team", entity="team", max_value=10, n_teams=5)

    with pytest.raises(NotTeamMemberError):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=7, rank=1, team_id="t1"),
            submitted_by=10,
            submitter_player_id="p9",
        )
    with pytest.raises(InvalidClaimError, match="队伍"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=7, rank=1, team_id="t999"),
            submitted_by=10,
            submitter_player_id="p1",
        )

    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=cid, value=7, rank=1, team_id="t1"),
        submitted_by=10,
        submitter_player_id="p1",
    )
    assert claim.team_name == "一队" and claim.entity == "team"
    with pytest.raises(DuplicateClaimError):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=6, rank=2, team_id="t1"),
            submitted_by=10,
            submitter_player_id="p2",
        )


def test_solo_contest_rejects_team_field(db_session):
    _add_player(db_session, "p1")
    cid = _contest(db_session)
    with pytest.raises(InvalidClaimError, match="个人赛"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=5, rank=1, team_id="t1"),
            submitted_by=10,
            submitter_player_id="p1",
        )


def test_formula_contest_claim_shape(db_session):
    """formula 场次 value/rank 必填且成对；award 不可混填。"""
    _add_player(db_session, "p1")
    cid = _contest(db_session)
    with pytest.raises(ValueError, match="名次"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=5),
            submitted_by=10,
            submitter_player_id="p1",
        )
    with pytest.raises(ValueError, match="同时"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=5, rank=1, award="gold"),
            submitted_by=10,
            submitter_player_id="p1",
        )


# ---- 认证提交（award_only 场次）---------------------------------------------


def _seed_award_levels(session) -> None:
    from xcpc_core.tier import api as tier_api
    from xcpc_core.tier.models import AwardLevelCreate

    for name, base in (("gold", 100.0), ("silver", 60.0)):
        if tier_api.find_award_level_by_name(name, session=session) is None:
            tier_api.create_award_level(AwardLevelCreate(name=name, base_points=base), session=session)


def test_award_only_claim_flow(db_session):
    """「积分只由奖项决定」的比赛：申报奖项，value/rank 不填。"""
    _add_player(db_session, "p1")
    _seed_award_levels(db_session)
    from xcpc_core.tier import api as tier_api
    from xcpc_core.tier.models import TierCreate

    tier = tier_api.create_tier(TierCreate(name="测试等级", coefficient=0.5), session=db_session)
    cid = _contest(db_session, contest_id="pts_award", scoring="award_only", max_value=None, tier_id=tier.id)

    with pytest.raises(InvalidClaimError, match="奖项"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=5, rank=1),
            submitted_by=10,
            submitter_player_id="p1",
        )
    with pytest.raises(InvalidClaimError, match="未知奖项"):
        points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, award="champion"),
            submitted_by=10,
            submitter_player_id="p1",
        )

    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=cid, award="gold"),
        submitted_by=10,
        submitter_player_id="p1",
    )
    assert claim.award == "gold" and claim.value is None and claim.rank is None

    points_api.review_claim(session=db_session, claim_id=claim.id, decision="approved", decided_by=99)
    entry = db_session.scalars(select(PointsEntry)).all()[0]
    # 金奖基线 100 × 等级系数 0.5 = 50
    assert entry.points == pytest.approx(50.0)
    snapshot = json.loads(entry.payload_json)
    assert snapshot["scoring"] == "award_only" and snapshot["award"] == "gold"
    assert snapshot["coefficient"] == 0.5


# ---- 审核 ------------------------------------------------------------------


def test_review_player_claim_writes_entry_and_audit(db_session):
    _add_player(db_session, "p1")
    cid = _contest(db_session)
    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=cid, value=8, rank=2),
        submitted_by=10,
        submitter_player_id="p1",
    )

    reviewed = points_api.review_claim(session=db_session, claim_id=claim.id, decision="approved", decided_by=99)
    assert reviewed.status == "approved" and reviewed.decided_by == 99

    entries = db_session.scalars(select(PointsEntry)).all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.owner_type == "player" and entry.owner_id == "p1" and entry.team_context is None
    assert entry.contest_id == cid
    assert entry.points == pytest.approx(compute_points(value=8, rank=2, max_value=12, n_teams=10))
    snapshot = json.loads(entry.payload_json)
    assert snapshot["value"] == 8 and snapshot["rank"] == 2
    assert snapshot["max_value"] == 12 and snapshot["n_teams"] == 10

    audit = db_session.scalars(select(AuditLog)).all()
    assert len(audit) == 1 and audit[0].action == "points.approve" and audit[0].user_id == 99

    with pytest.raises(ClaimStateError):
        points_api.review_claim(session=db_session, claim_id=claim.id, decision="rejected", decided_by=99)


def test_review_team_claim_shared_three(db_session):
    for pid in ("p1", "p2", "p3"):
        _add_player(db_session, pid)
    _add_team(db_session, "t1", ["p1", "p2", "p3"])
    cid = _contest(db_session, contest_id="pts_team2", entity="team", max_value=10, n_teams=5)
    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=cid, value=7, rank=1, team_id="t1"),
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
    cid = _contest(db_session)
    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=cid, value=3, rank=5),
        submitted_by=10,
        submitter_player_id="p1",
    )
    reviewed = points_api.review_claim(session=db_session, claim_id=claim.id, decision="rejected", decided_by=99)
    assert reviewed.status == "rejected"
    assert db_session.scalars(select(PointsEntry)).all() == []
    assert db_session.scalars(select(AuditLog)).all()[0].action == "points.reject"

    resubmitted = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=cid, value=8, rank=2),
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
    cid = _contest(db_session, contest_id="pts_board")

    for pid, value, rank in (("p1", 8, 2), ("p2", 5, 5), ("p4", 10, 1)):
        claim = points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=value, rank=rank),
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
    team_cid = _contest(db_session, contest_id="pts_cteam", entity="team", max_value=10, n_teams=5)
    solo_cid = _contest(db_session, contest_id="pts_csolo", title="个人训练赛", max_value=10, n_teams=5)

    team_claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=team_cid, value=7, rank=1, team_id="t1"),
        submitted_by=10,
        submitter_player_id="p1",
    )
    points_api.review_claim(session=db_session, claim_id=team_claim.id, decision="approved", decided_by=99)
    solo_claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=solo_cid, value=5, rank=1),
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
    c1 = _contest(db_session, contest_id="pts_w1", title="九月场")
    c2 = _contest(db_session, contest_id="pts_w2", title="十月场", day=D2)
    for cid, value in ((c1, 8), (c2, 10)):
        claim = points_api.submit_claim(
            session=db_session,
            params=PointsClaimCreate(contest_id=cid, value=value, rank=1),
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
    """改配置不溯及：已记流水的分值不变；流水快照保留计分参数。"""
    _add_player(db_session, "p1")
    cid = _contest(db_session, contest_id="pts_snap")
    claim = points_api.submit_claim(
        session=db_session,
        params=PointsClaimCreate(contest_id=cid, value=6, rank=1),
        submitted_by=10,
        submitter_player_id="p1",
    )
    points_api.review_claim(session=db_session, claim_id=claim.id, decision="approved", decided_by=99)
    before = db_session.scalars(select(PointsEntry)).all()[0].points

    # 管理员事后改 max_value（重存比赛）→ 已记流水不变，快照保留旧参数
    contest_api.save_contest(ContestCreate(
        id=cid, title="省赛积分场", date=D1, format="icpc", entity="player",
        max_value=24, n_teams=10, counts_for_points=True, allow_claims=True,
        counts_for_ranking=False,
    ))

    entry = db_session.scalars(select(PointsEntry)).all()[0]
    assert entry.points == pytest.approx(before)  # 100×(6/12)×(10/10) = 50
    assert json.loads(entry.payload_json)["max_value"] == 12  # 快照保留旧参数


def test_points_error_base():
    assert issubclass(InvalidClaimError, PointsError)
