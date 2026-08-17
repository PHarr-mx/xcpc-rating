from __future__ import annotations

from datetime import date

import pytest

from xcpc_core.contest import api as contest_api
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore
from xcpc_core.rating.api import compute_rating
from xcpc_core.rating.calculators import (
    FormalCalculator,
    OjContestCalculator,
    TrainingTeamXcpcCalculator,
)
from xcpc_core.rating.engine import RatingEngine
from xcpc_core.rating.events import build_events_from_contests
from xcpc_core.rating.models import PeriodFilter, RatingEvent


@pytest.fixture(autouse=True)
def _use_test_contest_store(db_session):
    contest_api.configure_store(ContestStore(db_session))
    yield
    contest_api.configure_store(None)


def _evt(event_id: str, *, player_id: str, source_type: str = "formal", date_: date = date(2026, 5, 18), contest_format: str | None = None, payload: dict | None = None, weight: int = 100) -> RatingEvent:
    return RatingEvent(
        event_id=event_id,
        source_type=source_type,
        date=date_,
        competition_year=2025,
        season="2026-春学期",
        contest_format=contest_format or ("team_xcpc" if source_type == "formal" else None),
        player_id=player_id,
        payload=payload or {"rank": 1, "total_teams": 100, "solved": 8},
        weight=weight,
    )


def test_formal_calculator_weight_applied():
    calc = FormalCalculator()
    event = _evt("e1", player_id="p001", weight=70, payload={"rank": 1, "total_teams": 100, "solved": 8})
    base = calc.compute_base_score(event)
    assert base == pytest.approx((100 - 1 + 1) / 100 * 1000 + 8 * 50)
    assert calc.compute(event) == pytest.approx(base * 70 / 100)


def test_training_team_divides_by_size():
    calc = TrainingTeamXcpcCalculator()
    event = _evt("e1", player_id="p001", source_type="training", payload={"rank": 2, "team_count": 10, "solved": 5, "size": 3})
    base = calc.compute_base_score(event)
    assert base == pytest.approx(((10 - 2 + 1) / 10 * 800 + 5 * 30) / 3)


def test_oj_contest_uses_delta():
    calc = OjContestCalculator()
    event = _evt("e1", player_id="p001", source_type="oj_contest", payload={"delta": 20})
    assert calc.compute(event) == pytest.approx(20)  # weight 100


def test_engine_mode_filter_and_aggregation():
    events = [
        _evt("f1", player_id="p001", source_type="formal"),
        _evt("f2", player_id="p002", source_type="formal", payload={"rank": 2, "total_teams": 100, "solved": 6}),
        _evt("t1", player_id="p001", source_type="training", date_=date(2026, 4, 1),
             contest_format="solo_xcpc", payload={"rank": 1, "player_count": 20, "solved": 5, "size": 1}),
    ]
    engine = RatingEngine()

    all_result = engine.compute(events, mode="all", period=PeriodFilter())
    formal_only = engine.compute(events, mode="formal_only", period=PeriodFilter())

    assert len(all_result.scores) == 2
    assert len(formal_only.scores) == 2
    p001_all = next(s for s in all_result.scores if s.player_id == "p001")
    p001_formal = next(s for s in formal_only.scores if s.player_id == "p001")
    assert p001_all.event_count == 2
    assert p001_formal.event_count == 1


def test_engine_period_filter():
    events = [
        _evt("e1", player_id="p001", date_=date(2026, 5, 18)),
        _evt("e2", player_id="p001", date_=date(2026, 8, 1)),
    ]
    engine = RatingEngine()
    period = PeriodFilter(type="season", id="2026-春学期", start=date(2026, 3, 1), end=date(2026, 6, 30))
    result = engine.compute(events, mode="all", period=period)
    assert result.scores[0].event_count == 1


def test_engine_compute_series_sorted_by_date():
    events = [
        _evt("e2", player_id="p001", date_=date(2026, 8, 1), payload={"rank": 3, "total_teams": 10, "solved": 5}),
        _evt("e1", player_id="p001", date_=date(2026, 5, 18), payload={"rank": 1, "total_teams": 10, "solved": 5}),
        _evt("t1", player_id="p002", source_type="training", date_=date(2026, 4, 1),
             contest_format="solo_xcpc", payload={"rank": 1, "player_count": 20, "solved": 5, "size": 1}),
    ]
    engine = RatingEngine()
    series = engine.compute_series(events, mode="all", period=PeriodFilter())

    p001 = series["p001"]
    assert [item.date for item in p001] == [date(2026, 5, 18), date(2026, 8, 1)]  # 按 date 升序
    assert p001[0].score == pytest.approx(1250.0)  # rank1 / 10 队
    assert p001[1].score == pytest.approx(1050.0)  # rank3 / 10 队
    assert len(series["p002"]) == 1
    # 聚合结果与 compute 一致
    result = engine.compute(events, mode="all", period=PeriodFilter())
    p001_agg = next(s for s in result.scores if s.player_id == "p001")
    assert p001_agg.rating == pytest.approx(1250.0 + 1050.0)
    assert p001_agg.event_count == 2


def test_build_events_from_contests_and_api(db_session):
    contest_api.save_contest(ContestCreate(
        id="contest_rating",
        title="测试正式赛",
        date=date(2026, 5, 18),
        contest_type="icpc_provincial",
        format="team_xcpc",
        total_teams=86,
        school_teams_count=2,
        weight=70,
        standings=[
            Standing(team_id="t001", team_name="一队", rank=1, award="gold", solved=8, penalty=600,
                     player_ids=["p001", "p002", "p003"]),
            Standing(team_id="t002", team_name="二队", rank=2, award="silver", solved=7, penalty=700,
                     player_ids=["p004"]),
        ],
    ))

    events = build_events_from_contests(db_session)
    assert len(events) == 4  # 3 + 1 名队员
    assert all(e.source_type == "formal" for e in events)
    assert all(e.payload["total_teams"] == 86 for e in events)

    result = compute_rating(session=db_session)
    assert len(result.scores) == 4
    p001 = next(s for s in result.scores if s.player_id == "p001")
    assert p001.event_count == 1
    # 第一名基础分 > 第二名
    rank1 = next(s for s in result.scores if s.player_id == "p001")
    rank2 = next(s for s in result.scores if s.player_id == "p004")
    assert rank1.rating > rank2.rating
