"""从 Contest/Standing 表生成 RatingEvent（归一化，docs/04 §5.3 的派生步骤）。

当前数据源只有 formal；training/OJ 的数据源到位后在此扩展。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from xcpc_core.db.tables import Contest, Standing, StandingMember
from xcpc_core.rating.models import RatingEvent


def build_events_from_contests(
    session: Session,
    *,
    source_types: tuple[str, ...] = ("formal",),
) -> list[RatingEvent]:
    contests = session.scalars(
        select(Contest).where(Contest.source_type.in_(source_types))
    ).all()

    events: list[RatingEvent] = []
    for contest in contests:
        standings = session.scalars(
            select(Standing).where(Standing.contest_id == contest.id).order_by(Standing.rank)
        ).all()
        for standing in standings:
            player_ids = list(session.scalars(
                select(StandingMember.player_id).where(StandingMember.standing_id == standing.id)
            ))
            if not player_ids:
                continue
            payload = {
                "rank": standing.rank,
                "solved": standing.solved,
                "penalty": standing.penalty,
                "score": standing.score,
                "award": standing.award,
            }
            if contest.source_type == "formal":
                payload["total_teams"] = contest.total_teams
            else:
                # training 占位：组队用 team_count/size，个人用 player_count
                if contest.format == "team_xcpc":
                    payload["team_count"] = contest.total_teams or len(standings)
                    payload["size"] = len(player_ids)
                else:
                    payload["player_count"] = contest.total_teams or len(standings)

            for player_id in player_ids:
                events.append(RatingEvent(
                    event_id=f"{contest.id}#{standing.id}#{player_id}",
                    source_type=contest.source_type,
                    date=contest.date,
                    competition_year=contest.competition_year,
                    season=contest.season,
                    contest_type=contest.contest_type,
                    contest_format=contest.format,
                    player_id=player_id,
                    team_id=standing.team_id,
                    payload=payload,
                    weight=contest.weight,
                ))
    return events
