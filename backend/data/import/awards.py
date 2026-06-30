from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel

from importer.models import AwardThresholds

_AWARD_MEDALS = frozenset({"gold", "silver", "bronze"})


class StandingScore(BaseModel):
    rank: int
    solved: int
    penalty: int
    award: str | None = None


def beats_or_equal(solved: int, penalty: int, cutoff: tuple[int, int]) -> bool:
    cutoff_solved, cutoff_penalty = cutoff
    return solved > cutoff_solved or (solved == cutoff_solved and penalty <= cutoff_penalty)


def assign_award(solved: int, penalty: int, thresholds: AwardThresholds) -> str | None:
    if thresholds.gold and beats_or_equal(solved, penalty, thresholds.gold):
        return "gold"
    if thresholds.silver and beats_or_equal(solved, penalty, thresholds.silver):
        return "silver"
    if thresholds.bronze and beats_or_equal(solved, penalty, thresholds.bronze):
        return "bronze"
    return None


def _weakest_cutoff(rows: list[StandingScore]) -> tuple[int, int] | None:
    if not rows:
        return None
    weakest = min(rows, key=lambda row: (row.solved, -row.penalty))
    return (weakest.solved, weakest.penalty)


def thresholds_from_formal_medals(rows: list[StandingScore]) -> AwardThresholds | None:
    by_medal = {medal: [row for row in rows if row.award == medal] for medal in _AWARD_MEDALS}
    if not any(by_medal.values()):
        return None
    return AwardThresholds(
        gold=_weakest_cutoff(by_medal["gold"]),
        silver=_weakest_cutoff(by_medal["silver"]),
        bronze=_weakest_cutoff(by_medal["bronze"]),
        source="formal_medals",
    )


def thresholds_from_percentiles(
    rows: list[StandingScore],
    *,
    total_teams: int,
    gold_ratio: float = 0.10,
    silver_ratio: float = 0.20,
    bronze_ratio: float = 0.30,
) -> AwardThresholds:
    ordered = sorted(rows, key=lambda row: row.rank)

    def cutoff(ratio: float) -> tuple[int, int] | None:
        if not ordered or total_teams <= 0:
            return None
        index = max(0, math.ceil(ratio * total_teams) - 1)
        index = min(index, len(ordered) - 1)
        team = ordered[index]
        return (team.solved, team.penalty)

    return AwardThresholds(
        gold=cutoff(gold_ratio),
        silver=cutoff(silver_ratio),
        bronze=cutoff(bronze_ratio),
        source="percentile",
    )


def resolve_award_thresholds(
    formal_rows: list[StandingScore],
    all_rows: list[StandingScore],
    *,
    total_teams: int,
) -> AwardThresholds:
    from_medals = thresholds_from_formal_medals(formal_rows)
    if from_medals is not None:
        return from_medals
    return thresholds_from_percentiles(all_rows, total_teams=total_teams)
