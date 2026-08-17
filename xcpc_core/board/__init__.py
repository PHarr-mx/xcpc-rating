"""榜单聚合模块（docs/07）：Rating 结果 × 选手信息 → BoardSnapshot。

只读聚合；数值计算复用 rating 引擎的事件得分序列。
"""

from xcpc_core.board.api import board, invalidate
from xcpc_core.board.models import BoardMeta, BoardRow, BoardSnapshot
from xcpc_core.board.service import BoardService, period_label

__all__ = [
    "BoardMeta",
    "BoardRow",
    "BoardService",
    "BoardSnapshot",
    "board",
    "invalidate",
    "period_label",
]
