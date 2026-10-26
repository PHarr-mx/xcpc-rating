"""把 data/raw 现有数据灌入 SQLite（幂等，可反复重跑）。

用法：
    uv run python -m xcpc_core.db.migrate

- schema 由 alembic 管（``db.migrations.run_migrations``）：全新库建表升级到
  head，alembic 引入前的存量库自动 stamp，已升级的库为 no-op
- 读 data/raw/players/roster.json、teams/roster.json、formal/*.json
- 按主键 upsert：已存在的选手/队伍更新，比赛则删旧成绩后重写
- 现有 ID（p001/t001）原样保留；created_at 缺失填迁移当日
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from xcpc_core.contest.api import save_contest
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.migrations import run_migrations
from xcpc_core.db.session import default_db_url, find_repo_root, make_session_factory
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


def migrate_players(session, *, today: date, plog: Plog, repo_root: Path) -> int:
    store = PlayerStore(session)
    raw_items = _load_json(repo_root / "data/raw/players/roster.json")
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


def migrate_teams(session, *, today: date, plog: Plog, repo_root: Path) -> int:
    store = TeamStore(session)
    raw_items = _load_json(repo_root / "data/raw/teams/roster.json")
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


def migrate_formal_contests(session, *, plog: Plog, repo_root: Path) -> int:
    """重灌两个 raw 归档目录：``raw/formal/``（正式赛 xlsx）与 ``raw/contests/``（P-U3 通用 JSON）。"""
    from xcpc_core.importer.formal_store import iter_raw_contest_files

    files = iter_raw_contest_files(repo_root)
    store = ContestStore(session)
    # raw 文档 → 统一比赛 DTO 的映射与正式赛导入共用一套（含 tier 解析）
    from xcpc_core.importer.contest_json import _contest_create_from_document as _json_to_contest
    from xcpc_core.importer.formal import _contest_create_from_document as _formal_to_contest
    from xcpc_core.tier.api import ensure_fallback_tier, find_tier_by_name

    count = 0
    for path in files:
        with path.open(encoding="utf-8") as file:
            doc = json.load(file)
        # source_file 写成相对仓库根的 posix 路径，与导入写入时一致
        source_rel = path.relative_to(repo_root).as_posix()
        if doc.get("source_format") == "contest_json":
            tier = find_tier_by_name(doc.get("tier", ""), session=session) or ensure_fallback_tier(
                session=session
            )
            contest = _json_to_contest(doc, source_file=source_rel, tier_id=tier.id, session=session)
        else:
            contest = _formal_to_contest(doc, source_file=source_rel, session=session)
        save_contest(contest, store=store)
        count += 1
        plog.info("比赛迁移完成", contest_id=contest.id, standings=len(contest.standings), source=source_rel)
    return count


def migrate(*, repo_root: Path | None = None) -> None:
    root = repo_root or find_repo_root()
    url = default_db_url(repo_root=root)
    run_migrations(url=url)
    engine, factory = make_session_factory(url=url)
    plog = Plog(name="xcpc-migrate")
    try:
        today = date.today()
        with factory() as session:
            n_players = migrate_players(session, today=today, plog=plog, repo_root=root)
            n_teams = migrate_teams(session, today=today, plog=plog, repo_root=root)
            n_contests = migrate_formal_contests(session, plog=plog, repo_root=root)
        plog.info("迁移完成", players=n_players, teams=n_teams, contests=n_contests)
    finally:
        plog.close()
        engine.dispose()


def main() -> None:
    migrate()


if __name__ == "__main__":
    main()
