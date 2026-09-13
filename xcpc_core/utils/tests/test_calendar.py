"""calendar 日历工具：赛年/赛季标签 + 周期 → 日期区间解析（盲区补齐）。"""

from datetime import date

import pytest

from xcpc_core.utils.calendar import (
    competition_year,
    resolve_period_dates,
    season_label,
)


def test_competition_year_boundary():
    assert competition_year(date(2025, 9, 1)) == 2025
    assert competition_year(date(2026, 8, 31)) == 2025
    assert competition_year(date(2026, 9, 1)) == 2026
    assert competition_year(date(2025, 5, 18)) == 2024


def test_season_label_kinds():
    assert season_label(date(2025, 9, 15)) == "2025-秋学期"
    assert season_label(date(2026, 1, 10)) == "2025-秋学期"  # 跨年归前一年秋学期
    assert season_label(date(2026, 2, 20)) == "2026-寒假"
    assert season_label(date(2026, 5, 18)) == "2026-春学期"
    assert season_label(date(2026, 7, 30)) == "2026-暑假"


def test_resolve_competition_year():
    assert resolve_period_dates("competition_year", 2025) == (date(2025, 9, 1), date(2026, 8, 31))
    assert resolve_period_dates("competition_year", "2025") == (date(2025, 9, 1), date(2026, 8, 31))
    assert resolve_period_dates("competition_year", " 2025 ") == (date(2025, 9, 1), date(2026, 8, 31))


def test_resolve_season_kinds():
    assert resolve_period_dates("season", "2025-秋学期") == (date(2025, 9, 1), date(2026, 1, 31))
    assert resolve_period_dates("season", "2026-寒假") == (date(2026, 2, 1), date(2026, 2, 28))
    assert resolve_period_dates("season", "2024-寒假") == (date(2024, 2, 1), date(2024, 2, 29))  # 闰月
    assert resolve_period_dates("season", "2026-春学期") == (date(2026, 3, 1), date(2026, 6, 30))
    assert resolve_period_dates("season", "2026-暑假") == (date(2026, 7, 1), date(2026, 8, 31))


def test_resolve_invalid_returns_none():
    assert resolve_period_dates("career", None) is None
    assert resolve_period_dates("competition_year", None) is None
    assert resolve_period_dates("competition_year", "bogus") is None
    assert resolve_period_dates("competition_year", 12345) is None  # 越界年份
    assert resolve_period_dates("season", "bogus") is None
    assert resolve_period_dates("season", "2025-不存在") is None
    assert resolve_period_dates("season", "秋学期") is None  # 缺年份
    assert resolve_period_dates("weird", "x") is None
