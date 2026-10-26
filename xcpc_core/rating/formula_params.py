"""AtCoder 式训练赛 Rating 公式参数（docs/04 §2.1，定案 2026-09-28）。

两套用法：
- **生产**：直接用模块级常量（``CENTER`` 等），值等于 ``DEFAULT`` 的字段；
- **权重试算（P6）**：构造 :class:`FormulaParams` 覆盖任意项，传给
  ``formula.*`` 函数或 ``AtcoderReplayEngine(params=...)``，**不改模块级常量**
  ——试算不落库、不污染全局、也不进榜单缓存。

改生产默认值只动 ``DEFAULT``。
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class FormulaParams:
    """公式全部可调参数（不可变，派生用 :meth:`with_overrides`）。"""

    center: float = 800.0              # 无历史先验锚点（对应 AtCoder ABC 档；暂不分档）
    logistic_scale: float = 400.0      # Logistic 尺度：实力差 400 分 → 期望对局赔率 1:6
    logistic_odds: float = 6.0         # 赔率基数
    g_scale: float = 800.0             # g 变换尺度 g(X)=2^(X/800)
    time_decay: float = 0.9            # 时间权重 0.9^i（i=1 最新，约 22 场半衰）
    first_perf_inflation: float = 1.5  # 实体首场表现分膨胀
    f_full: float = 1200.0             # f(n) 满额（n=1 时的扣减值）

    def __post_init__(self) -> None:
        if self.center <= 0:
            raise ValueError(f"center 必须 > 0: {self.center}")
        if self.logistic_scale <= 0:
            raise ValueError(f"logistic_scale 必须 > 0: {self.logistic_scale}")
        if self.logistic_odds <= 1:
            raise ValueError(f"logistic_odds 必须 > 1: {self.logistic_odds}")
        if self.g_scale <= 0:
            raise ValueError(f"g_scale 必须 > 0: {self.g_scale}")
        if not (0 < self.time_decay < 1):
            raise ValueError(f"time_decay 必须在 (0, 1): {self.time_decay}")
        if self.first_perf_inflation <= 0:
            raise ValueError(f"first_perf_inflation 必须 > 0: {self.first_perf_inflation}")
        if self.f_full < 0:
            raise ValueError(f"f_full 必须 ≥ 0: {self.f_full}")

    def with_overrides(self, **overrides: float) -> "FormulaParams":
        """返回替换若干项后的新实例（未知键直接报错，避免拼错静默失效）。"""
        unknown = set(overrides) - set(self.__dataclass_fields__)
        if unknown:
            raise ValueError(f"未知公式参数: {sorted(unknown)}")
        return replace(self, **{key: float(value) for key, value in overrides.items()})


#: 生产默认值（2026-09-28 定案）
DEFAULT = FormulaParams()

# ---- 兼容旧代码的模块级别名（值来自 DEFAULT，改默认值改上面即可）----
CENTER: float = DEFAULT.center
LOGISTIC_SCALE: float = DEFAULT.logistic_scale
LOGISTIC_ODDS: float = DEFAULT.logistic_odds
G_SCALE: float = DEFAULT.g_scale
TIME_DECAY: float = DEFAULT.time_decay
FIRST_PERF_INFLATION: float = DEFAULT.first_perf_inflation
F_FULL: float = DEFAULT.f_full

#: 试算页可调的项（顺序即 UI 展示顺序）
TUNABLE_FIELDS: tuple[str, ...] = (
    "center",
    "logistic_scale",
    "logistic_odds",
    "g_scale",
    "time_decay",
    "first_perf_inflation",
    "f_full",
)