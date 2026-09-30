"""AtCoder 式 Rating 纯函数（docs/04 §2.1，定案 2026-09-28）。

规格与 AtCoder Rating System ver. 1.00 一致，扩展两点：场次权重融进时间加权
（0.9^i × w/100，division 查表）；组队赛以队伍为参赛实体（编排见 replay.py）。
全部函数无状态、按新→旧的列表约定，可独立单测。
"""

from __future__ import annotations

from math import log2, sqrt
from typing import Sequence

from xcpc_core.rating.formula_params import (
    F_FULL,
    G_SCALE,
    LOGISTIC_ODDS,
    LOGISTIC_SCALE,
    TIME_DECAY,
)


def solve_perf(target_rank: float, entrant_aperfs: Sequence[float]) -> float:
    """解 Σ_j 1/(1+6^((X−a_j)/400)) = target_rank − 0.5 的唯一表现分 X。

    左侧随 X 严格单调递减，二分求解；并列名次由调用方折算为平均名次后传入。
    """
    lo = min(entrant_aperfs) - 4000.0
    hi = max(entrant_aperfs) + 4000.0
    target = target_rank - 0.5

    def expected_wins(x: float) -> float:
        return sum(1.0 / (1.0 + LOGISTIC_ODDS ** ((x - a) / LOGISTIC_SCALE)) for a in entrant_aperfs)

    for _ in range(100):
        mid = (lo + hi) / 2
        if expected_wins(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def weighted_average(
    values: Sequence[float], contest_weights: Sequence[int] | None = None
) -> float | None:
    """0.9^i × (w_i/100) 归一化加权平均，values 按新→旧排列（i=1 最新）。

    空序列返回 None，由调用方决定回落 Center。
    """
    if not values:
        return None
    weights = [TIME_DECAY ** (i + 1) for i in range(len(values))]
    if contest_weights is not None:
        weights = [w * (cw / 100.0) for w, cw in zip(weights, contest_weights)]
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def _capital_f(n: int) -> float:
    """F(n) = sqrt(Σ 0.81^i) / Σ 0.9^i（0.81 = 0.9²）。"""
    numerator = sqrt(sum(TIME_DECAY ** (2 * i) for i in range(1, n + 1)))
    denominator = sum(TIME_DECAY ** i for i in range(1, n + 1))
    return numerator / denominator


_F_INF = sqrt(TIME_DECAY**2 / (1 - TIME_DECAY**2)) / (TIME_DECAY / (1 - TIME_DECAY))
_F_1 = _capital_f(1)


def f_correction(n: int) -> float:
    """参赛次数补项：f(1)=F_FULL，随场次单调衰减趋近 0（初始分收敛机制）。"""
    if n <= 0:
        return F_FULL
    return (_capital_f(n) - _F_INF) / (_F_1 - _F_INF) * F_FULL


def g(x: float) -> float:
    return 2.0 ** (x / G_SCALE)


def g_inv(y: float) -> float:
    return G_SCALE * log2(y)


def aperf_from_history(
    perfs: Sequence[float], contest_weights: Sequence[int] | None = None
) -> float | None:
    """进场先验：历史表现分的加权平均（新→旧），无历史返回 None。"""
    return weighted_average(perfs, contest_weights)


def rating_from_history(
    perfs: Sequence[float], contest_weights: Sequence[int] | None = None
) -> float:
    """个人 Rating：g 空间时间加权平均 − f(n)。perfs 至少 1 场。"""
    if not perfs:
        raise ValueError("rating_from_history 需要至少一场表现分")
    avg = weighted_average([g(p) for p in perfs], contest_weights)
    assert avg is not None  # perfs 非空
    return g_inv(avg) - f_correction(len(perfs))
