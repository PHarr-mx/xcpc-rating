"""AuditLog 写入 API。

设计：与 `xcpc_core.player.api` 一致的依赖注入模式——
- `configure_session()` 供测试注入，`_get_session()` 回落默认工厂。
- web 层导入后调用 ``record()`` 写审计日志。

跨 DB 约束：web DB 绑定事实先 commit（rx.session()），
AuditLog 到 core DB 是 best-effort，不回滚绑定。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from xcpc_core.db.base import Base
from xcpc_core.db.session import make_session_factory
from xcpc_core.db.tables import AuditLog

_default_session: Session | None = None
_factory: sessionmaker | None = None


def configure_session(session: Session | None) -> None:
    """为当前进程设置默认 session（测试注入 / 复位）。"""
    global _default_session
    _default_session = session


def _get_session() -> Session:
    global _factory
    if _default_session is not None:
        return _default_session
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory()


def record(
    *,
    action: str,
    target: str,
    user_id: int,
    diff_json: dict | None = None,
) -> int:
    """写一条审计日志，返回新行的 id。"""
    session = _get_session()
    log = AuditLog(
        action=action,
        target=target,
        user_id=user_id,
        diff_json=json.dumps(diff_json or {}, ensure_ascii=False),
        at=datetime.now(timezone.utc),
    )
    session.add(log)
    session.flush()
    session.refresh(log)
    session.commit()
    return log.id


def list_logs(
    *,
    user_id: int | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """按条件读取审计日志，返回可跨层传递的普通字典。"""
    session = _get_session()
    stmt = select(AuditLog).order_by(AuditLog.at.desc(), AuditLog.id.desc())
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from is not None:
        stmt = stmt.where(AuditLog.at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        # 日期筛选包含当天。
        stmt = stmt.where(
            AuditLog.at < datetime.combine(
                date_to,
                datetime.min.time(),
            ) + timedelta(days=1)
        )
    rows = session.scalars(stmt).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "action": row.action,
            "target": row.target,
            "diff_json": row.diff_json,
            "at": row.at.isoformat(),
        }
        for row in rows
    ]
