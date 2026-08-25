"""回归：core API facade 自建会话必须在调用后关闭。

背景（2026-08-25）：`player/team/contest/audit.api` 每次调用都从默认工厂新建
session，却从不 close —— SQLAlchemy 2.0 中 session 借出的连接要到 close/commit
才归还连接池。单进程顺序调用靠 GC 侥幸回收；Reflex 多线程并发处理事件（computed
var 每次 delta 都会重算）时会同时检出多个连接，撞满默认 QueuePool(5+10=15) 上限，
表现为「什么都点不了」（QueuePool 超时 30s）。

本测试用 pool_size=1 的临时文件库接管各模块 `_factory`，若某次调用没关闭自建
session，下一次调用就会在 pool_timeout 内抛 TimeoutError。
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from xcpc_core import contest as contest_mod
from xcpc_core import player as player_mod
from xcpc_core import team as team_mod
from xcpc_core.audit import api as audit_api
from xcpc_core.contest import api as contest_api
from xcpc_core.db.base import Base
from xcpc_core.db import tables  # noqa: F401  注册全部表
from xcpc_core.player import api as player_api
from xcpc_core.team import api as team_api


@pytest.fixture
def leak_guard(tmp_path):
    """接管各 facade 的默认 factory 为单连接池，测试后复位。"""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'leak.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=2,  # 泄漏时快速失败，避免 30s 挂起
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # 确保回落默认路径（自建 session），而非此前测试注入的 store。
    player_api.configure_store(None)
    team_api.configure_store(None)
    contest_api.configure_store(None)
    audit_api.configure_session(None)
    for api in (player_api, team_api, contest_api, audit_api):
        api._factory = factory  # type: ignore[attr-defined]
    try:
        yield
    finally:
        for api in (player_api, team_api, contest_api, audit_api):
            api._factory = None  # type: ignore[attr-defined]
        engine.dispose()


def test_facade_owned_sessions_are_closed(leak_guard):
    """读+写反复调用不耗尽单连接池（自建 session 均已关闭）。"""
    for _ in range(10):
        player_api.list_players()
        player_api.find_by_name("不存在的名字")
        created = player_api.create_player(
            player_mod.PlayerCreate(name="测试选手", grade=0, status="active")
        )
        player_api.list_players()
        team_api.list_teams()
        team_api.create_team(team_mod.TeamCreate(members=[created.id]))
        team_api.find_by_members([created.id])
        contest_api.list_contests()
        audit_api.record(action="test.session_lifecycle", target=created.id, user_id=1)
        audit_api.list_logs()


def test_facade_returns_dto_not_orm(leak_guard):
    """调用后 session 已关闭，返回的是脱离 ORM 的 DTO（可安全序列化）。"""
    created = player_api.create_player(
        player_mod.PlayerCreate(name="返回校验", grade=0, status="active")
    )
    assert created.id is not None
    # 若返回的是仍挂在已关闭 session 上的 ORM 行，访问惰性字段会抛 DetachedInstanceError。
    assert created.name == "返回校验"
    assert isinstance(created, player_mod.Player)
