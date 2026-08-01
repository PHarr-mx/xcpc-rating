from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def raw_contest_basename(contest_id: str) -> str:
    if contest_id.startswith("formal_"):
        return contest_id.removeprefix("formal_")
    return contest_id


def raw_contest_rel_path(contest_id: str) -> str:
    return f"raw/formal/{raw_contest_basename(contest_id)}.json"


def raw_contest_path(repo_root: Path, contest_id: str) -> Path:
    return repo_root / "data" / raw_contest_rel_path(contest_id)


def load_raw_contest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"正式赛 raw 文件不存在: {path}")
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} 必须是 JSON 对象")
    return data


def save_raw_contest(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(document, file, ensure_ascii=False, indent=2)
        file.write("\n")


def update_standings_counts(document: dict[str, Any]) -> None:
    standings = document.get("standings") or []
    document["school_teams_awarded"] = len(standings)
    manual_count = sum(1 for row in standings if row.get("manually_added"))
    auto_count = len(standings) - manual_count
    if manual_count:
        document["school_teams_manual"] = manual_count
    elif "school_teams_manual" in document:
        document.pop("school_teams_manual", None)
    if auto_count == 0 and "school_teams_count" not in document:
        pass
