from __future__ import annotations

from importer.awards import (
    assign_award,
    beats_or_equal,
    resolve_award_thresholds,
    StandingScore,
    thresholds_from_formal_medals,
    thresholds_from_percentiles,
)
from importer.models import AwardThresholds


def test_beats_or_equal():
    assert beats_or_equal(7, 1000, (5, 519))
    assert beats_or_equal(5, 519, (5, 519))
    assert not beats_or_equal(5, 520, (5, 519))
    assert beats_or_equal(2, 211, (2, 211))
    assert not beats_or_equal(2, 238, (2, 211))


def test_thresholds_from_formal_medals():
    rows = [
        StandingScore(rank=1, solved=11, penalty=100, award="gold"),
        StandingScore(rank=20, solved=5, penalty=519, award="gold"),
        StandingScore(rank=59, solved=3, penalty=131, award="silver"),
        StandingScore(rank=122, solved=2, penalty=211, award="bronze"),
    ]
    thresholds = thresholds_from_formal_medals(rows)
    assert thresholds is not None
    assert thresholds.source == "formal_medals"
    assert thresholds.gold == (5, 519)
    assert thresholds.silver == (3, 131)
    assert thresholds.bronze == (2, 211)


def test_assign_award_from_thresholds():
    thresholds = AwardThresholds(
        gold=(5, 519),
        silver=(3, 131),
        bronze=(2, 211),
        source="formal_medals",
    )
    assert assign_award(7, 956, thresholds) == "gold"
    assert assign_award(5, 529, thresholds) == "silver"
    assert assign_award(2, 211, thresholds) == "bronze"
    assert assign_award(2, 338, thresholds) is None


def test_thresholds_from_percentiles():
    rows = [StandingScore(rank=i, solved=max(0, 12 - i), penalty=i * 10) for i in range(1, 11)]
    thresholds = thresholds_from_percentiles(rows, total_teams=10)
    assert thresholds.source == "percentile"
    assert thresholds.gold == (11, 10)
    assert thresholds.silver == (10, 20)
    assert thresholds.bronze == (9, 30)


def test_resolve_prefers_formal_medals():
    formal = [StandingScore(rank=1, solved=5, penalty=100, award="gold")]
    all_rows = [StandingScore(rank=i, solved=1, penalty=i) for i in range(1, 11)]
    thresholds = resolve_award_thresholds(formal, all_rows, total_teams=10)
    assert thresholds.source == "formal_medals"
