"""Rating 对外接口：从 DB 生成事件 → 引擎计算。"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from xcpc_core.db.session import make_session_factory
from xcpc_core.rating.engine import RatingEngine
from xcpc_core.rating.events import build_events_from_contests
from xcpc_core.rating.models import PeriodFilter, RatingResult

_factory: sessionmaker | None = None


def _get_default_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory


def compute_rating(
    *,
    mode: str = "all",
    period: PeriodFilter | None = None,
    session: Session | None = None,
) -> RatingResult:
    """计算一个 mode × period 的榜单结果。period 缺省为生涯（不过滤日期）。"""
    close = False
    if session is None:
        session = _get_default_factory()()
        close = True
    try:
        events = build_events_from_contests(session)
    finally:
        if close:
            session.close()
    engine = RatingEngine()
    return engine.compute(events, mode=mode, period=period or PeriodFilter())
