"""PeriodFilter：赛年/赛季 type+id 自动解析为 start/end（接线测试）。"""

from datetime import date

from xcpc_core.rating.models import PeriodFilter


def test_competition_year_resolved():
    period = PeriodFilter(type="competition_year", id="2025")
    assert period.start == date(2025, 9, 1)
    assert period.end == date(2026, 8, 31)


def test_season_resolved():
    period = PeriodFilter(type="season", id="2025-秋学期")
    assert period.start == date(2025, 9, 1)
    assert period.end == date(2026, 1, 31)


def test_explicit_dates_win():
    period = PeriodFilter(type="season", id="2025-秋学期", start=date(2025, 10, 1), end=date(2025, 10, 31))
    assert period.start == date(2025, 10, 1)
    assert period.end == date(2025, 10, 31)


def test_career_and_unparseable_stay_none():
    assert PeriodFilter().start is None
    assert PeriodFilter(type="career", id="2025").start is None
    bogus = PeriodFilter(type="season", id="bogus")  # 手输 URL 等非法值 → 不过滤
    assert bogus.start is None and bogus.end is None
