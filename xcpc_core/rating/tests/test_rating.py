from __future__ import annotations

from datetime import date

import pytest

from xcpc_core.contest import api as contest_api
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore
from xcpc_core.rating.api import compute_rating
from xcpc_core.rating.calculators import (
    ContestDispatcher,
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


def test_contest_dispatcher_internal_rank_and_entity():
    """统一比赛计算器：按重排名百分位计，团队形式按队员数均分。"""
    dispatcher = ContestDispatcher()
    team_event = _evt(
        "e1", player_id="p001", source_type="contest", contest_format="icpc",
        payload={"internal_rank": 2.5, "n_recorded": 2, "solved": 5, "size": 3, "entity": "team"},
    )
    base = dispatcher.compute_base_score(team_event)
    assert base == pytest.approx(((2 - 2.5 + 1) / 2 * 800 + 5 * 30) / 3)
    solo_event = _evt(
        "e2", player_id="p001", source_type="contest", contest_format="icpc",
        payload={"internal_rank": 1.0, "n_recorded": 4, "solved": 6, "entity": "player"},
    )
    assert dispatcher.compute_base_score(solo_event) == pytest.approx((4 - 1 + 1) / 4 * 800 + 6 * 30)


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
        n_teams=86,
        school_teams_count=2,
        standings=[
            Standing(team_id="t001", team_name="一队", rank=1, award="gold", solved=8, penalty=600,
                     player_ids=["p001", "p002", "p003"]),
            Standing(team_id="t002", team_name="二队", rank=2, award="silver", solved=7, penalty=700,
                     player_ids=["p004"]),
        ],
    ))

    events = build_events_from_contests(db_session)
    assert len(events) == 4  # 3 + 1 名队员
    assert all(e.source_type == "contest" for e in events)
    assert all(e.payload["n_recorded"] == 2 for e in events)
    # 重排名：原始 rank 1 → 1，rank 2 → 2（无并列时不变）
    p004_event = next(e for e in events if e.player_id == "p004")
    assert p004_event.payload["rank"] == 2 and p004_event.payload["internal_rank"] == 2.0
    # 未指定 tier → 兜底「未分级」系数 1.0 → 整数权重 100
    assert all(e.weight == 100 for e in events)

    result = compute_rating(session=db_session)
    assert len(result.scores) == 4
    p001 = next(s for s in result.scores if s.player_id == "p001")
    assert p001.event_count == 1
    # 占位公式：团队基础分按队员数均分（一队 3 人 < 单人队 p004 的人均值）
    rank1 = next(s for s in result.scores if s.player_id == "p001")
    rank2 = next(s for s in result.scores if s.player_id == "p004")
    assert rank1.rating == pytest.approx(round(((2 - 1 + 1) / 2 * 800 + 8 * 30) / 3, 2))  # 346.67
    assert rank2.rating == pytest.approx(round((2 - 2 + 1) / 2 * 800 + 7 * 30, 2))  # 610.0


def test_build_events_tier_weight_and_rerank_ties(db_session):
    """等级系数 → 整数权重；并列名次重排名取平均。"""
    from xcpc_core.tier import api as tier_api
    from xcpc_core.tier.models import TierCreate

    tier = tier_api.create_tier(TierCreate(name="测试等级", coefficient=0.7), session=db_session)
    contest_api.save_contest(ContestCreate(
        id="contest_tie",
        title="并列重排名",
        date=date(2026, 5, 18),
        tier_id=tier.id,
        standings=[
            Standing(team_id="t001", team_name="一队", rank=1, solved=8, player_ids=["p001", "p002", "p003"]),
            Standing(team_id="t002", team_name="二队", rank=2, solved=7, player_ids=["p004"]),
            Standing(team_id="t003", team_name="三队", rank=2, solved=7, player_ids=["p005"]),
            Standing(team_id="t004", team_name="四队", rank=4, solved=5, player_ids=["p006"]),
        ],
    ))

    events = build_events_from_contests(db_session)
    by_player = {e.player_id: e for e in events}
    assert by_player["p001"].payload["internal_rank"] == 1.0
    # 原始 rank 2,2 并列 → 内部名次 (2+3)/2 = 2.5
    assert by_player["p004"].payload["internal_rank"] == 2.5
    assert by_player["p005"].payload["internal_rank"] == 2.5
    assert by_player["p006"].payload["internal_rank"] == 4.0
    # 系数 0.7 → 整数权重 70
    assert all(e.weight == 70 for e in events)


def test_build_events_skips_tiny_and_non_ranking(db_session):
    """护栏：可排名实体 < 2 跳过；counts_for_ranking=False 不进事件流。"""
    contest_api.save_contest(ContestCreate(
        id="c_solo", title="单实体场", date=date(2026, 5, 18),
        standings=[Standing(team_id="t001", team_name="一队", rank=1, solved=8, player_ids=["p001"])],
    ))
    contest_api.save_contest(ContestCreate(
        id="c_norank", title="不进排名场", date=date(2026, 5, 20), counts_for_ranking=False,
        standings=[
            Standing(team_id="t001", team_name="一队", rank=1, solved=8, player_ids=["p001", "p002"]),
            Standing(team_id="t002", team_name="二队", rank=2, solved=7, player_ids=["p003"]),
        ],
    ))
    assert build_events_from_contests(db_session) == []
