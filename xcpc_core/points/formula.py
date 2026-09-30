"""积分公式（UCup 式单场分，去 GP30；CONTEST_UNIFICATION_PLAN §2.6）。

    formula:     R = 100 × (value / max_value) × ((n_teams − rank + 1) / n_teams) × 系数
    award_only:  R = awardlevel.base_points × 系数

- 无 GP30 项、无参赛保底分；资格线 = value ≥ 1（service 层校验）
- 系数 = tier.coefficient（赛事等级），审核通过时随流水快照，改配置不溯及
"""

from __future__ import annotations


def compute_points(
    *, value: int, rank: int, max_value: int, n_teams: int, coefficient: float = 1.0
) -> float:
    """计算 formula 场次单场积分（不取整，展示层决定小数位）。"""
    if value <= 0:
        raise ValueError(f"value 必须 ≥ 1（积分资格线）: {value}")
    if max_value <= 0:
        raise ValueError(f"max_value 必须 > 0: {max_value}")
    if n_teams <= 0:
        raise ValueError(f"n_teams 必须 > 0: {n_teams}")
    if rank < 1 or rank > n_teams:
        raise ValueError(f"rank 超出范围 [1, {n_teams}]: {rank}")
    if coefficient <= 0:
        raise ValueError(f"coefficient 必须 > 0: {coefficient}")
    return 100.0 * (value / max_value) * ((n_teams - rank + 1) / n_teams) * coefficient


def compute_award_points(*, base_points: float, coefficient: float = 1.0) -> float:
    """计算 award_only 场次奖项积分：基线分 × 赛事等级系数。"""
    if base_points < 0:
        raise ValueError(f"base_points 必须 ≥ 0: {base_points}")
    if coefficient <= 0:
        raise ValueError(f"coefficient 必须 > 0: {coefficient}")
    return base_points * coefficient
