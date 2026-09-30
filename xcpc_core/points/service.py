"""points 业务逻辑（改挂统一 contest，CONTEST_UNIFICATION_PLAN §4.2/§2.6）。

会话注入模式与 importer.staged 一致：函数接收 ``Session | None``，未注入时
走默认工厂并负责关闭；写函数单事务 commit，异常回滚。审核通过在同一事务内
写积分流水（双 owner）与审计行，保证「记分 + 审计」原子生效。

场次创建已并入统一比赛（contest 模块）：本模块只负责认证工作流与积分聚合。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from xcpc_core.db.tables import (
    AuditLog,
    Contest,
    Player,
    PointsClaim,
    PointsEntry,
    Team,
    TeamAlias,
    TeamMember,
    Tier,
)
from xcpc_core.points.exceptions import (
    ClaimNotFoundError,
    ClaimStateError,
    DuplicateClaimError,
    InvalidClaimError,
    NotTeamMemberError,
    UnknownAwardError,
)
from xcpc_core.points.formula import compute_award_points, compute_points
from xcpc_core.points.models import (
    IndividualPointsRow,
    PointsClaimCreate,
    PointsClaimView,
    TeamPointsRow,
)
from xcpc_core.tier.store import TierStore

DEFAULT_W_TEAM = 0.6
DEFAULT_W_MEMBER = 0.4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_session(session: Session | None) -> tuple[Session, bool]:
    if session is not None:
        return session, False
    from xcpc_core.db.session import make_session_factory

    return make_session_factory()[1](), True


# ---- 认证 ------------------------------------------------------------------


def _team_display_name(session: Session, team_id: str) -> str:
    """队伍展示名：最新别名（无别名回退 team_id）。"""
    aliases = session.scalars(
        select(TeamAlias.alias).where(TeamAlias.team_id == team_id).order_by(TeamAlias.id)
    ).all()
    return aliases[-1] if aliases else team_id


def _claim_view(session: Session, row: PointsClaim) -> PointsClaimView:
    contest = session.get(Contest, row.contest_id)
    player_name = None
    if row.player_id:
        player = session.get(Player, row.player_id)
        player_name = player.name if player else None
    team_name = _team_display_name(session, row.team_id) if row.team_id else None
    return PointsClaimView(
        id=row.id,
        contest_id=row.contest_id,
        contest_title=contest.title if contest else None,
        scoring=contest.scoring if contest else None,
        entity=row.entity,
        player_id=row.player_id,
        player_name=player_name,
        team_id=row.team_id,
        team_name=team_name,
        value=row.value,
        rank=row.rank,
        award=row.award,
        note=row.note,
        status=row.status,
        submitted_by=row.submitted_by,
        decided_by=row.decided_by,
        created_at=row.created_at,
        decided_at=row.decided_at,
    )


def _load_claimable_contest(session: Session, contest_id: str) -> Contest:
    """加载可申报的比赛：存在、允许申报、计入积分。"""
    contest = session.get(Contest, contest_id)
    if contest is None:
        from xcpc_core.points.exceptions import ContestNotFoundError

        raise ContestNotFoundError(f"比赛不存在: {contest_id}")
    if not contest.allow_claims:
        raise InvalidClaimError("该比赛不接受选手申报")
    if not contest.counts_for_points:
        raise InvalidClaimError("该比赛不计入积分，无需申报认证")
    return contest


def submit_claim(
    session: Session | None,
    *,
    params: PointsClaimCreate,
    submitted_by: int,
    submitter_player_id: str,
) -> PointsClaimView:
    """提交认证。个人赛只能为本人提交；队伍赛提交者须为该队现役成员。

    formula 场次校验 value/rank 与 max_value/n_teams；award_only 场次校验奖项
    在 awardlevel 内，value/rank 必须为空。
    """
    s, owned = _resolve_session(session)
    try:
        contest = _load_claimable_contest(s, params.contest_id)

        value = params.value
        rank = params.rank
        award = params.award
        if contest.scoring == "formula":
            if value is None or rank is None:
                raise InvalidClaimError("该比赛按解题数/名次计分，请填写解题数与名次")
            if contest.max_value is None or contest.n_teams is None:
                raise InvalidClaimError("该比赛缺少 max_value/n_teams 配置，请联系管理员补全")
            if value > contest.max_value:
                raise InvalidClaimError(
                    f"value={value} 超过本场最高值 max_value={contest.max_value}，请核对后重试"
                )
            if rank > contest.n_teams:
                raise InvalidClaimError(f"rank={rank} 超出参赛实体数 n_teams={contest.n_teams}")
        else:  # award_only
            if award is None:
                raise InvalidClaimError("该比赛积分只由奖项决定，请选择获奖等级")
            award_names = {row.name for row in TierStore(s).list_award_levels()}
            if award not in award_names:
                raise UnknownAwardError(f"未知奖项: {award}（须为奖项基线表中已配置的等级）")

        player_id: str | None = None
        team_id: str | None = None
        if contest.entity == "player":
            if params.team_id:
                raise InvalidClaimError("个人赛不能提交队伍认证")
            player_id = submitter_player_id
            if not player_id:
                raise InvalidClaimError("当前账号未绑定选手，无法提交认证")
            duplicate = s.scalar(
                select(PointsClaim.id).where(
                    PointsClaim.contest_id == contest.id,
                    PointsClaim.player_id == player_id,
                    PointsClaim.status != "rejected",
                )
            )
            if duplicate is not None:
                raise DuplicateClaimError("该比赛已存在本人的认证记录")
        else:
            team_id = params.team_id
            if not team_id:
                raise InvalidClaimError("队伍赛必须选择队伍")
            team = s.get(Team, team_id)
            if team is None:
                raise InvalidClaimError(f"队伍不存在: {team_id}")
            membership = s.scalar(
                select(TeamMember.id).where(
                    TeamMember.team_id == team_id,
                    TeamMember.player_id == submitter_player_id,
                )
            )
            if membership is None:
                raise NotTeamMemberError("只有该队伍的现役成员才能提交认证")
            duplicate = s.scalar(
                select(PointsClaim.id).where(
                    PointsClaim.contest_id == contest.id,
                    PointsClaim.team_id == team_id,
                    PointsClaim.status != "rejected",
                )
            )
            if duplicate is not None:
                raise DuplicateClaimError("该比赛已存在此队伍的认证记录")

        row = PointsClaim(
            contest_id=contest.id,
            entity=contest.entity,
            player_id=player_id,
            team_id=team_id,
            value=value,
            rank=rank,
            award=award,
            note=params.note,
            status="staged",
            submitted_by=submitted_by,
            created_at=_now(),
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return _claim_view(s, row)
    except Exception:
        s.rollback()
        raise
    finally:
        if owned:
            s.close()


def list_claims(
    session: Session | None, *, contest_id: str | None = None, status: str | None = None
) -> list[PointsClaimView]:
    s, owned = _resolve_session(session)
    try:
        stmt = select(PointsClaim).order_by(PointsClaim.id.desc())
        if contest_id is not None:
            stmt = stmt.where(PointsClaim.contest_id == contest_id)
        if status is not None:
            stmt = stmt.where(PointsClaim.status == status)
        return [_claim_view(s, row) for row in s.scalars(stmt).all()]
    finally:
        if owned:
            s.close()


def my_claims(session: Session | None, *, player_id: str) -> list[PointsClaimView]:
    """本人相关认证：本人 player 认证 + 所在队伍的 team 认证。"""
    s, owned = _resolve_session(session)
    try:
        team_ids = s.scalars(
            select(TeamMember.team_id).where(TeamMember.player_id == player_id)
        ).all()
        stmt = select(PointsClaim).order_by(PointsClaim.id.desc())
        if team_ids:
            stmt = stmt.where(
                (PointsClaim.player_id == player_id) | (PointsClaim.team_id.in_(team_ids))
            )
        else:
            stmt = stmt.where(PointsClaim.player_id == player_id)
        return [_claim_view(s, row) for row in s.scalars(stmt).all()]
    finally:
        if owned:
            s.close()


def player_teams(session: Session | None, *, player_id: str) -> list[dict]:
    """提交队伍认证时的可选队伍（现役成员身份），供 Web 下拉。"""
    s, owned = _resolve_session(session)
    try:
        team_ids = s.scalars(
            select(TeamMember.team_id).where(TeamMember.player_id == player_id)
        ).all()
        return [
            {"team_id": team_id, "name": _team_display_name(s, team_id)}
            for team_id in team_ids
        ]
    finally:
        if owned:
            s.close()


def _compute_claim_points(session: Session, contest: Contest, claim: PointsClaim) -> float:
    """统一计分入口：formula = UCup 式 × 等级系数；award_only = 基线分 × 等级系数。"""
    tier = TierStore(session).get(contest.tier_id) if contest.tier_id else None
    coefficient = tier.coefficient if tier else 1.0
    if contest.scoring == "formula":
        return compute_points(
            value=claim.value or 0,
            rank=claim.rank or 0,
            max_value=contest.max_value or 0,
            n_teams=contest.n_teams or 0,
            coefficient=coefficient,
        )
    award = TierStore(session).find_award_by_name(claim.award or "")
    base = award.base_points if award else 0.0
    return compute_award_points(base_points=base, coefficient=coefficient)


def review_claim(
    session: Session | None,
    *,
    claim_id: int,
    decision: Literal["approved", "rejected"],
    decided_by: int,
) -> PointsClaimView:
    """审核认证。通过在同一事务内写积分流水（双 owner）与审计行。"""
    if decision not in ("approved", "rejected"):
        raise ClaimStateError(f"未知审核决定: {decision}")
    s, owned = _resolve_session(session)
    try:
        claim = s.get(PointsClaim, claim_id)
        if claim is None:
            raise ClaimNotFoundError(f"认证记录不存在: {claim_id}")
        if claim.status != "staged":
            raise ClaimStateError(f"认证 #{claim_id} 当前状态为 {claim.status}，不能审核")

        contest = s.get(Contest, claim.contest_id)
        if contest is None:
            raise ClaimNotFoundError(f"认证对应的比赛不存在: {claim.contest_id}")
        tier = TierStore(s).get(contest.tier_id) if contest.tier_id else None
        now = _now()
        points: float | None = None
        if decision == "approved":
            points = _compute_claim_points(s, contest, claim)
            snapshot = json.dumps(
                {
                    "scoring": contest.scoring,
                    "value": claim.value,
                    "rank": claim.rank,
                    "award": claim.award,
                    "max_value": contest.max_value,
                    "n_teams": contest.n_teams,
                    "tier": tier.name if tier else None,
                    "coefficient": tier.coefficient if tier else 1.0,
                },
                ensure_ascii=False,
            )

            def _entry(owner_type: str, owner_id: str, team_context: str | None) -> PointsEntry:
                return PointsEntry(
                    owner_type=owner_type,
                    owner_id=owner_id,
                    points=points,
                    contest_id=contest.id,
                    claim_id=claim.id,
                    team_context=team_context,
                    payload_json=snapshot,
                    date=contest.date,
                    created_at=now,
                )

            if claim.entity == "player":
                s.add(_entry("player", claim.player_id, None))
            else:
                # 队伍赛三人共享：1 条 team 流水 + 每名现役成员 1 条 player 流水
                s.add(_entry("team", claim.team_id, claim.team_id))
                member_ids = s.scalars(
                    select(TeamMember.player_id).where(TeamMember.team_id == claim.team_id)
                ).all()
                for member_id in member_ids:
                    s.add(_entry("player", member_id, claim.team_id))

        claim.status = decision
        claim.decided_by = decided_by
        claim.decided_at = now
        s.add(
            AuditLog(
                action="points.approve" if decision == "approved" else "points.reject",
                target=f"claim#{claim.id}",
                user_id=decided_by,
                diff_json=json.dumps(
                    {
                        "contest_id": claim.contest_id,
                        "entity": claim.entity,
                        "value": claim.value,
                        "rank": claim.rank,
                        "award": claim.award,
                        "points": points,
                    },
                    ensure_ascii=False,
                ),
                at=now,
            )
        )
        s.commit()
        s.refresh(claim)
        return _claim_view(s, claim)
    except Exception:
        s.rollback()
        raise
    finally:
        if owned:
            s.close()


# ---- 榜单 ------------------------------------------------------------------


def individual_leaderboard(
    session: Session | None, *, start: date | None = None, end: date | None = None
) -> list[IndividualPointsRow]:
    """个人积分榜：个人流水直加。离队（left）选手不出榜。"""
    s, owned = _resolve_session(session)
    try:
        stmt = (
            select(
                PointsEntry.owner_id,
                Player.name,
                Player.status,
                func.sum(PointsEntry.points),
                func.count(PointsEntry.id),
            )
            .join(Player, Player.id == PointsEntry.owner_id)
            .where(PointsEntry.owner_type == "player")
            .group_by(PointsEntry.owner_id, Player.name, Player.status)
        )
        if start is not None:
            stmt = stmt.where(PointsEntry.date >= start)
        if end is not None:
            stmt = stmt.where(PointsEntry.date <= end)
        rows = [
            IndividualPointsRow(rank=0, player_id=owner_id, name=name, points=float(total), entry_count=count)
            for owner_id, name, status, total, count in s.execute(stmt).all()
            if status != "left"
        ]
        rows.sort(key=lambda r: (-r.points, r.player_id))
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows
    finally:
        if owned:
            s.close()


def team_leaderboard(
    session: Session | None,
    *,
    w_team: float = DEFAULT_W_TEAM,
    w_member: float = DEFAULT_W_MEMBER,
    start: date | None = None,
    end: date | None = None,
) -> list[TeamPointsRow]:
    """队伍积分榜：复合分 = w_team×团队积分 + w_member×Σ(成员队外个人积分)。

    排除规则防双计：成员队外积分 = 成员全部个人流水 − team_context=本队的流水。
    成员取当前 roster（teammember），队名取最新别名。
    """
    s, owned = _resolve_session(session)

    def _window(stmt):
        if start is not None:
            stmt = stmt.where(PointsEntry.date >= start)
        if end is not None:
            stmt = stmt.where(PointsEntry.date <= end)
        return stmt

    try:
        team_rows = s.execute(
            _window(
                select(PointsEntry.owner_id, func.sum(PointsEntry.points))
                .where(PointsEntry.owner_type == "team")
                .group_by(PointsEntry.owner_id)
            )
        ).all()
        team_points = {owner_id: float(total) for owner_id, total in team_rows}

        player_totals: dict[str, float] = {}
        for owner_id, total in s.execute(
            _window(
                select(PointsEntry.owner_id, func.sum(PointsEntry.points))
                .where(PointsEntry.owner_type == "player")
                .group_by(PointsEntry.owner_id)
            )
        ).all():
            player_totals[owner_id] = float(total)

        via_team: dict[tuple[str, str], float] = {}
        for team_id, owner_id, total in s.execute(
            _window(
                select(PointsEntry.team_context, PointsEntry.owner_id, func.sum(PointsEntry.points))
                .where(PointsEntry.owner_type == "player", PointsEntry.team_context.is_not(None))
                .group_by(PointsEntry.team_context, PointsEntry.owner_id)
            )
        ).all():
            via_team[(team_id, owner_id)] = float(total)

        rows: list[TeamPointsRow] = []
        for team_id, points in team_points.items():
            members = s.execute(
                select(TeamMember.player_id, Player.name)
                .join(Player, Player.id == TeamMember.player_id)
                .where(TeamMember.team_id == team_id)
            ).all()
            member_names = [name for _, name in members]
            member_points = sum(
                player_totals.get(member_id, 0.0) - via_team.get((team_id, member_id), 0.0)
                for member_id, _ in members
            )
            composite = w_team * points + w_member * member_points
            rows.append(
                TeamPointsRow(
                    rank=0,
                    team_id=team_id,
                    name=_team_display_name(s, team_id),
                    team_points=round(points, 2),
                    member_points=round(member_points, 2),
                    composite=round(composite, 2),
                    members=member_names,
                )
            )
        rows.sort(key=lambda r: (-r.composite, r.team_id))
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows
    finally:
        if owned:
            s.close()
