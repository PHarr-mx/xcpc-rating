"""积分公式（UCup 式单场分，RATING_FORMULA_PLAN.md §9.1）。

    R = 100 × (value / max_value) × ((n_teams − rank + 1) / n_teams)

- 无 GP30 项、无参赛保底分；资格线 = value ≥ 1（service 层校验）
- value 为解题数（kind=solved）或得分（kind=score），max_value 为全场最高值
- max_value / n_teams 由管理员按场次配置；审核通过时随流水快照，改配置不溯及
"""

from __future__ import annotations


def compute_points(*, value: int, rank: int, max_value: int, n_teams: int) -> float:
    """计算单场积分（不取整，展示层决定小数位）。"""
    if value <= 0:
        raise ValueError(f"value 必须 ≥ 1（积分资格线）: {value}")
    if max_value <= 0:
        raise ValueError(f"max_value 必须 > 0: {max_value}")
    if n_teams <= 0:
        raise ValueError(f"n_teams 必须 > 0: {n_teams}")
    if rank < 1 or rank > n_teams:
        raise ValueError(f"rank 超出范围 [1, {n_teams}]: {rank}")
    return 100.0 * (value / max_value) * ((n_teams - rank + 1) / n_teams)
