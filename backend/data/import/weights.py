from __future__ import annotations

from pathlib import Path

import yaml

from player.store import find_repo_root


def load_formal_weight(contest_type: str, *, repo_root: Path | None = None) -> tuple[int, str]:
    root = repo_root or find_repo_root()
    path = root / "data" / "config" / "contest_weights.yaml"
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    formal_types = data.get("formal_types") or {}
    if contest_type not in formal_types:
        raise ValueError(f"未知 contest_type: {contest_type}")
    entry = formal_types[contest_type]
    return int(entry["weight"]), str(entry.get("label", contest_type))
