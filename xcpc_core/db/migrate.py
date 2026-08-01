"""一次性把 data/raw 现有数据灌入 SQLite（幂等，可反复重跑）。

用法：
    uv run python -m xcpc_core.db.migrate

- 读 data/raw/players/roster.json、teams/roster.json、formal/*.json
- 按主键 upsert：已存在的选手/队伍更新，比赛则删旧成绩后重写
- 现有 ID（p001/t001）原样保留；created_at 缺失填迁移当日
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from xcpc_core.contest.api import save_contest
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.session import create_all, default_db_url, find_repo_root, make_session_factory
from xcpc_core.player.models import Player
from xcpc_core.player.store import PlayerStore
from xcpc_core.team.models import Team
from xcpc_core.team.store import TeamStore
from xcpc_core.utils.plog import Plog


def _load_json(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} 必须是 JSON 数组")
    return data


def migrate_players(session, *, today: date, plog: Plog) -> int:
    store = PlayerStore(session)
    raw_items = _load_json(find_repo_root() / "data/raw/players/roster.json")
    count = 0
    for item in raw_items:
        player = Player.model_validate(item)
        if player.created_at is None:
            player.created_at = today
        if store.get(player.id) is None:
            store.insert(player)
        else:
            store.update(player)
        count += 1
    plog.info("选手迁移完成", total=count)
    return count


def migrate_teams(session, *, today: date, plog: Plog) -> int:
    store = TeamStore(session)
    raw_items = _load_json(find_repo_root() / "data/raw/teams/roster.json")
    count = 0
    for item in raw_items:
        team = Team.model_validate(item)
        if team.created_at is None:
            team.created_at = today
        if store.get(team.id) is None:
            store.insert(team)
        else:
            store.update(team)
        count += 1
    plog.info("队伍迁移完成", total=count)
    return count


def migrate_formal_contests(session, *, plog: Plog) -> int:
    raw_dir = find_repo_root() / "data/raw/formal"
    files = sorted(raw_dir.glob("*.json")) if raw_dir.is_dir() else []
    store = ContestStore(session)
    count = 0
    for path in files:
        with path.open(encoding="utf-8") as file:
            doc = json.load(file)
        contest = ContestCreate(
            id=doc["contest_id"],
            source_type="formal",
            title=doc["title"],
            date=date.fromisoformat(doc["date"]),
            contest_type=doc.get("contest_type"),
            format=doc.get("format", "team_xcpc"),
            total_teams=doc.get("total_teams"),
            school_teams_count=doc.get("school_teams_count"),
            rated=doc.get("rated", True),
            weight=doc.get("weight", 100),
            weight_source=doc.get("weight_source", "config"),
            source_file=f"raw/formal/{path.name}",
            standings=[
                Standing(
                    team_id=row.get("team_id"),
                    team_name=row.get("team_name"),
                    rank=row["rank"],
                    school_rank=row.get("school_rank"),
                    award=row.get("award"),
                    solved=row.get("solved"),
                    penalty=row.get("penalty"),
                    score=row.get("score"),
                    manually_added=row.get("manually_added", False),
                    player_ids=row.get("player_ids") or [],
                )
                for row in doc.get("standings") or []
            ],
        )
        save_contest(contest, store=store)
        count += 1
        plog.info("正式赛迁移完成", contest_id=contest.id, standings=len(contest.standings))
    return count


def migrate(*, repo_root: Path | None = None) -> None:
    root = repo_root or find_repo_root()
    url = default_db_url(repo_root=root)
    create_all(url=url)
    engine, factory = make_session_factory(url=url)
    plog = Plog(name="xcpc-migrate")
    try:
        today = date.today()
        with factory() as session:
            n_players = migrate_players(session, today=today, plog=plog)
            n_teams = migrate_teams(session, today=today, plog=plog)
            n_contests = migrate_formal_contests(session, plog=plog)
        plog.info("迁移完成", players=n_players, teams=n_teams, contests=n_contests)
    finally:
        plog.close()
        engine.dispose()


def main() -> None:
    migrate()


if __name__ == "__main__":
    main()
