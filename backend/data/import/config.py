from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from player.store import find_repo_root


def load_school_organizations(*, repo_root: Path | None = None) -> list[str]:
    root = repo_root or find_repo_root()
    path = root / "data" / "config" / "school.yaml"
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    organizations = data.get("organizations") or []
    if not organizations:
        raise ValueError(f"{path} 缺少 organizations 配置")
    return [str(item) for item in organizations]


def load_default_player_grade(
    *,
    repo_root: Path | None = None,
    override: int | None = None,
) -> int:
    if override is not None:
        return override
    root = repo_root or find_repo_root()
    path = root / "data" / "config" / "school.yaml"
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    grade = (data.get("player_defaults") or {}).get("grade")
    if grade is None:
        raise ValueError(f"{path} 缺少 player_defaults.grade，导入自动建档时需要指定入学年")
    return int(grade)


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
