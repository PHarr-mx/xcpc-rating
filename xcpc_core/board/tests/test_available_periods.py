"""available_periods 选项枚举 + 解析后的赛年/赛季过滤真实生效（接线测试）。"""

from datetime import date

from xcpc_core.board.api import available_periods
from xcpc_core.board.service import BoardService
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.service import ContestService
from xcpc_core.contest.store import ContestStore
from xcpc_core.player.models import PlayerCreate
from xcpc_core.player.service import PlayerService
from xcpc_core.player.store import PlayerStore
from xcpc_core.rating.models import PeriodFilter


def _seed_player_and_contests(session) -> None:
    PlayerService(PlayerStore(session)).create_player(
        PlayerCreate(name="张三", handle="zs", grade=2023)
    )
    contest_service = ContestService(ContestStore(session))
    # 三场分属：2025-秋学期（2025-09~2026-01）、2026-春学期、2026-暑假，均在 2025 赛年内
    contest_service.save_contest(ContestCreate(
        id="c_autumn", title="秋学期赛", date=date(2025, 10, 1), contest_type="icpc_school",
        total_teams=10, standings=[Standing(team_name="一队", rank=1, solved=5, player_ids=["p001"])],
    ))
    contest_service.save_contest(ContestCreate(
        id="c_spring", title="春学期赛", date=date(2026, 3, 15), contest_type="icpc_school",
        total_teams=10, standings=[Standing(team_name="一队", rank=2, solved=5, player_ids=["p001"])],
    ))
    contest_service.save_contest(ContestCreate(
        id="c_summer", title="暑假赛", date=date(2026, 7, 1), contest_type="icpc_school",
        total_teams=10, standings=[Standing(team_name="一队", rank=1, solved=5, player_ids=["p001"])],
    ))


def test_available_periods_covers_data_span(db_session):
    _seed_player_and_contests(db_session)
    options = available_periods(session=db_session)

    assert options[0] == {"key": "career", "period_type": "career", "id": None, "label": "生涯"}
    keys = [opt["key"] for opt in options]
    # 数据最早 2025-10-01 → competition_year 2025；赛年 2025 的四季：
    assert "competition_year:2025" in keys
    assert "season:2025-秋学期" in keys
    assert "season:2026-寒假" in keys
    assert "season:2026-春学期" in keys
    assert "season:2026-暑假" in keys
    # 不应出现数据范围之外的赛年
    assert "competition_year:2024" not in keys and "competition_year:2026" not in keys


def test_available_periods_empty_db(db_session):
    assert available_periods(session=db_session) == [
        {"key": "career", "period_type": "career", "id": None, "label": "生涯"}
    ]


def test_resolved_season_filter_actually_filters(db_session):
    """修复点：type+id（无显式日期）过去不参与过滤，现在必须真实过滤。"""
    _seed_player_and_contests(db_session)

    autumn = PeriodFilter(type="season", id="2025-秋学期")
    snap = BoardService(db_session).build(mode="all", period=autumn)
    (row,) = snap.rows
    assert row.event_count == 1  # 只算了秋学期那场
    assert snap.meta.start == date(2025, 9, 1) and snap.meta.end == date(2026, 1, 31)

    spring = PeriodFilter(type="season", id="2026-春学期")
    snap_spring = BoardService(db_session).build(mode="all", period=spring)
    (row_spring,) = snap_spring.rows
    assert row_spring.event_count == 1 and row_spring.rating != row.rating


def test_resolved_competition_year_filters(db_session):
    _seed_player_and_contests(db_session)

    cy2025 = PeriodFilter(type="competition_year", id="2025")
    snap = BoardService(db_session).build(mode="all", period=cy2025)
    (row,) = snap.rows
    assert row.event_count == 3  # 三场都在 2025 赛年（2025-09 ~ 2026-08）

    cy2024 = PeriodFilter(type="competition_year", id="2024")
    snap_2024 = BoardService(db_session).build(mode="all", period=cy2024)
    assert snap_2024.rows == []  # 数据范围之外
