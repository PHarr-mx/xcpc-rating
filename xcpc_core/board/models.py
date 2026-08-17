"""榜单 DTO（docs/07 §4 输出结构）。

BoardSnapshot = meta（mode × period 组合的说明）+ rows（排名行）。
榜单数值如何计算由 rating 模块负责；本模块只做聚合与展示字段装配。
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from xcpc_core.rating.models import BoardMode, PeriodType

# 与 docs/06 §2.5 的占位算法版本号保持一致（meta.rating_algorithm 缺省值）
DEFAULT_ALGORITHM = "placeholder_v0"
# 排名规则说明（docs/07 §4.3）：rating 降序，同分按 player_id 字典序，同分同 rank、下一名跳号
TIE_BREAK_DESC = "rating_desc_player_id_asc"


class BoardMeta(BaseModel):
    """榜单头部：说明这次快照的筛选条件与生成信息。"""

    mode: BoardMode
    period_type: PeriodType
    period_id: str | int | None = None  # None for career
    period_label: str
    start: date | None = None
    end: date | None = None
    algorithm: str = DEFAULT_ALGORITHM
    data_version: int = 0
    tie_break: str = TIE_BREAK_DESC
    generated_at: datetime


class BoardRow(BaseModel):
    """榜单一行（docs/07 §4.1）。"""

    rank: int
    player_id: str
    name: str
    grade_label: str
    rating: float
    event_count: int
    delta_recent: float  # 周期内最近一次事件对该选手 rating 的贡献


class BoardSnapshot(BaseModel):
    """一个 mode × period 组合下的榜单快照。"""

    meta: BoardMeta
    rows: list[BoardRow]
