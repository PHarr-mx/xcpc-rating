"""赛年与赛季日历工具。

- 赛年：当年 9/1 至次年 8/31（见 docs/07-榜单模块.md §3.2）
- 赛季：秋学期 / 寒假 / 春学期 / 暑假 四类（见 docs/07 §3.3）
"""

from __future__ import annotations

from datetime import date, timedelta

_MIN_YEAR = 2000
_MAX_YEAR = 2100


def competition_year(value: date) -> int:
    if value.month >= 9:
        return value.year
    return value.year - 1


def season_label(value: date) -> str:
    month = value.month
    year = value.year
    if month in (9, 10, 11, 12, 1):
        label_year = year if month >= 9 else year - 1
        return f"{label_year}-秋学期"
    if month == 2:
        return f"{year}-寒假"
    if month in (3, 4, 5, 6):
        return f"{year}-春学期"
    return f"{year}-暑假"


def _parse_year(value: object) -> int | None:
    try:
        year = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return year if _MIN_YEAR <= year <= _MAX_YEAR else None


def _month_end(year: int, month: int) -> date:
    """该月最后一天（下月 1 号前一天，自动处理闰月）。"""
    next_year = year + (month == 12)
    next_month = month % 12 + 1
    return date(next_year, next_month, 1) - timedelta(days=1)


def resolve_period_dates(
    period_type: str,
    period_id: str | int | None,
) -> tuple[date, date] | None:
    """把具体周期解析为闭区间 (start, end)。

    - ``competition_year`` + ``2025`` → 2025-09-01 ~ 2026-08-31
    - ``season`` + ``2025-秋学期`` → 2025-09-01 ~ 2026-01-31（寒假/春/暑假同理）
    - ``career`` 或 id 无法解析 → ``None``（调用方不过滤日期）
    """
    if period_type == "competition_year":
        year = _parse_year(period_id)
        if year is None:
            return None
        return date(year, 9, 1), date(year + 1, 8, 31)

    if period_type == "season":
        text = str(period_id or "").strip()
        year_text, sep, kind = text.partition("-")
        if not sep:
            return None
        year = _parse_year(year_text)
        if year is None:
            return None
        if kind == "秋学期":
            return date(year, 9, 1), date(year + 1, 1, 31)
        if kind == "寒假":
            return date(year, 2, 1), _month_end(year, 2)
        if kind == "春学期":
            return date(year, 3, 1), date(year, 6, 30)
        if kind == "暑假":
            return date(year, 7, 1), date(year, 8, 31)
    return None
