"""队伍模块对外编程接口。

CLI（``team.cli``）与本模块共用同一套函数；其他 core 子模块应从此处导入，
勿直接读写数据库。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import sessionmaker

from xcpc_core.db.session import make_session_factory
from xcpc_core.team.models import Team, TeamCreate, TeamUpdate
from xcpc_core.team.service import TeamService
from xcpc_core.team.store import TeamStore

_default_store: TeamStore | None = None
_factory: sessionmaker | None = None


def configure_store(store: TeamStore) -> None:
    """为当前进程设置默认数据存储（测试或自定义路径时使用）。"""
    global _default_store
    _default_store = store


def _get_default_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory


def get_service(*, store: TeamStore | None = None) -> TeamService:
    """获取 ``TeamService`` 实例。"""
    resolved = store or _default_store
    if resolved is not None:
        return TeamService(resolved)
    return TeamService(TeamStore(_get_default_factory()()))


def list_teams(
    *,
    store: TeamStore | None = None,
) -> list[Team]:
    """列出所有队伍。"""
    return get_service(store=store).list_teams()


def get_team(team_id: str, *, store: TeamStore | None = None) -> Team:
    """按 ID 查询单个队伍。"""
    return get_service(store=store).get_team(team_id)


def find_by_members(
    members: list[str],
    *,
    store: TeamStore | None = None,
) -> Team | None:
    """按队员集合查找队伍，未找到返回 ``None``。"""
    return get_service(store=store).find_by_members(members)


def create_team(
    data: TeamCreate,
    *,
    today: date | None = None,
    store: TeamStore | None = None,
) -> Team:
    """新建队伍并持久化。"""
    return get_service(store=store).create_team(data, today=today)


def update_team(
    team_id: str,
    data: TeamUpdate,
    *,
    today: date | None = None,
    store: TeamStore | None = None,
) -> Team:
    """更新队伍字段并持久化。"""
    return get_service(store=store).update_team(team_id, data, today=today)


def delete_team(
    team_id: str,
    *,
    today: date | None = None,
    store: TeamStore | None = None,
) -> Team:
    """从名册物理删除队伍。"""
    return get_service(store=store).delete_team(team_id, today=today)