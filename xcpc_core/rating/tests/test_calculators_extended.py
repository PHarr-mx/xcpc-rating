"""计算器补齐：TrainingDispatcher 路由、OI/OJ 计算器、未知 format/source_type 报错（盲区补齐）。"""

from datetime import date

import pytest

from xcpc_core.rating.calculators import (
    OjContestCalculator,
    OjPracticeCalculator,
    TrainingDispatcher,
    TrainingOiCalculator,
)
from xcpc_core.rating.engine import RatingEngine
from xcpc_core.rating.models import PeriodFilter, RatingEvent


def _event(*, source_type: str, contest_format: str | None = None,
           payload: dict, weight: int = 100) -> RatingEvent:
    return RatingEvent(
        event_id="e1",
        source_type=source_type,  # type: ignore[arg-type]
        date=date(2026, 5, 1),
        competition_year=2025,
        season="2025-春学期",
        contest_format=contest_format,
        player_id="p001",
        payload=payload,
        weight=weight,
    )


def test_training_oi_calculator():
    event = _event(source_type="training", contest_format="oi",
                   payload={"rank": 1, "score": 280, "player_count": 10}, weight=60)
    # base = (10-1+1)/10*800 + 280*2 = 1360；× 0.6
    assert TrainingOiCalculator().compute(event) == pytest.approx(816.0)


def test_dispatcher_routes_team_xcpc():
    event = _event(source_type="training", contest_format="team_xcpc",
                   payload={"rank": 2, "solved": 4, "team_count": 8, "size": 3}, weight=95)
    # base = (8-2+1)/8*800 + 120 = 820 → /3 → ×0.95
    assert TrainingDispatcher().compute(event) == pytest.approx(820 / 3 * 0.95)


def test_dispatcher_routes_solo_xcpc():
    event = _event(source_type="training", contest_format="solo_xcpc",
                   payload={"rank": 1, "solved": 5, "player_count": 6}, weight=70)
    assert TrainingDispatcher().compute(event) == pytest.approx(665.0)


def test_dispatcher_unknown_format_raises():
    event = _event(source_type="training", contest_format="mystery", payload={"rank": 1})
    with pytest.raises(ValueError, match="未知训练赛 format"):
        TrainingDispatcher().compute(event)


def test_oj_contest_calculator():
    event = _event(source_type="oj_contest", payload={"delta": 20}, weight=40)
    assert OjContestCalculator().compute(event) == pytest.approx(8.0)
    # delta 缺失按 0；负 delta 归零
    assert OjContestCalculator().compute(_event(source_type="oj_contest", payload={}, weight=40)) == 0
    assert OjContestCalculator().compute(
        _event(source_type="oj_contest", payload={"delta": -30}, weight=40)
    ) == 0


def test_oj_practice_calculator():
    event = _event(source_type="oj_practice",
                   payload={"rating_numeric": 2200, "solve_count": 450}, weight=20)
    # base = 2200*0.5 + 450*2 = 2000；× 0.2
    assert OjPracticeCalculator().compute(event) == pytest.approx(400.0)


def test_engine_unknown_source_type_raises():
    """DTO 层 Literal 拒绝未知类型；绕过校验构造时引擎以 KeyError 暴露。"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _event(source_type="weird", payload={})

    event = RatingEvent.model_construct(
        event_id="e1", source_type="weird", date=date(2026, 5, 1),
        competition_year=2025, season="2025-春学期", contest_format=None,
        player_id="p001", payload={}, weight=100,
    )
    with pytest.raises(KeyError):
        RatingEngine().compute([event], mode="all", period=PeriodFilter())
