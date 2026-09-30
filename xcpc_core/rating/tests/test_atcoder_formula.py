"""AtCoder 式公式纯函数单测（docs/04 §2.1；收敛数值来自合成赛季演算）。"""

import math

import pytest

from xcpc_core.rating.formula import (
    aperf_from_history,
    f_correction,
    g,
    g_inv,
    rating_from_history,
    solve_perf,
    weighted_average,
)
from xcpc_core.rating.formula_params import CENTER


def test_f_correction_boundaries():
    assert f_correction(1) == pytest.approx(1200.0)
    assert f_correction(2) < f_correction(1)
    assert 0 < f_correction(60) < 10
    assert f_correction(0) == pytest.approx(1200.0)  # 防御路径：无场次按满额


def test_constant_perf_convergence():
    """恒定打出 X：从 X−1200 起步、逐步收敛到 X（数值与合成演算一致）。"""
    assert rating_from_history([800.0]) == pytest.approx(-400.0)
    assert rating_from_history([800.0] * 3) == pytest.approx(255.0, abs=1.0)
    assert rating_from_history([800.0] * 5) == pytest.approx(453.0, abs=1.0)
    assert rating_from_history([800.0] * 10) == pytest.approx(643.0, abs=1.0)
    assert rating_from_history([1200.0]) == pytest.approx(0.0)


def test_rating_requires_history():
    with pytest.raises(ValueError, match="至少一场"):
        rating_from_history([])


def test_weighted_average_recency():
    assert weighted_average([]) is None
    assert weighted_average([500.0]) == pytest.approx(500.0)
    # 最新 0.9、次新 0.81：(200×0.9 + 100×0.81) / 1.71
    assert weighted_average([200.0, 100.0]) == pytest.approx(152.63, abs=0.01)


def test_weight_extension_in_time_weights():
    equal = weighted_average([1000.0, 500.0], [100, 100])
    # 场次权重乘进 0.9^i：老场次 w=300 把平均拉向旧表现
    pulled = weighted_average([1000.0, 500.0], [100, 300])
    assert pulled < equal
    # 权重整体缩放不影响归一化平均
    assert weighted_average([1000.0, 500.0], [200, 200]) == pytest.approx(equal)


def test_solve_perf_all_equal_priors():
    """n 个同先验入场者有闭式解：X = a + 400·log6(n/(r−0.5) − 1)。"""
    aperfs = [CENTER] * 8
    spread = 400.0 * math.log(15, 6)  # r=1 → n/(0.5)−1 = 15
    assert solve_perf(1, aperfs) == pytest.approx(CENTER + spread, abs=0.01)
    assert solve_perf(8, aperfs) == pytest.approx(CENTER - spread, abs=0.01)
    assert solve_perf(4.5, aperfs) == pytest.approx(CENTER, abs=0.01)  # 中位名次恰为锚点


def test_solve_perf_monotone_in_rank():
    aperfs = [700.0, 800.0, 900.0, 1000.0, 1100.0]
    perfs = [solve_perf(r, aperfs) for r in range(1, 6)]
    assert perfs == sorted(perfs, reverse=True)


def test_g_roundtrip():
    for x in (0.0, 400.0, 1200.0, -300.0):
        assert g_inv(g(x)) == pytest.approx(x)


def test_aperf_none_when_no_history():
    assert aperf_from_history([]) is None
    # 新值权重更高：(900×0.9 + 700×0.81)/1.71 ≈ 805.26
    assert aperf_from_history([900.0, 700.0]) == pytest.approx(805.26, abs=0.01)
