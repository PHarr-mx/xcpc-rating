"""榜单模块对外编程接口（docs/06 §3：运行时按需算）。

- ``board()``：计算一个 mode × period 组合的榜单快照。
- 缓存：缺省数据源路径按 ``(mode, period, data_version)`` 进程内缓存（上限 256 条）；
  注入 ``session``（测试 / 自定义数据源）时**不走缓存**，保证测试隔离。
- 写操作（改选手 / 导比赛 / 调权重）后应调用 ``invalidate()``，或按 docs/06 §3
  由写路径 bump ``meta.data_version`` 令缓存自然失效。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from xcpc_core.board.models import BoardSnapshot
from xcpc_core.board.service import BoardService
from xcpc_core.db.session import make_session_factory
from xcpc_core.db.tables import Meta as MetaRow
from xcpc_core.rating.models import PeriodFilter

_factory: sessionmaker | None = None
_cache: dict[tuple, BoardSnapshot] = {}
_MAX_CACHE_SIZE = 256


def _get_default_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory


def _read_meta(session: Session) -> tuple[int, str]:
    """读单行 meta 表：(data_version, rating_algorithm)。无行时返回缺省。"""
    row = session.get(MetaRow, 1)
    if row is None:
        return 0, "placeholder_v0"
    return row.data_version, row.rating_algorithm


def _period_key(period: PeriodFilter) -> tuple:
    """PeriodFilter → 可 hash 的缓存 key 片段。"""
    return (
        period.type,
        str(period.id) if period.id is not None else None,
        period.start.isoformat() if period.start is not None else None,
        period.end.isoformat() if period.end is not None else None,
    )


def invalidate() -> None:
    """清空进程内榜单缓存。任何写操作完成后调用（或依赖 data_version bump）。"""
    _cache.clear()


def board(
    *,
    mode: str = "all",
    period: PeriodFilter | None = None,
    session: Session | None = None,
) -> BoardSnapshot:
    """计算一个 mode × period 组合的榜单快照（docs/07 §2/§3）。"""
    close = False
    if session is None:
        session = _get_default_factory()()
        close = True
    try:
        period = period or PeriodFilter()
        data_version, algorithm = _read_meta(session)
        if close:
            key = (mode, _period_key(period), data_version)
            hit = _cache.get(key)
            if hit is not None:
                return hit

        snapshot = BoardService(session).build(
            mode=mode,
            period=period,
            data_version=data_version,
            algorithm=algorithm,
            generated_at=datetime.now(timezone.utc),
        )

        if close:
            if len(_cache) >= _MAX_CACHE_SIZE:
                _cache.clear()
            _cache[key] = snapshot
        return snapshot
    finally:
        if close:
            session.close()
