"""榜单模块对外编程接口（docs/06 §3：运行时按需算）。

- ``board()``：计算一个 mode × period 组合的榜单快照。
- 缓存：缺省数据源路径按 ``(mode, period, data_version)`` 进程内缓存（上限 256 条）；
  注入 ``session``（测试 / 自定义数据源）时**不走缓存**，保证测试隔离。
- 缓存失效：写路径（player / contest service 的写方法、importer 确认）已统一在
  提交前调用 ``xcpc_core.db.meta.bump_data_version``，业务提交后缓存按新版本号
  自然失效。``invalidate()`` 保留为手动兜底（如外部工具直改库后）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from xcpc_core.board.models import BoardSnapshot
from xcpc_core.board.service import BoardService
from xcpc_core.db.session import make_session_factory
from xcpc_core.db.tables import Contest as ContestRow
from xcpc_core.db.tables import Meta as MetaRow
from xcpc_core.rating.models import PeriodFilter
from xcpc_core.utils.calendar import competition_year

_factory: sessionmaker | None = None
_default_session: Session | None = None
_cache: dict[tuple, BoardSnapshot] = {}
_MAX_CACHE_SIZE = 256


def _get_default_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory


def configure_session(session: Session | None) -> None:
    """为当前进程设置默认数据源会话（测试注入 / 复位；DI 模式镜像 importer/audit）。"""
    global _default_session
    _default_session = session


def _resolve_session(session: Session | None) -> tuple[Session, bool]:
    """返回 (session, owned)：显式参数 > 注入的默认会话 > 默认工厂短会话。"""
    resolved = session or _default_session
    if resolved is not None:
        return resolved, False
    return _get_default_factory()(), True


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
    session, close = _resolve_session(session)
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


def available_periods(*, session: Session | None = None) -> list[dict]:
    """榜单周期下拉的具体选项：生涯 + 数据覆盖的赛年/赛季（按 contest 日期推导）。

    返回项形如 ``{"key": "season:2025-秋学期", "period_type": ..., "id": ..., "label": ...}``，
    key 供前端 select 绑定，label 供展示；赛季按所属赛年枚举四季
    （赛年 Y 含：Y-秋学期、Y+1-寒假/春学期/暑假）。
    """
    session, close = _resolve_session(session)
    try:
        dates = [d for d in session.scalars(select(ContestRow.date)).all() if d is not None]
    finally:
        if close:
            session.close()

    options = [{"key": "career", "period_type": "career", "id": None, "label": "生涯"}]
    for year in sorted({competition_year(d) for d in dates}):
        options.append({
            "key": f"competition_year:{year}",
            "period_type": "competition_year",
            "id": str(year),
            "label": f"{year}赛年",
        })
        for kind in ("秋学期", "寒假", "春学期", "暑假"):
            label_year = year if kind == "秋学期" else year + 1
            label = f"{label_year}-{kind}"
            options.append({
                "key": f"season:{label}",
                "period_type": "season",
                "id": label,
                "label": label,
            })
    return options
