"""player_event_history：选手个人页的参赛记录与逐场 Rating（P-U2 重放语义）。"""

import math
from datetime import date

import pytest

from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.service import ContestService
from xcpc_core.contest.store import ContestStore
from xcpc_core.player.models import PlayerCreate
from xcpc_core.player.service import PlayerService
from xcpc_core.player.store import PlayerStore
from xcpc_core.rating.api import player_event_history
from xcpc_core.rating.formula_params import CENTER

# 两队全 Center 先验首场的表现分闭式解（n=2，首场膨胀 ×1.5）：
# rank1: X = Center + 400·log6(3)·1.5；rank2: X = Center − 同值
_SPREAD = 400.0 * math.log(3, 6) * 1.5
_PERF_RANK1 = CENTER + _SPREAD
_PERF_RANK2 = CENTER - _SPREAD
# 首场 Rating = perf − f(1) = perf − 1200（负分照实显示）
_RATING_RANK1 = round(_PERF_RANK1 - 1200.0, 2)
_RATING_RANK2 = round(_PERF_RANK2 - 1200.0, 2)


def _seed_players(session) -> None:
    service = PlayerService(PlayerStore(session))
    service.create_player(PlayerCreate(name="张三", handle="zs", grade=2023))
    service.create_player(PlayerCreate(name="李四", handle="ls", grade=2023))


def _seed_contest(session, contest_id: str, day: date, p1_rank: int) -> None:
    """个人赛（entity=player）：p001 名次 p1_rank，p002 名次互补，两实体过护栏。"""
    other_rank = 2 if p1_rank == 1 else 1
    ContestService(ContestStore(session)).save_contest(ContestCreate(
        id=contest_id,
        title=f"测试赛 {contest_id}",
        date=day,
        entity="player",
        standings=[
            Standing(team_name="张三", rank=p1_rank, solved=5, penalty=100, player_ids=["p001"]),
            Standing(team_name="李四", rank=other_rank, solved=4, penalty=200, player_ids=["p002"]),
        ],
    ))


def test_history_cumulative_and_ordering(db_session):
    _seed_players(db_session)
    _seed_contest(db_session, "c_a", date(2026, 3, 15), p1_rank=1)
    _seed_contest(db_session, "c_b", date(2026, 4, 20), p1_rank=2)

    history = player_event_history("p001", session=db_session)
    assert [r.contest_id for r in history] == ["c_a", "c_b"]  # 按日期升序

    # 第一场：rating = perf − 1200；rating_delta 相对 0 起点
    assert history[0].rating_delta == _RATING_RANK1
    assert history[0].rating_after == _RATING_RANK1

    # 第二场接线核对：p001 先验 = 首场表现分；期望值用同套公式函数复算
    # （公式本身的数学正确性由 test_atcoder_formula 覆盖，这里验证 wiring）
    from xcpc_core.rating.formula import rating_from_history, solve_perf

    perf_b = solve_perf(2.0, [_PERF_RANK1, _PERF_RANK2])
    expected_after = rating_from_history([perf_b, _PERF_RANK1], [100, 100])  # 新→旧
    rec2 = history[1]
    assert rec2.rating_after == pytest.approx(round(expected_after, 2))
    # delta 基于未舍入的前值：首场未舍入 rating = perf − 1200
    assert rec2.rating_delta == pytest.approx(round(expected_after - (_PERF_RANK1 - 1200.0), 2))

    first = history[0]
    assert first.source_type == "contest"
    assert first.contest_title == "测试赛 c_a"
    assert first.rank == 1  # 原始名次
    assert first.solved == 5
    assert first.event_id.startswith("c_a#") and first.event_id.endswith("#p001")


def test_history_empty_for_player_without_events(db_session):
    _seed_players(db_session)
    assert player_event_history("p001", session=db_session) == []


def test_history_unknown_player(db_session):
    assert player_event_history("p999", session=db_session) == []


def test_history_weight_applied(db_session):
    """等级系数进时间加权：最新场次权重低 → 旧场次（高分）占比更高，rating 更高。"""
    from xcpc_core.tier import api as tier_api
    from xcpc_core.tier.models import TierCreate

    _seed_players(db_session)
    PlayerService(PlayerStore(db_session)).create_player(PlayerCreate(name="赵六", handle="zl", grade=2023))
    PlayerService(PlayerStore(db_session)).create_player(PlayerCreate(name="钱七", handle="qq", grade=2023))
    tier_low = tier_api.create_tier(TierCreate(name="低权重等级", coefficient=0.7), session=db_session)

    # 结构完全相同的两组对局：p1/p3 先赢后输；区别仅在第二场的赛事等级系数
    ContestService(ContestStore(db_session)).save_contest(ContestCreate(
        id="c1a", title="第一场A", date=date(2026, 3, 15), entity="player",
        standings=[
            Standing(team_name="张三", rank=1, solved=5, player_ids=["p001"]),
            Standing(team_name="李四", rank=2, solved=4, player_ids=["p002"]),
        ],
    ))
    ContestService(ContestStore(db_session)).save_contest(ContestCreate(
        id="c1b", title="第一场B", date=date(2026, 3, 15), entity="player",
        standings=[
            Standing(team_name="赵六", rank=1, solved=5, player_ids=["p003"]),
            Standing(team_name="钱七", rank=2, solved=4, player_ids=["p004"]),
        ],
    ))
    ContestService(ContestStore(db_session)).save_contest(ContestCreate(
        id="c2a", title="第二场低权重", date=date(2026, 4, 20), entity="player", tier_id=tier_low.id,
        standings=[
            Standing(team_name="张三", rank=2, solved=5, player_ids=["p001"]),
            Standing(team_name="李四", rank=1, solved=6, player_ids=["p002"]),
        ],
    ))
    ContestService(ContestStore(db_session)).save_contest(ContestCreate(
        id="c2b", title="第二场基准", date=date(2026, 4, 20), entity="player",
        standings=[
            Standing(team_name="赵六", rank=2, solved=5, player_ids=["p003"]),
            Standing(team_name="钱七", rank=1, solved=6, player_ids=["p004"]),
        ],
    ))

    # 输掉的第二场被降权（0.7 vs 1.0）→ 对 rating 的拖累更小
    low = player_event_history("p001", session=db_session)[-1].rating_after
    base = player_event_history("p003", session=db_session)[-1].rating_after
    assert low > base
