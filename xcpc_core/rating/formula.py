"""AtCoder 式 Rating 纯函数（docs/04 §2.1，定案 2026-09-28）。

规格与 AtCoder Rating System ver. 1.00 一致，扩展两点：场次权重融进时间加权
（0.9^i × w/100，division 查表）；组队赛以队伍为参赛实体（编排见 replay.py）。

全部函数无状态、按新→旧的列表约定，可独立单测。每个函数接受可选 ``params``，
缺省用 ``formula_params.DEFAULT``——试算页（P6）传覆盖值即可，不改全局。
"""

from __future__ import annotations

from math import log2, sqrt
from typing import Sequence

from xcpc_core.rating.formula_params import DEFAULT, FormulaParams


def _f_inf(time_decay: float) -> float:
    """F(∞) = sqrt(Σ0.81^i) / Σ0.9^i 的极限（0.81 = 0.9²）。"""
    return sqrt(time_decay**2 / (1 - time_decay**2)) / (time_decay / (1 - time_decay))


def solve_perf(
    target_rank: float,
    entrant_aperfs: Sequence[float],
    *,
    params: FormulaParams | None = None,
) -> float:
    """解 Σ_j 1/(1+odds^((X−a_j)/scale)) = target_rank − 0.5 的唯一表现分 X。

    左侧随 X 严格单调递减，二分求解；并列名次由调用方折算为平均名次后传入。
    """
    p = params or DEFAULT
    lo = min(entrant_aperfs) - 4000.0
    hi = max(entrant_aperfs) + 4000.0
    target = target_rank - 0.5

    def expected_wins(x: float) -> float:
        return sum(
            1.0 / (1.0 + p.logistic_odds ** ((x - a) / p.logistic_scale)) for a in entrant_aperfs
        )

    for _ in range(100):
        mid = (lo + hi) / 2
        if expected_wins(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def weighted_average(
    values: Sequence[float],
    contest_weights: Sequence[int] | None = None,
    *,
    params: FormulaParams | None = None,
) -> float | None:
    """time_decay^i × (w_i/100) 归一化加权平均，values 按新→旧排列（i=1 最新）。

    空序列返回 None，由调用方决定回落 Center。
    """
    p = params or DEFAULT
    if not values:
        return None
    weights = [p.time_decay ** (i + 1) for i in range(len(values))]
    if contest_weights is not None:
        weights = [w * (cw / 100.0) for w, cw in zip(weights, contest_weights)]
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def _capital_f(n: int, time_decay: float) -> float:
    """F(n) = sqrt(Σ 0.81^i) / Σ 0.9^i（0.81 = 0.9²）。"""
    numerator = sqrt(sum(time_decay ** (2 * i) for i in range(1, n + 1)))
    denominator = sum(time_decay**i for i in range(1, n + 1))
    return numerator / denominator


def f_correction(n: int, *, params: FormulaParams | None = None) -> float:
    """参赛次数补项：f(1)=f_full，随场次单调衰减趋近 0（初始分收敛机制）。"""
    p = params or DEFAULT
    if n <= 0:
        return p.f_full
    f_1 = _capital_f(1, p.time_decay)
    return (_capital_f(n, p.time_decay) - _f_inf(p.time_decay)) / (f_1 - _f_inf(p.time_decay)) * p.f_full


def g(x: float, *, params: FormulaParams | None = None) -> float:
    p = params or DEFAULT
    return 2.0 ** (x / p.g_scale)


def g_inv(y: float, *, params: FormulaParams | None = None) -> float:
    p = params or DEFAULT
    return p.g_scale * log2(y)


def aperf_from_history(
    perfs: Sequence[float],
    contest_weights: Sequence[int] | None = None,
    *,
    params: FormulaParams | None = None,
) -> float | None:
    """进场先验：历史表现分的加权平均（新→旧），无历史返回 None。"""
    return weighted_average(perfs, contest_weights, params=params)


def rating_from_history(
    perfs: Sequence[float],
    contest_weights: Sequence[int] | None = None,
    *,
    params: FormulaParams | None = None,
) -> float:
    """个人 Rating：g 空间时间加权平均 − f(n)。perfs 至少 1 场。"""
    if not perfs:
        raise ValueError("rating_from_history 需要至少一场表现分")
    p = params or DEFAULT
    avg = weighted_average([g(x, params=p) for x in perfs], contest_weights, params=p)
    assert avg is not None  # perfs 非空
    return g_inv(avg, params=p) - f_correction(len(perfs), params=p)