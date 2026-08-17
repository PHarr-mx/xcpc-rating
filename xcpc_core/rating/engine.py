"""RatingEngine：编排计算流程，按 source_type 分发计算器。

docs/06 §2.4。触发方式为「运行时按需算」：结果可按 (mode, period_key, data_version) 做 lru_cache。
"""

from __future__ import annotations

from xcpc_core.rating.calculators import (
    BaseRatingCalculator,
    FormalCalculator,
    OjContestCalculator,
    OjPracticeCalculator,
    TrainingDispatcher,
)
from xcpc_core.rating.models import (
    EventScore,
    PeriodFilter,
    PlayerScore,
    RatingEvent,
    RatingResult,
)


class RatingEngine:
    def __init__(self, calculators: dict[str, BaseRatingCalculator] | None = None) -> None:
        self.calculators: dict[str, BaseRatingCalculator] = calculators or {
            "formal": FormalCalculator(),
            "training": TrainingDispatcher(),
            "oj_contest": OjContestCalculator(),
            "oj_practice": OjPracticeCalculator(),
        }

    def compute_series(
        self,
        events: list[RatingEvent],
        *,
        mode: str,
        period: PeriodFilter,
    ) -> dict[str, list[EventScore]]:
        """过滤后按选手聚合得分序列（按 date 升序）。

        供榜单模块取每选手的得分明细（如 ``delta_recent`` 与选手历史）。
        """
        filtered = self._filter(events, mode=mode, period=period)
        series: dict[str, list[EventScore]] = {}
        for event in filtered:
            calc = self.calculators[event.source_type]
            score = calc.compute(event)
            series.setdefault(event.player_id, []).append(EventScore(date=event.date, score=score))
        for values in series.values():
            values.sort(key=lambda item: item.date)
        return series

    def compute(
        self,
        events: list[RatingEvent],
        *,
        mode: str,
        period: PeriodFilter,
    ) -> RatingResult:
        series = self.compute_series(events, mode=mode, period=period)
        rows = [
            PlayerScore(
                player_id=player_id,
                rating=round(sum(item.score for item in values), 2),
                event_count=len(values),
            )
            for player_id, values in series.items()
        ]
        rows.sort(key=lambda row: (-row.rating, row.player_id))
        return RatingResult(mode=mode, period=period, scores=rows)

    @staticmethod
    def _filter(events: list[RatingEvent], *, mode: str, period: PeriodFilter) -> list[RatingEvent]:
        result: list[RatingEvent] = []
        for event in events:
            if mode == "formal_only" and event.source_type != "formal":
                continue
            if period.start is not None and event.date < period.start:
                continue
            if period.end is not None and event.date > period.end:
                continue
            result.append(event)
        return result
