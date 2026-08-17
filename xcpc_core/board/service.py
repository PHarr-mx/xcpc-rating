"""榜单聚合服务（docs/07）。

输入：一个 DB session（数据经 rating 事件流 + player 名册）。
输出：BoardSnapshot —— 按 rating 降序、同分按 player_id 字典序、竞赛排名（1,2,2,4）。

只读聚合，不写任何表；依赖 rating 引擎的事件得分序列计算 ``delta_recent``。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from xcpc_core.board.models import (
    DEFAULT_ALGORITHM,
    BoardMeta,
    BoardRow,
    BoardSnapshot,
)
from xcpc_core.player.models import PlayerStatus
from xcpc_core.player.store import PlayerStore
from xcpc_core.rating.engine import RatingEngine
from xcpc_core.rating.events import build_events_from_contests
from xcpc_core.rating.models import PeriodFilter


def period_label(period: PeriodFilter) -> str:
    """时间维度的展示名（docs/07 §3）：生涯 / 2025赛年 / 2026-春学期。"""
    if period.type == "career":
        return "生涯"
    if period.type == "competition_year":
        return f"{period.id}赛年"
    return str(period.id)


class BoardService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def build(
        self,
        *,
        mode: str = "all",
        period: PeriodFilter | None = None,
        data_version: int = 0,
        algorithm: str = DEFAULT_ALGORITHM,
        generated_at: datetime | None = None,
    ) -> BoardSnapshot:
        period = period or PeriodFilter()
        series = RatingEngine().compute_series(
            build_events_from_contests(self.session),
            mode=mode,
            period=period,
        )

        players = {p.id: p for p in PlayerStore(self.session).list_all()}

        rows: list[BoardRow] = []
        for player_id, values in series.items():
            player = players.get(player_id)
            if player is None or player.status == PlayerStatus.left:
                # 离队选手不出现在榜单（docs/08 §4.1）；退役保留、数据与 Rating 保留
                continue
            rows.append(BoardRow(
                rank=0,  # 排序后统一赋值
                player_id=player_id,
                name=player.name,
                grade_label="未设置" if player.grade == 0 else f"{player.grade}级",
                rating=round(sum(item.score for item in values), 2),
                event_count=len(values),
                delta_recent=round(values[-1].score, 2),  # 最近一次事件（按 date 升序末尾）
            ))

        rows.sort(key=lambda row: (-row.rating, row.player_id))

        # 竞赛排名：同分同 rank，下一名跳号（1, 2, 2, 4）
        rank = 0
        prev_rating: float | None = None
        for index, row in enumerate(rows, start=1):
            if prev_rating is None or row.rating != prev_rating:
                rank = index
            row.rank = rank
            prev_rating = row.rating

        return BoardSnapshot(
            meta=BoardMeta(
                mode=mode,  # type: ignore[arg-type]
                period_type=period.type,
                period_id=period.id,
                period_label=period_label(period),
                start=period.start,
                end=period.end,
                algorithm=algorithm,
                data_version=data_version,
                generated_at=generated_at or datetime.now(timezone.utc),
            ),
            rows=rows,
        )
