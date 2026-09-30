"""重放引擎语义测试：同队同分 / 队伍先验 / 打星 / 并列名次 / 周期窗口 / 数据校验。"""

import math
from datetime import date

import pytest

from xcpc_core.rating.formula_params import CENTER
from xcpc_core.rating.models import PeriodFilter, RatingEvent
from xcpc_core.rating.replay import AtcoderReplayEngine

_seq = iter(range(100000))


def _event(
    *,
    contest_id: str,
    player_id: str,
    rank: int,
    d: date,
    team_id: str | None = None,
    weight: int = 100,
    fmt: str = "team_xcpc",
    unofficial: bool = False,
) -> RatingEvent:
    return RatingEvent(
        event_id=f"{contest_id}#{next(_seq)}",
        source_type="training",
        date=d,
        competition_year=2025,
        season="2025-秋学期",
        contest_format=fmt,
        player_id=player_id,
        team_id=team_id,
        weight=weight,
        payload={"rank": rank, **({"unofficial": True} if unofficial else {})},
    )


def _team(contest_id, team_id, members, rank, d, weight=100, unofficial=False):
    return [
        _event(contest_id=contest_id, player_id=m, team_id=team_id, rank=rank,
               d=d, weight=weight, unofficial=unofficial)
        for m in members
    ]


D1 = date(2025, 9, 10)


def test_team_members_share_perf_and_rating():
    events = (
        _team("c1", "t1", ["p1", "p2", "p3"], 1, D1)
        + _team("c1", "t2", ["p4", "p5", "p6"], 2, D1)
    )
    series = AtcoderReplayEngine().compute_series(events)

    assert series["p1"][0].perf == series["p2"][0].perf == series["p3"][0].perf
    assert series["p4"][0].perf == series["p5"][0].perf == series["p6"][0].perf
    assert series["p1"][0].perf > series["p4"][0].perf
    assert series["p1"][0].rating_after == series["p2"][0].rating_after
    # 单场历史：rating_after = perf − f(1) = perf − 1200
    assert series["p1"][0].rating_after == pytest.approx(series["p1"][0].perf - 1200.0)


def test_first_contest_perf_matches_closed_form():
    """两队全 Center 先验首场：X = Center ± 400·log6(3)·1.5（n=2，膨胀 ×1.5）。"""
    events = (
        _team("c1", "t1", ["p1", "p2", "p3"], 1, D1)
        + _team("c1", "t2", ["p4", "p5", "p6"], 2, D1)
    )
    series = AtcoderReplayEngine().compute_series(events)
    spread = 400.0 * math.log(3, 6) * 1.5
    assert series["p1"][0].perf == pytest.approx(CENTER + spread, abs=0.01)
    assert series["p4"][0].perf == pytest.approx(CENTER - spread, abs=0.01)


def test_second_contest_uses_team_history():
    """t1 两连冠：第二场先验来自队伍自身历史，同名次表现分高于首场。"""
    d2 = date(2025, 9, 17)
    events = (
        _team("c1", "t1", ["p1", "p2", "p3"], 1, D1)
        + _team("c1", "t2", ["p4", "p5", "p6"], 2, D1)
        + _team("c2", "t1", ["p1", "p2", "p3"], 1, d2)
        + _team("c2", "t3", ["p7", "p8", "p9"], 2, d2)
    )
    series = AtcoderReplayEngine().compute_series(events)
    assert series["p1"][1].perf > series["p1"][0].perf


def test_solo_contest_personal_history():
    d2 = date(2025, 9, 17)
    events = [
        _event(contest_id="s1", player_id="p1", rank=1, d=D1, fmt="solo_xcpc"),
        _event(contest_id="s1", player_id="p2", rank=2, d=D1, fmt="solo_xcpc"),
        _event(contest_id="s2", player_id="p1", rank=3, d=d2, fmt="oi"),
        _event(contest_id="s2", player_id="p2", rank=1, d=d2, fmt="oi"),
        _event(contest_id="s2", player_id="p3", rank=2, d=d2, fmt="oi"),
    ]
    series = AtcoderReplayEngine().compute_series(events)
    assert len(series["p1"]) == 2
    assert series["p1"][0].rating_after == pytest.approx(series["p1"][0].perf - 1200.0)
    # 第二场：f(2)≈745 < f(1)，rating_after 明显高于 perf−1200
    rec2 = series["p1"][1]
    assert rec2.rating_after > rec2.perf - 1200.0


def test_unofficial_participates_but_not_recorded():
    base = (
        _team("c1", "t1", ["p1", "p2", "p3"], 1, D1)
        + _team("c1", "t2", ["p4", "p5", "p6"], 2, D1)
    )
    with_star = base + _team("c1", "t9", ["x1", "x2", "x3"], 2, D1, unofficial=True)
    series_base = AtcoderReplayEngine().compute_series(base)
    series_star = AtcoderReplayEngine().compute_series(with_star)

    assert "x1" not in series_star and "x3" not in series_star  # 打星不入任何历史
    assert series_star["p1"][0].perf != series_base["p1"][0].perf  # 但参与名次方程


