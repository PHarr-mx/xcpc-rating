from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from xcpc_core.player.store import find_repo_root


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


# 赛年/赛季规则下沉到 utils.calendar，此处重导出保持兼容
from xcpc_core.utils.calendar import competition_year, season_label  # noqa: F401
