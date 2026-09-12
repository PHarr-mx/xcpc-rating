"""data_version 自动 bump（评审项 ⑪）。

写路径（player / contest service 写方法）在业务提交前 bump ``meta.data_version``，
令榜单进程内缓存按新版本号自然失效——此前缓存 key 永远不变，写库后榜单页在
进程存活期间一直命中旧快照。

- bump 语义：无行建行 1，有行加一；只 flush 不 commit，随调用方事务提交/回滚。
- service 接线：create/update/delete（player）、save/delete（contest）。
- 端到端：board_api.board()（走缓存路径）在写操作后必须给出新快照。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from xcpc_core.board import api as board_api
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.service import ContestService
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.base import Base
from xcpc_core.db import tables  # noqa: F401  注册全部表
from xcpc_core.db.meta import bump_data_version
from xcpc_core.db.tables import Meta as MetaRow
from xcpc_core.player.models import PlayerCreate, PlayerStatus, PlayerUpdate
from xcpc_core.player.service import PlayerService
from xcpc_core.player.store import PlayerStore
from xcpc_core.rating.models import PeriodFilter


def _read_version(session) -> int:
    row = session.get(MetaRow, 1)
    return 0 if row is None else row.data_version


def _make_player_service(session) -> PlayerService:
    return PlayerService(PlayerStore(session))


def _make_contest_service(session) -> ContestService:
    return ContestService(ContestStore(session))


# ---- bump 语义 ----

def test_bump_creates_row_and_increments(db_session):
    assert _read_version(db_session) == 0  # 无行
    assert bump_data_version(db_session) == 1
    assert bump_data_version(db_session) == 2
    db_session.commit()
    assert _read_version(db_session) == 2


def test_bump_rolls_back_with_transaction(db_session):
    """bump 只 flush 不提交：事务回滚时版本推进一并回滚。"""
    assert bump_data_version(db_session) == 1
    db_session.rollback()
    assert _read_version(db_session) == 0


# ---- service 接线 ----

def test_player_writes_bump(db_session):
    service = _make_player_service(db_session)

    service.create_player(PlayerCreate(name="张三", handle="zs", grade=2023))
    assert _read_version(db_session) == 1

    service.update_player("p001", PlayerUpdate(grade=2023))
    assert _read_version(db_session) == 2

    service.mark_left("p001")
    assert _read_version(db_session) == 3

    service.delete_player("p001")
    assert _read_version(db_session) == 4


def test_contest_writes_bump(db_session):
    service = _make_contest_service(db_session)
    data = ContestCreate(
        id="c1", title="测试赛", date=date(2026, 5, 1), contest_type="icpc_school",
        total_teams=10, standings=[Standing(team_name="一队", rank=1, solved=5, player_ids=["p001"])],
    )

    service.save_contest(data)  # insert
    assert _read_version(db_session) == 1

    service.save_contest(data)  # 已存在 → 整批替换（update）
    assert _read_version(db_session) == 2

    service.delete_contest("c1")
    assert _read_version(db_session) == 3

    service.delete_contest("c1")  # 不存在 → 静默 no-op，不 bump
    assert _read_version(db_session) == 3


def test_player_create_bump_rolls_back_on_unique_conflict(db_session):
    """唯一约束冲突时整个事务回滚，版本推进不残留。"""
    service = _make_player_service(db_session)
    service.create_player(PlayerCreate(name="张三", handle="zs", grade=2023))
    assert _read_version(db_session) == 1

    from xcpc_core.player.exceptions import PlayerValidationError
    try:
        service.create_player(PlayerCreate(name="李四", handle="zs", grade=2024))
        raise AssertionError("应当抛出唯一性冲突")
    except PlayerValidationError:
        pass
    assert _read_version(db_session) == 1


# ---- 端到端：榜单缓存失效 ----

def _make_isolated_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_board_cache_invalidated_by_write(monkeypatch):
    """写操作提交后，board()（走缓存路径）必须给出新快照——修复前这里命中旧缓存。"""
    factory = _make_isolated_factory()
    monkeypatch.setattr(board_api, "_factory", factory)
    monkeypatch.setattr(board_api, "_cache", {})

    with factory() as s:
        _make_player_service(s).create_player(PlayerCreate(name="张三", handle="zs", grade=2023))
        _make_contest_service(s).save_contest(ContestCreate(
            id="c1", title="测试赛", date=date(2026, 5, 1), contest_type="icpc_school",
            total_teams=10, standings=[Standing(team_name="一队", rank=1, solved=5, player_ids=["p001"])],
        ))

    period = PeriodFilter()
    snap1 = board_api.board(mode="all", period=period)
    assert [row.player_id for row in snap1.rows] == ["p001"]
    assert board_api.board(mode="all", period=period) is snap1  # 数据未变 → 缓存命中

    with factory() as s:
        _make_player_service(s).mark_left("p001")  # 离队 → 不再出现在榜单

    snap2 = board_api.board(mode="all", period=period)
    assert snap2.rows == []
    assert snap2.meta.data_version == snap1.meta.data_version + 1


def test_meta_row_created_with_default_algorithm(db_session):
    """meta 行由首次写路径创建，rating_algorithm 走列默认值。"""
    _make_player_service(db_session).create_player(PlayerCreate(name="张三", grade=0))
    db_session.commit()
    row = db_session.get(MetaRow, 1)
    assert row.data_version == 1
    assert row.rating_algorithm == "placeholder_v0"
