"""raw 归档读写。

归档目录有两处（P-U3，2026-10-26 起）：
- ``raw/formal/{id}.json``  —— 正式赛 xlsx 导入产物（历史位置，保留写回）
- ``raw/contests/{id}.json`` —— 通用比赛 JSON 导入产物（P-U3 新位置）

读取侧用 :func:`resolve_raw_contest_path` 做「新目录优先、旧目录回退」，
因此存量正式赛文件无需搬迁；写入侧按 ``kind`` 决定落哪个目录。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FORMAL_KIND = "formal"
CONTESTS_KIND = "contests"

#: 读取时的目录搜索顺序（新目录优先）
_READ_ORDER = (CONTESTS_KIND, FORMAL_KIND)


def raw_contest_basename(contest_id: str) -> str:
    if contest_id.startswith("formal_"):
        return contest_id.removeprefix("formal_")
    return contest_id


def raw_contest_rel_path(contest_id: str, *, kind: str = FORMAL_KIND) -> str:
    """``kind`` 缺省为 ``formal``，保持正式赛既有口径与测试不变。"""
    return f"raw/{kind}/{raw_contest_basename(contest_id)}.json"


def raw_contest_path(repo_root: Path, contest_id: str, *, kind: str = FORMAL_KIND) -> Path:
    """按 ``kind`` 计算归档文件路径（**不做回退**，供写入与精确读取）。"""
    return repo_root / "data" / raw_contest_rel_path(contest_id, kind=kind)


def resolve_raw_contest_path(repo_root: Path, contest_id: str) -> Path:
    """读取用：依次在 ``raw/contests/``、``raw/formal/`` 查找，返回首个存在的路径。

    两处都不存在时返回新目录路径（让调用方的 FileNotFoundError 指向推荐位置）。
    """
    for kind in _READ_ORDER:
        candidate = raw_contest_path(repo_root, contest_id, kind=kind)
        if candidate.is_file():
            return candidate
    return raw_contest_path(repo_root, contest_id, kind=CONTESTS_KIND)


def iter_raw_contest_files(repo_root: Path) -> list[Path]:
    """两个归档目录下的全部 ``*.json``（按路径排序，供 migrate 重灌）。"""
    files: list[Path] = []
    for kind in _READ_ORDER:
        directory = repo_root / "data" / "raw" / kind
        if directory.is_dir():
            files.extend(sorted(directory.glob("*.json")))
    return files


def load_raw_contest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"比赛 raw 文件不存在: {path}")
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