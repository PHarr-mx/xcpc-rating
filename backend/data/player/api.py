"""选手模块对外编程接口。

CLI（``player.cli``）与本模块共用同一套函数；其他 backend 子模块应从此处导入，
勿直接读写 JSON 文件。
"""

from __future__ import annotations

from datetime import date

from player.models import Player, PlayerCreate, PlayerStatus, PlayerUpdate
from player.service import PlayerService
from player.store import PlayerStore

_default_store: PlayerStore | None = None


def configure_store(store: PlayerStore) -> None:
    """为当前进程设置默认数据存储（测试或自定义路径时使用）。"""
    global _default_store
    _default_store = store


def get_service(*, store: PlayerStore | None = None) -> PlayerService:
    """获取 ``PlayerService`` 实例。"""
    resolved = store or _default_store
    return PlayerService(resolved) if resolved is not None else PlayerService()


def list_players(
    *,
    include_left: bool = True,
    status: PlayerStatus | None = None,
    grade: int | None = None,
    store: PlayerStore | None = None,
) -> list[Player]:
    """列出选手，支持按状态、年级筛选。"""
    return get_service(store=store).list_players(
        include_left=include_left,
        status=status,
        grade=grade,
    )


def get_player(player_id: str, *, store: PlayerStore | None = None) -> Player:
    """按校内 ID 查询单个选手。"""
    return get_service(store=store).get_player(player_id)


def find_by_name(
    name: str,
    *,
    grade: int | None = None,
    store: PlayerStore | None = None,
) -> list[Player]:
    """按姓名或别名查找选手。"""
    return get_service(store=store).find_by_name(name, grade=grade)


def find_by_oj(
    platform: str,
    handle: str,
    *,
    store: PlayerStore | None = None,
) -> Player | None:
    """按 OJ 平台账号查找选手，未找到返回 ``None``。"""
    return get_service(store=store).find_by_oj(platform, handle)


def create_player(
    data: PlayerCreate,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """新建选手并持久化。"""
    return get_service(store=store).create_player(data, today=today)


def update_player(
    player_id: str,
    data: PlayerUpdate,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """更新选手字段并持久化。"""
    return get_service(store=store).update_player(player_id, data, today=today)


def delete_player(
    player_id: str,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """从名册物理删除选手。"""
    return get_service(store=store).delete_player(player_id, today=today)


def mark_left(
    player_id: str,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player:
    """将选手标记为离队（软删除，``status=left``）。"""
    return get_service(store=store).mark_left(player_id, today=today)
