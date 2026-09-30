"""训练赛 Rating 重放引擎（docs/04 §2.1 定案，P-R1）。

与逐事件计算器（engine.py）不同，AtCoder 式公式跨选手耦合、按时间序依赖：
第 r 名的表现分依赖「当时」全场每个参赛实体的 APerf。本引擎按场次（event_id
前缀，与 delete_contest 约定一致）× 日期升序重放事件流，维护队伍/个人的历史
表现分，产出每选手逐场 ``ReplayEventScore``（perf + rating_after）。

定案语义（2026-09-28）：
- 组队赛（team_xcpc）参赛实体为队伍：APerf = 队伍自身历史队 Perf 加权平均；
  换员即新队（member_key 约定，team_id 已随之稳定）→ 先验重置 Center
- solo/oi 参赛实体为个人：APerf = 个人历史加权平均
- 同队三人同分：队 Perf 全额记入每名队员个人历史
- 打星（payload.unofficial）参与名次方程、先验记 Center、不入任何历史
- 并列名次取平均；实体首场表现分膨胀 ×1.5；负分照实显示
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from xcpc_core.rating.formula import aperf_from_history, rating_from_history, solve_perf
from xcpc_core.rating.formula_params import CENTER, FIRST_PERF_INFLATION
from xcpc_core.rating.models import PeriodFilter, RatingEvent, ReplayEventScore


def _perf_weights(hist: list[tuple[float, int]]) -> tuple[list[float], list[int]]:
    """历史按旧→新存储，公式约定新→旧，此处翻转。"""
    perfs = [p for p, _ in reversed(hist)]
    weights = [w for _, w in reversed(hist)]
    return perfs, weights


class AtcoderReplayEngine:
    """按场次 × 日期重放训练赛事件流（仅消费 source_type=training）。"""

    def compute_series(
        self,
        events: list[RatingEvent],
        *,
        period: PeriodFilter | None = None,
    ) -> dict[str, list[ReplayEventScore]]:
        scoped = [e for e in events if e.source_type == "training"]
        if period is not None:
            scoped = [
                e
                for e in scoped
                if (period.start is None or e.date >= period.start)
                and (period.end is None or e.date <= period.end)
            ]

        by_contest: dict[str, list[RatingEvent]] = defaultdict(list)
        for event in scoped:
            by_contest[event.event_id.split("#", 1)[0]].append(event)

        personal: dict[str, list[tuple[float, int]]] = {}
        teams: dict[str, list[tuple[float, int]]] = {}
        series: dict[str, list[ReplayEventScore]] = {}
        for contest_id in sorted(by_contest, key=lambda cid: (min(e.date for e in by_contest[cid]), cid)):
            self._replay_contest(by_contest[contest_id], personal, teams, series)
        return series

    # -- 单场重放 -----------------------------------------------------------

    def _replay_contest(
        self,
        contest_events: list[RatingEvent],
        personal: dict[str, list[tuple[float, int]]],
        teams: dict[str, list[tuple[float, int]]],
        series: dict[str, list[ReplayEventScore]],
    ) -> None:
        first = contest_events[0]
        weight = first.weight
        if first.contest_format == "team_xcpc":
            entrants = self._team_entrants(contest_events)
        else:
            entrants = [
                {
                    "key": e.player_id,
                    "team_id": None,
                    "members": [e.player_id],
                    "rank": self._rank(e),
                    "unofficial": bool(e.payload.get("unofficial")),
                }
                for e in contest_events
            ]

        entrants.sort(key=lambda en: en["rank"])
        for position, entrant in enumerate(entrants, start=1):
            entrant["position"] = position
        for entrant in entrants:
            tied = [en["position"] for en in entrants if en["rank"] == entrant["rank"]]
            entrant["avg_rank"] = sum(tied) / len(tied)

        priors: list[float] = []
        for entrant in entrants:
            hist: list[tuple[float, int]] | None = None
            if not entrant["unofficial"]:
                hist = teams.get(entrant["team_id"]) if entrant["team_id"] else personal.get(entrant["key"])
            if hist:
                perfs, weights = _perf_weights(hist)
                aperf = aperf_from_history(perfs, weights)
                entrant["prior"] = CENTER if aperf is None else aperf
                entrant["first_contest"] = False
            else:
                entrant["prior"] = CENTER
                entrant["first_contest"] = not entrant["unofficial"]
            priors.append(entrant["prior"])

        solved: dict[float, float] = {}
        for entrant in entrants:
            avg_rank = entrant["avg_rank"]
            if avg_rank not in solved:
                solved[avg_rank] = solve_perf(avg_rank, priors)
            perf = solved[avg_rank]
            if entrant["first_contest"]:
                perf = (perf - CENTER) * FIRST_PERF_INFLATION + CENTER
            entrant["perf"] = perf

        for entrant in entrants:
            if entrant["unofficial"]:
                continue
            perf = entrant["perf"]
            if entrant["team_id"]:
                teams.setdefault(entrant["team_id"], []).append((perf, weight))
            for player_id in entrant["members"]:
                history = personal.setdefault(player_id, [])
                history.append((perf, weight))
                perfs, weights = _perf_weights(history)
                series.setdefault(player_id, []).append(
                    ReplayEventScore(
                        date=first.date,
                        perf=perf,
                        rating_after=rating_from_history(perfs, weights),
                    )
                )

    # -- 事件解析 -----------------------------------------------------------

    def _team_entrants(self, contest_events: list[RatingEvent]) -> list[dict[str, Any]]:
        grouped: dict[str, list[RatingEvent]] = {}
        for event in contest_events:
            if event.team_id is None:
                raise ValueError(f"team_xcpc 场次事件缺少 team_id: {event.event_id}")
            grouped.setdefault(event.team_id, []).append(event)

        entrants: list[dict[str, Any]] = []
        for team_id, member_events in grouped.items():
            ranks = {self._rank(e) for e in member_events}
            if len(ranks) != 1:
                raise ValueError(f"队伍 {team_id} 成员名次不一致: {sorted(ranks)}")
            entrants.append(
                {
                    "key": team_id,
                    "team_id": team_id,
                    "members": [e.player_id for e in member_events],
                    "rank": ranks.pop(),
                    "unofficial": any(bool(e.payload.get("unofficial")) for e in member_events),
                }
            )
        return entrants

    @staticmethod
    def _rank(event: RatingEvent) -> int:
        rank = event.payload.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            raise ValueError(f"事件 {event.event_id} 缺少合法 rank: {rank!r}")
        return rank
