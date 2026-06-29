from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from player.models import Player


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for parent in [current, *current.parents]:
        if (parent / "data" / "raw" / "players" / "roster.json").is_file():
            return parent
    raise FileNotFoundError("无法定位仓库根目录（缺少 data/raw/players/roster.json）")


class PlayerStore:
    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        raw_path: Path | None = None,
        processed_path: Path | None = None,
    ) -> None:
        root = repo_root or find_repo_root()
        self.raw_path = raw_path or root / "data" / "raw" / "players" / "roster.json"
        self.processed_path = processed_path or root / "data" / "processed" / "players.json"

    def load_all(self) -> list[Player]:
        raw_items = self._read_json_array(self.raw_path)
        players = [Player.model_validate(item) for item in raw_items]
        return self._sort_players(players)

    def save_all(self, players: list[Player], *, today: date | None = None) -> None:
        today = today or date.today()
        ordered = self._sort_players(players)
        enriched: list[Player] = []
        raw_items: list[dict] = []

        for player in ordered:
            item = player.model_copy()
            if item.created_at is None:
                item.created_at = today
            item = item.with_derived_fields(today=today)
            enriched.append(item)
            raw_items.append(item.to_raw_dict())

        self._write_json_array(self.raw_path, raw_items)
        self.processed_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_array(
            self.processed_path,
            [player.model_dump(mode="json") for player in enriched],
        )

    def next_id(self, grade: int, players: list[Player] | None = None) -> str:
        players = players if players is not None else self.load_all()
        prefix = f"p{grade}"
        max_seq = 0
        for player in players:
            if player.id.startswith(prefix) and len(player.id) > len(prefix):
                suffix = player.id[len(prefix) :]
                if suffix.isdigit():
                    max_seq = max(max_seq, int(suffix))
        return f"{prefix}{max_seq + 1:03d}"

    @staticmethod
    def _sort_players(players: list[Player]) -> list[Player]:
        return sorted(players, key=lambda item: item.id)

    @staticmethod
    def _read_json_array(path: Path) -> list[dict]:
        if not path.is_file():
            return []
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError(f"{path} 必须是 JSON 数组")
        return data

    @staticmethod
    def _write_json_array(path: Path, items: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False, indent=2)
            file.write("\n")
