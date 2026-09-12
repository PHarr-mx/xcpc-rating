"""Rating 对外接口：从 DB 生成事件 → 引擎计算。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from xcpc_core.db.session import make_session_factory
from xcpc_core.db.tables import Contest as ContestRow
from xcpc_core.rating.engine import RatingEngine
from xcpc_core.rating.events import build_events_from_contests
from xcpc_core.rating.models import PeriodFilter, PlayerEventRecord, RatingResult

_factory: sessionmaker | None = None
_default_session: Session | None = None


def _get_default_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory


def configure_session(session: Session | None) -> None:
    """为当前进程设置默认数据源会话（测试注入用；DI 模式镜像 importer/audit）。"""
    global _default_session
    _default_session = session


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


def player_event_history(
    player_id: str,
    *,
    mode: str = "all",
    session: Session | None = None,
) -> list[PlayerEventRecord]:
    """按选手聚合全部事件的参赛记录与逐场累计 Rating（个人页用）。

    按 (date, event_id) 升序；contribution 为该场贡献（已含权重），
    rating_after 为累计到该场后的 rating（与榜单 placeholder 聚合语义一致）。
    无事件的选手返回空列表。
    """
    owns = False
    resolved = session or _default_session
    if resolved is None:
        resolved = _get_default_factory()()
        owns = True
    try:
        events = [e for e in build_events_from_contests(resolved) if e.player_id == player_id]
        if mode == "formal_only":
            events = [e for e in events if e.source_type == "formal"]
        if not events:
            return []

        titles: dict[str, str] = {}
        contest_ids = {e.event_id.split("#", 1)[0] for e in events}
        for row in resolved.scalars(select(ContestRow).where(ContestRow.id.in_(contest_ids))):
            titles[row.id] = row.title
    finally:
        if owns:
            resolved.close()

    engine = RatingEngine()
    records: list[PlayerEventRecord] = []
    cumulative = 0.0
    for event in sorted(events, key=lambda e: (e.date, e.event_id)):
        contribution = engine.calculators[event.source_type].compute(event)
        cumulative = round(cumulative + contribution, 2)
        payload = event.payload
        # contest_id 约定为 event_id 前缀（{contest_id}#{standing_id}#{player_id}），
        # 与 contest.store.delete_contest 的派生事件清理约定一致
        contest_id = event.event_id.split("#", 1)[0]
        records.append(PlayerEventRecord(
            event_id=event.event_id,
            contest_id=contest_id,
            contest_title=titles.get(contest_id),
            date=event.date,
            source_type=event.source_type,
            contest_type=event.contest_type,
            contest_format=event.contest_format,
            team_id=event.team_id,
            rank=payload.get("rank"),
            solved=payload.get("solved"),
            penalty=payload.get("penalty"),
            score=payload.get("score"),
            award=payload.get("award"),
            contribution=contribution,
            rating_after=cumulative,
        ))
    return records
