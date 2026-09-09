"""选手模块对外编程接口。

CLI（``player.cli``）与本模块共用同一套函数；其他 core 子模块应从此处导入，
勿直接读写数据库。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from xcpc_core.db.session import make_session_factory
from xcpc_core.player.models import Player, PlayerCreate, PlayerStatus, PlayerUpdate
from xcpc_core.player.service import PlayerService
from xcpc_core.player.store import PlayerStore

_default_store: PlayerStore | None = None
_factory: sessionmaker | None = None


def configure_store(store: PlayerStore) -> None:
    """为当前进程设置默认数据存储（测试或自定义路径时使用）。"""
    global _default_store
    _default_store = store


def _get_default_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory


def _open_service(*, store: PlayerStore | None = None) -> tuple[PlayerService, Session | None]:
    """打开 service，返回 (service, owned_session)。

    - 注入或已 ``configure_store`` 的 store 由外部管理，owned_session 为 ``None``；
    - 未注入时自建短事务 session，调用方必须在 ``finally`` 中关闭，
      否则每次调用都会向连接池借出一个连接且不归还（Reflex 并发下会耗尽池）。
    """
    resolved = store or _default_store
    if resolved is not None:
        return PlayerService(resolved), None
    session = _get_default_factory()()
    return PlayerService(PlayerStore(session)), session


def list_players(
    *,
    include_left: bool = True,
    status: PlayerStatus | None = None,
    grade: int | None = None,
    store: PlayerStore | None = None,
) -> list[Player]:
    """列出选手，支持按状态、年级筛选。"""
    service, session = _open_service(store=store)
    try:
        return service.list_players(
            include_left=include_left,
            status=status,
            grade=grade,
        )
    finally:
        if session is not None:
            session.close()


def get_player(player_id: str, *, store: PlayerStore | None = None) -> Player:
    """按校内 ID 查询单个选手。"""
    service, session = _open_service(store=store)
    try:
        return service.get_player(player_id)
    finally:
        if session is not None:
            session.close()


def find_by_name(
    name: str,
    *,
    grade: int | None = None,
    store: PlayerStore | None = None,
) -> list[Player]:
    """按姓名或别名查找选手。"""
    service, session = _open_service(store=store)
    try:
        return service.find_by_name(name, grade=grade)
    finally:
        if session is not None:
            session.close()


def find_by_oj(
    platform: str,
    handle: str,
    *,
    store: PlayerStore | None = None,
) -> Player | None:
    """按 OJ 平台账号查找选手，未找到返回 ``None``。"""
    service, session = _open_service(store=store)
    try:
        return service.find_by_oj(platform, handle)
    finally:
        if session is not None:
            session.close()


def create_player(
    data: PlayerCreate,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """新建选手并持久化。"""
    service, session = _open_service(store=store)
    try:
        return service.create_player(data, today=today)
    finally:
        if session is not None:
            session.close()


def update_player(
    player_id: str,
    data: PlayerUpdate,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """更新选手字段并持久化。"""
    service, session = _open_service(store=store)
    try:
        return service.update_player(player_id, data, today=today)
    finally:
        if session is not None:
            session.close()


def delete_player(
    player_id: str,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """从名册物理删除选手。"""
    service, session = _open_service(store=store)
    try:
        return service.delete_player(player_id, today=today)
    finally:
        if session is not None:
            session.close()


def mark_left(
    player_id: str,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """将选手标记为离队（软删除，``status=left``）。"""
    service, session = _open_service(store=store)
    try:
        return service.mark_left(player_id, today=today)
    finally:
        if session is not None:
            session.close()


def mark_retired(
    player_id: str,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """将选手标记为退役（``status=retired``，档案与榜单保留）。"""
    service, session = _open_service(store=store)
    try:
        return service.mark_retired(player_id, today=today)
    finally:
        if session is not None:
            session.close()


def mark_active(
    player_id: str,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """将预备队员转为现役（入队考核通过）；仅 ``probation`` 状态可调用。"""
    service, session = _open_service(store=store)
    try:
        return service.mark_active(player_id, today=today)
    finally:
        if session is not None:
            session.close()
