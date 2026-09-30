"""从统一 Contest/Standing 表生成 RatingEvent（归一化，docs/04 §5.3 的派生步骤）。

数据源 = counts_for_ranking=True 的比赛（CONTEST_UNIFICATION_PLAN §3：逐场开关取代
旧「仅训练赛」体系隔离）。名次口径：入库 standing 保留全省/全场原始名次，事件
生成时做**内部重排名**（按原始名次排序 → 1,2,3…，并列取平均）——原始名次直接
喂 Perf 方程会无解（r−0.5 可能超过入库实体数），重排名是数学上必须的一步。

护栏（方案 D1）：入库可排名实体 < 2 的场次跳过——单实体 Perf 恒等于自身先验，
纯噪声；OJ 数据源到位后在此扩展。
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from xcpc_core.db.tables import Contest, Standing, StandingMember, Tier
from xcpc_core.rating.models import RatingEvent


def _rerank(standings: list[Standing]) -> dict[int, float]:
    """原始名次 → 内部名次（1,2,3…；并列同名次取平均，如 1,2,2 → 1,2.5,2.5）。"""
    by_rank: dict[int, int] = defaultdict(int)
    for row in standings:
        by_rank[row.rank] += 1
    ordered = sorted(by_rank)  # 并列共享同一起始位
    internal: dict[int, float] = {}
    pos = 1.0
    for rank in ordered:
        count = by_rank[rank]
        internal[rank] = pos + (count - 1) / 2
        pos += count
    return internal


def build_events_from_contests(
    session: Session,
    *,
    only_ranking: bool = True,
) -> list[RatingEvent]:
    stmt = select(Contest)
    if only_ranking:
        stmt = stmt.where(Contest.counts_for_ranking)
    contests = session.scalars(stmt).all()

    tiers = {tier.id: tier for tier in session.scalars(select(Tier)).all()}

    events: list[RatingEvent] = []
    for contest in contests:
        standings = session.scalars(
            select(Standing).where(Standing.contest_id == contest.id).order_by(Standing.rank)
        ).all()
        rankable = [row for row in standings if row.rank is not None]
        if len(rankable) < 2:
            # 护栏：可排名实体 < 2 的场次不进重放（单实体无相对名次信息）
            continue

        internal_rank = _rerank(rankable)
        member_ids: dict[int, list[str]] = {}
        for standing_id, player_id in session.execute(
            select(StandingMember.standing_id, StandingMember.player_id).where(
                StandingMember.standing_id.in_([row.id for row in rankable])
            )
        ).all():
            member_ids.setdefault(standing_id, []).append(player_id)

        for standing in rankable:
            player_ids = member_ids.get(standing.id) or []
            if not player_ids:
                continue
            payload = {
                key: value
                for key, value in {
                    "rank": standing.rank,  # 原始名次（全省/全场），积分百分位口径
                    "internal_rank": internal_rank[standing.rank],  # 重排名，Perf 方程口径
                    "n_recorded": len(rankable),  # 入库实体数（重排名分母）
                    "solved": standing.solved,
                    "penalty": standing.penalty,
                    "score": standing.score,
                    "award": standing.award,
                }.items()
                if value is not None
            }
            if contest.entity == "team":
                payload.setdefault("team_count", contest.n_teams or len(rankable))
                payload["size"] = len(player_ids)
            else:
                payload.setdefault("player_count", contest.n_teams or len(rankable))
            payload["entity"] = contest.entity  # 计算器按 (赛制, 形式) 路由

            tier = tiers.get(contest.tier_id)
            for player_id in player_ids:
                events.append(RatingEvent(
                    event_id=f"{contest.id}#{standing.id}#{player_id}",
                    source_type="contest",
                    player_id=player_id,
                    team_id=standing.team_id,
                    date=contest.date,
                    competition_year=contest.competition_year,
                    season=contest.season,
                    contest_type=tier.name if tier else None,
                    contest_format=contest.format,
                    # 整数权重 = 系数×100（引擎侧时间加权接线在 P-U2）
                    weight=int(round((tier.coefficient if tier else 1.0) * 100)),
                    payload=payload,
                ))
    return events
