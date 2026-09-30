from __future__ import annotations

from pathlib import Path

import yaml

from xcpc_core.player.store import find_repo_root


def _load_formal_entries(repo_root: Path | None = None) -> dict:
    root = repo_root or find_repo_root()
    path = root / "data" / "config" / "contest_weights.yaml"
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data.get("formal_types") or {}


def load_formal_types(*, repo_root: Path | None = None) -> dict[str, str]:
    """读取 contest_weights.yaml 的 formal_types：{contest_type: 中文标签}。"""
    return {
        str(key): str(entry.get("label", key))
        for key, entry in _load_formal_entries(repo_root).items()
    }


def load_formal_weight(contest_type: str, *, repo_root: Path | None = None) -> tuple[int, str]:
    entries = _load_formal_entries(repo_root)
    if contest_type not in entries:
        valid = "、".join(f"{key}({entry.get('label', key)})" for key, entry in entries.items())
        raise ValueError(f"未知 contest_type: {contest_type}（可用: {valid}）")
    entry = entries[contest_type]
    return int(entry["weight"]), str(entry.get("label", contest_type))
