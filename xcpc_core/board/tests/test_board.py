"""榜单模块测试（docs/07）：聚合、排名、过滤、缓存。"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from xcpc_core.board import api as board_api
from xcpc_core.board.models import BoardSnapshot
from xcpc_core.board.service import BoardService
from xcpc_core.contest import api as contest_api
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.base import Base
from xcpc_core.db import tables  # noqa: F401  注册全部表
from xcpc_core.player.models import Player, PlayerStatus
from xcpc_core.player.store import PlayerStore
from xcpc_core.rating.models import PeriodFilter


@pytest.fixture(autouse=True)
def _clear_board_cache():
    board_api._cache.clear()
    yield
    board_api._cache.clear()


@pytest.fixture(autouse=True)
def _use_test_contest_store(db_session):
    contest_api.configure_store(ContestStore(db_session))
    yield
    contest_api.configure_store(None)


def _player(player_id: str, *, name: str, grade: int = 0, status: PlayerStatus = PlayerStatus.active) -> Player:
    return Player(id=player_id, name=name, grade=grade, status=status)


def _save_players(session, *players: Player) -> None:
    store = PlayerStore(session)
    for player in players:
        store.insert(player)


def _save_contest(
    *,
    contest_id: str,
    date_: date,
    standings: list[Standing],
    weight: int = 70,
    total_teams: int = 86,
) -> None:
    contest_api.save_contest(ContestCreate(
        id=contest_id,
        title=f"测试比赛 {contest_id}",
        date=date_,
        contest_type="icpc_provincial",
        format="team_xcpc",
        total_teams=total_teams,
        school_teams_count=len(standings),
        weight=weight,
        standings=standings,
    ))


def test_board_basic_structure_and_rank_ties(db_session):
    _save_players(
        db_session,
        _player("p001", name="张三", grade=2024),
        _player("p002", name="李四", grade=0),
        _player("p003", name="王五", grade=2023),
        _player("p004", name="赵六", grade=2025),
    )
    _save_contest(
        contest_id="c1",
        date_=date(2026, 5, 18),
        standings=[
            Standing(team_id="t001", team_name="一队", rank=1, award="gold", solved=8,
                     player_ids=["p001", "p002"]),
            Standing(team_id="t002", team_name="二队", rank=2, award="silver", solved=7,
                     player_ids=["p003", "p004"]),
        ],
    )

    snap = BoardService(db_session).build(mode="all")

    assert isinstance(snap, BoardSnapshot)
    # meta
    assert snap.meta.mode == "all"
    assert snap.meta.period_type == "career"
    assert snap.meta.period_id is None
    assert snap.meta.period_label == "生涯"
    assert snap.meta.algorithm == "placeholder_v0"
    assert snap.meta.data_version == 0
    assert snap.meta.generated_at is not None
    # 行：4 名选手，按 rating 降序
    assert [r.player_id for r in snap.rows] == ["p001", "p002", "p003", "p004"]
    # 同队同分 → 竞赛排名 1,1,3,3（同分同 rank、下一名跳号）
    assert [r.rank for r in snap.rows] == [1, 1, 3, 3]
    assert snap.rows[0].rating == pytest.approx(980.0)
    assert snap.rows[2].rating == pytest.approx(936.86, abs=0.01)
    # 展示字段
    assert snap.rows[0].name == "张三"
    assert snap.rows[0].grade_label == "2024级"
    assert snap.rows[1].grade_label == "未设置"
    # 仅一场比赛：delta_recent == rating
    assert snap.rows[0].event_count == 1
    assert snap.rows[0].delta_recent == pytest.approx(snap.rows[0].rating)


def test_board_excludes_left_players(db_session):
    _save_players(
        db_session,
        _player("p001", name="张三"),
        _player("p002", name="李四"),
        _player("p003", name="王五", status=PlayerStatus.left),
    )
    _save_contest(
        contest_id="c1",
        date_=date(2026, 5, 18),
        standings=[
            Standing(team_id="t001", team_name="一队", rank=1, player_ids=["p001", "p002"]),
            Standing(team_id="t002", team_name="二队", rank=2, player_ids=["p003"]),
        ],
    )

    snap = BoardService(db_session).build(mode="all")

    assert [r.player_id for r in snap.rows] == ["p001", "p002"]  # 离队 p003 不出现


def test_board_period_filter_and_delta_recent(db_session):
    _save_players(db_session, _player("p001", name="张三"))
    # 两场比赛，rank 不同 → 得分不同，便于区分 delta_recent
    _save_contest(
        contest_id="c_a",
        date_=date(2026, 3, 15),
        weight=100,
        total_teams=10,
        standings=[Standing(team_id="t001", team_name="一队", rank=1, solved=5, player_ids=["p001"])],
    )
    _save_contest(
        contest_id="c_b",
        date_=date(2026, 4, 20),
        weight=100,
        total_teams=10,
        standings=[Standing(team_id="t001", team_name="一队", rank=3, solved=5, player_ids=["p001"])],
    )

    # 整个春学期：两场都算，delta_recent = 最近一场（c_b）的得分
    spring = PeriodFilter(type="season", id="2026-春学期", start=date(2026, 3, 1), end=date(2026, 6, 30))
    snap = BoardService(db_session).build(mode="all", period=spring)
    row = snap.rows[0]
    assert row.event_count == 2
    assert row.rating == pytest.approx(1250.0 + 1050.0)
    assert row.delta_recent == pytest.approx(1050.0)

    # 只含 3 月：只有 c_a，delta_recent = c_a 得分
    march = PeriodFilter(type="season", id="2026-春学期", start=date(2026, 3, 1), end=date(2026, 3, 31))
    snap_march = BoardService(db_session).build(mode="all", period=march)
    row_march = snap_march.rows[0]
    assert row_march.event_count == 1
    assert row_march.rating == pytest.approx(1250.0)
    assert row_march.delta_recent == pytest.approx(1250.0)


def test_board_competition_year_label_and_filter(db_session):
    _save_players(db_session, _player("p001", name="张三"), _player("p002", name="李四"))
    _save_contest(
        contest_id="c_in",
        date_=date(2026, 5, 18),  # 属 2025 赛年（2025-09-01 ~ 2026-08-31）
        standings=[Standing(team_id="t001", team_name="一队", rank=1, player_ids=["p001"])],
    )
    _save_contest(
        contest_id="c_out",
        date_=date(2026, 9, 5),  # 属 2026 赛年，2025 赛年窗口外
        standings=[Standing(team_id="t001", team_name="一队", rank=1, player_ids=["p002"])],
    )

    cy = PeriodFilter(type="competition_year", id=2025, start=date(2025, 9, 1), end=date(2026, 8, 31))
    snap = BoardService(db_session).build(mode="all", period=cy)

    assert snap.meta.period_type == "competition_year"
    assert snap.meta.period_id == 2025
    assert snap.meta.period_label == "2025赛年"
    assert [r.player_id for r in snap.rows] == ["p001"]  # c_out 被窗口排除


def test_board_api_with_injected_session_does_not_cache(db_session):
    _save_players(db_session, _player("p001", name="张三"))
    _save_contest(
        contest_id="c1",
        date_=date(2026, 5, 18),
        standings=[Standing(team_id="t001", team_name="一队", rank=1, player_ids=["p001"])],
    )

    snap1 = board_api.board(mode="all", session=db_session)
    snap2 = board_api.board(mode="all", session=db_session)

    assert snap1 is not snap2  # 注入 session 不走缓存
    assert snap1.meta.period_label == snap2.meta.period_label
    assert [r.player_id for r in snap1.rows] == [r.player_id for r in snap2.rows]


def test_board_api_cache_hit_and_invalidation(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(board_api, "_get_default_factory", lambda: factory)

    with factory() as session:
        _save_players(session, _player("p001", name="张三"))
        _save_contest(
            contest_id="c1",
            date_=date(2026, 5, 18),
            standings=[Standing(team_id="t001", team_name="一队", rank=1, player_ids=["p001"])],
        )

    snap1 = board_api.board(mode="all")
    snap2 = board_api.board(mode="all")
    assert snap1 is snap2  # 缓存命中（同一对象）

    # data_version bump → 缓存失效
    from xcpc_core.db.tables import Meta as MetaRow

    with factory() as session:
        session.add(MetaRow(id=1, data_version=1))
        session.commit()
    snap3 = board_api.board(mode="all")
    assert snap3 is not snap1
    assert snap3.meta.data_version == 1

    # invalidate() → 强制失效
    board_api.invalidate()
    snap4 = board_api.board(mode="all")
    assert snap4 is not snap3
