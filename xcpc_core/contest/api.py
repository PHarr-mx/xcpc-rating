"""比赛模块对外编程接口。

CLI 与 core 其他子模块（importer 等）应从此处导入，勿直接读写数据库。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from xcpc_core.contest.models import Contest, ContestCreate, ContestDetail
from xcpc_core.contest.service import ContestService
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.session import make_session_factory

_default_store: ContestStore | None = None
_factory: sessionmaker | None = None


def configure_store(store: ContestStore) -> None:
    """为当前进程设置默认数据存储（测试或自定义路径时使用）。"""
    global _default_store
    _default_store = store


def _get_default_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory


def _open_service(*, store: ContestStore | None = None) -> tuple[ContestService, Session | None]:
    """打开 service，返回 (service, owned_session)。

    - 注入或已 ``configure_store`` 的 store 由外部管理，owned_session 为 ``None``；
    - 未注入时自建短事务 session，调用方必须在 ``finally`` 中关闭，
      否则每次调用都会向连接池借出一个连接且不归还（Reflex 并发下会耗尽池）。
    """
    resolved = store or _default_store
    if resolved is not None:
        return ContestService(resolved), None
    session = _get_default_factory()()
    return ContestService(ContestStore(session)), session


def save_contest(data: ContestCreate, *, today: date | None = None, store: ContestStore | None = None) -> Contest:
    service, session = _open_service(store=store)
    try:
        return service.save_contest(data, today=today)
    finally:
        if session is not None:
            session.close()


def get_contest(contest_id: str, *, store: ContestStore | None = None) -> ContestDetail:
    service, session = _open_service(store=store)
    try:
        return service.get_contest(contest_id)
    finally:
        if session is not None:
            session.close()


def list_contests(*, source_type: str | None = None, store: ContestStore | None = None) -> list[Contest]:
    service, session = _open_service(store=store)
    try:
        return service.list_contests(source_type=source_type)
    finally:
        if session is not None:
            session.close()


def delete_contest(contest_id: str, *, store: ContestStore | None = None) -> None:
    service, session = _open_service(store=store)
    try:
        return service.delete_contest(contest_id)
    finally:
        if session is not None:
            session.close()
