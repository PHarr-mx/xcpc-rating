"""db.migrate：临时仓库端到端灌数据 + 幂等重跑（盲区补齐）。

覆盖 repo_root 传参修复：子函数此前硬编码 find_repo_root()，
migrate(repo_root=…) 会被无视而静默读真实仓库数据。
"""

import json
from datetime import date

import pytest
from sqlalchemy import select

from xcpc_core.db import tables
from xcpc_core.db.migrate import migrate
from xcpc_core.db.session import default_db_url, make_session_factory


@pytest.fixture
def repo(tmp_path):
    """最小 raw 仓库：2 选手 / 1 队伍 / 1 场正式赛 + 空的 config 目录。"""
    raw = tmp_path / "data/raw"
    (raw / "players").mkdir(parents=True)
    (raw / "teams").mkdir(parents=True)
    (raw / "formal").mkdir(parents=True)
    (tmp_path / "data/config").mkdir(parents=True)

    (raw / "players/roster.json").write_text(json.dumps([
        {"id": "p001", "name": "张三", "grade": 2023, "status": "active", "oj_accounts": []},
        {"id": "p002", "name": "李四", "grade": 2023, "status": "active", "oj_accounts": []},
    ], ensure_ascii=False), encoding="utf-8")
    (raw / "teams/roster.json").write_text(json.dumps([
        {"id": "t001", "members": ["p001", "p002"], "member_key": "p001|p002",
         "size": 2, "aliases": ["一队"]},
    ], ensure_ascii=False), encoding="utf-8")
    (raw / "formal/c1.json").write_text(json.dumps({
        "contest_id": "c1", "title": "测试赛", "date": "2026-05-18",
        "contest_type": "icpc_school", "format": "team_xcpc",
        "total_teams": 10, "school_teams_count": 1, "rated": True,
        "weight": 100, "weight_source": "config",
        "standings": [
            {"team_id": "t001", "team_name": "一队", "rank": 1,
             "solved": 5, "penalty": 100, "player_ids": ["p001", "p002"]},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def _counts(repo):
    engine, factory = make_session_factory(url=default_db_url(repo_root=repo))
    try:
        with factory() as session:
            return {
                "players": len(session.scalars(select(tables.Player)).all()),
                "teams": len(session.scalars(select(tables.Team)).all()),
                "contests": len(session.scalars(select(tables.Contest)).all()),
                "standings": len(session.scalars(select(tables.Standing)).all()),
                "members": len(session.scalars(select(tables.StandingMember)).all()),
            }
    finally:
        engine.dispose()


def test_migrate_seeds_from_repo_root(repo):
    assert (repo / "data/raw/players/roster.json").is_file()  # 数据在临时仓库，非真实仓库
    migrate(repo_root=repo)

    assert _counts(repo) == {"players": 2, "teams": 1, "contests": 1, "standings": 1, "members": 2}

    engine, factory = make_session_factory(url=default_db_url(repo_root=repo))
    try:
        with factory() as session:
            player = session.get(tables.Player, "p001")
            assert player.name == "张三" and player.grade == 2023
            contest = session.get(tables.Contest, "c1")
            assert contest.total_teams == 10
            assert contest.competition_year == 2025 and contest.season == "2026-春学期"
    finally:
        engine.dispose()


def test_migrate_is_idempotent(repo):
    migrate(repo_root=repo)
    first = _counts(repo)
    migrate(repo_root=repo)  # 重跑：upsert，不重复不报错
    assert _counts(repo) == first


def test_migrate_missing_raw_dirs_is_noop(tmp_path):
    (tmp_path / "data/raw").mkdir(parents=True)
    migrate(repo_root=tmp_path)  # 无 roster / formal → 不报错，零写入
    assert _counts(tmp_path) == {"players": 0, "teams": 0, "contests": 0, "standings": 0, "members": 0}
