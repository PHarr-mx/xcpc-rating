from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from team.models import Team


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for parent in [current, *current.parents]:
        if (parent / "data" / "config" / "school.yaml").is_file():
            return parent
    raise FileNotFoundError("无法定位仓库根目录（缺少 data/config/school.yaml）")


def make_member_key(members: list[str]) -> str:
    return "|".join(sorted(members))


def make_team_id(member_key: str) -> str:
    digest = hashlib.sha256(member_key.encode()).hexdigest()[:8]
    return f"t_{digest}"


class TeamStore:
    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        raw_path: Path | None = None,
    ) -> None:
        root = repo_root or find_repo_root()
        self.raw_path = raw_path or root / "data" / "raw" / "teams" / "roster.json"

    def load_all(self) -> list[Team]:
        raw_items = self._read_json_array(self.raw_path)
        teams = [Team.model_validate(item) for item in raw_items]
        return self._sort_teams(teams)

    def save_all(self, teams: list[Team], *, today: date | None = None) -> None:
        today = today or date.today()
        ordered = self._sort_teams(teams)
        raw_items: list[dict] = []

        for team in ordered:
            item = team.model_copy()
            if item.created_at is None:
                item.created_at = today
            raw_items.append(item.to_raw_dict())

        self._write_json_array(self.raw_path, raw_items)

    @staticmethod
    def _sort_teams(teams: list[Team]) -> list[Team]:
        return sorted(teams, key=lambda item: item.id)

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