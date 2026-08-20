"""AuditLog 写入 API。

设计：与 `xcpc_core.player.api` 一致的依赖注入模式——
- `configure_session()` 供测试注入，`_get_session()` 回落默认工厂。
- web 层导入后调用 ``record()`` 写审计日志。

跨 DB 约束：web DB 绑定事实先 commit（rx.session()），
AuditLog 到 core DB 是 best-effort，不回滚绑定。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

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