def test_tied_ranks_averaged():
    """三人并列第 1 → 平均名次 2.0；n=3 全 Center：t = (2−0.5)/3 = 0.5 → X 恰为 Center。"""
    events = [
        _event(contest_id="s1", player_id=p, rank=1, d=D1, fmt="solo_xcpc")
        for p in ("p1", "p2", "p3")
    ]
    series = AtcoderReplayEngine().compute_series(events)
    for p in ("p1", "p2", "p3"):
        assert series[p][0].perf == pytest.approx(CENTER, abs=0.01)


def test_period_window_replays_from_scratch():
    """周期榜语义：窗口内以全 Center 重放，窗口前场次不参与。"""
    d2 = date(2025, 10, 8)
    events = (
        _team("c1", "t1", ["p1", "p2", "p3"], 1, D1)
        + _team("c1", "t2", ["p4", "p5", "p6"], 2, D1)
        + _team("c2", "t1", ["p1", "p2", "p3"], 2, d2)
        + _team("c2", "t3", ["p7", "p8", "p9"], 1, d2)
    )
    engine = AtcoderReplayEngine()
    career = engine.compute_series(events)
    window = engine.compute_series(
        events, period=PeriodFilter(type="career", start=date(2025, 10, 1))
    )

    assert len(career["p1"]) == 2
    assert len(window["p1"]) == 1  # 9 月场次被窗口过滤
    # 窗口内 t1 变成首场 → Center 先验 + 膨胀，与生涯重放的第 2 场表现分不同
    spread = 400.0 * math.log(3, 6) * 1.5
    assert window["p1"][0].perf == pytest.approx(CENTER - spread, abs=0.01)
    assert window["p1"][0].rating_after == pytest.approx(CENTER - spread - 1200.0, abs=0.01)


def test_weight_affects_rating():
    """场次权重融进时间加权：同队两连冠，高权重场次压轴拉高 rating。"""
    d2 = date(2025, 9, 17)
    plain = (
        _team("c1", "t1", ["p1", "p2", "p3"], 1, D1)
        + _team("c1", "t2", ["p4", "p5", "p6"], 2, D1)
        + _team("c2", "t1", ["p1", "p2", "p3"], 1, d2)
        + _team("c2", "t3", ["p7", "p8", "p9"], 2, d2)
    )
    boosted = (
        _team("c1", "t1", ["p1", "p2", "p3"], 1, D1)
        + _team("c1", "t2", ["p4", "p5", "p6"], 2, D1)
        + _team("c2", "t1", ["p1", "p2", "p3"], 1, d2, weight=300)
        + _team("c2", "t3", ["p7", "p8", "p9"], 2, d2, weight=300)
    )
    series_plain = AtcoderReplayEngine().compute_series(plain)
    series_boosted = AtcoderReplayEngine().compute_series(boosted)
    assert series_boosted["p1"][1].rating_after > series_plain["p1"][1].rating_after


def test_strong_team_rating_climbs():
    """四连冠：rating 逐场单调上升（表现分上行 + f(n) 收敛双驱动）。"""
    dates = [date(2025, 9, 10), date(2025, 9, 17), date(2025, 9, 24), date(2025, 10, 8)]
    events = []
    for i, d in enumerate(dates):
        events += _team(f"c{i}", "t1", ["p1", "p2", "p3"], 1, d)
        events += _team(f"c{i}", "t2", ["p4", "p5", "p6"], 2, d)
    series = AtcoderReplayEngine().compute_series(events)
    ratings = [s.rating_after for s in series["p1"]]
    assert ratings == sorted(ratings)
    assert ratings[-1] > 0


def test_inconsistent_team_rank_raises():
    events = [
        _event(contest_id="c1", player_id="p1", team_id="t1", rank=1, d=D1),
        _event(contest_id="c1", player_id="p2", team_id="t1", rank=2, d=D1),
    ]
    with pytest.raises(ValueError, match="名次不一致"):
        AtcoderReplayEngine().compute_series(events)


def test_missing_rank_raises():
    event = _event(contest_id="c1", player_id="p1", team_id="t1", rank=1, d=D1)
    event.payload.pop("rank")
    with pytest.raises(ValueError, match="rank"):
        AtcoderReplayEngine().compute_series([event])


def test_team_event_without_team_id_raises():
    event = _event(contest_id="c1", player_id="p1", rank=1, d=D1)  # team_xcpc 但无 team_id
    with pytest.raises(ValueError, match="team_id"):
        AtcoderReplayEngine().compute_series([event])
