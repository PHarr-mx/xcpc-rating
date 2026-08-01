"""赛年与赛季日历工具。

- 赛年：当年 9/1 至次年 8/31（见 docs/07-榜单模块.md §3.2）
- 赛季：秋学期 / 寒假 / 春学期 / 暑假 四类（见 docs/07 §3.3）
"""

from __future__ import annotations

from datetime import date


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
