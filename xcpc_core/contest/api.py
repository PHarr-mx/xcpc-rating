"""比赛模块对外编程接口。

CLI 与 core 其他子模块（importer 等）应从此处导入，勿直接读写数据库。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import sessionmaker

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


def get_service(*, store: ContestStore | None = None) -> ContestService:
    """获取 ``ContestService`` 实例。"""
    resolved = store or _default_store
    if resolved is not None:
        return ContestService(resolved)
    return ContestService(ContestStore(_get_default_factory()()))


def save_contest(data: ContestCreate, *, today: date | None = None, store: ContestStore | None = None) -> Contest:
    return get_service(store=store).save_contest(data, today=today)


def get_contest(contest_id: str, *, store: ContestStore | None = None) -> ContestDetail:
    return get_service(store=store).get_contest(contest_id)


def list_contests(*, source_type: str | None = None, store: ContestStore | None = None) -> list[Contest]:
    return get_service(store=store).list_contests(source_type=source_type)


def delete_contest(contest_id: str, *, store: ContestStore | None = None) -> None:
    return get_service(store=store).delete_contest(contest_id)
