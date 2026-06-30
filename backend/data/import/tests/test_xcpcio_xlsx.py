from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from importer.config import load_school_organizations
from importer.formal import import_formal_xcpcio_xlsx
from importer.models import FormalImportParams
from importer.xcpcio_xlsx import _count_problem_columns, parse_xcpcio_xlsx
from player.store import find_repo_root

UESTC = ["电子科技大学"]


@pytest.fixture
def sample_xlsx() -> Path:
    path = find_repo_root() / "第十八届四川省大学生程序设计竞赛 - 正式赛.xlsx"
    if not path.is_file():
        pytest.skip("样例 xlsx 不在仓库根目录")
    return path


@pytest.fixture
def import_repo(tmp_path) -> Path:
    root = find_repo_root()
    shutil.copytree(root / "data" / "config", tmp_path / "data" / "config")
    (tmp_path / "data" / "raw" / "formal").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "players").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "players" / "roster.json").write_text("[]\n", encoding="utf-8")
    return tmp_path



def test_count_problem_columns():
    headers = ("Rank", "Team", "Solved", "Penalty", "A", "B", "C", "Dirt", "Member1")
    assert _count_problem_columns(headers) == 3


def test_parse_xcpcio_xlsx(sample_xlsx):
    parsed = parse_xcpcio_xlsx(
        sample_xlsx,
        school_organizations=UESTC,
        standings_sheet="正式组",
        total_teams_sheet="所有队伍",
    )
    assert parsed.source_format == "xcpcio_xlsx"
    assert "四川省大学生程序设计竞赛" in parsed.title
    assert parsed.total_teams == 312
    assert parsed.total_problems == 12
    assert parsed.school_teams_total == 6
    assert len(parsed.standings) == 6
    assert parsed.standings[0].team_name == "UESTC_忒修斯之船"
    assert parsed.standings[0].award == "gold"
    assert parsed.standings[0].rank == 1
    assert parsed.standings[0].members == ["梁育诚", "刘杭鑫", "吕书武"]
    assert sum(1 for row in parsed.standings if row.unofficial) == 1
    assert parsed.award_thresholds is not None
    assert parsed.award_thresholds.source == "formal_medals"


def test_parse_xcpcio_xlsx_without_unofficial(sample_xlsx):
    parsed = parse_xcpcio_xlsx(
        sample_xlsx,
        school_organizations=UESTC,
        include_unofficial=False,
    )
    assert len(parsed.standings) == 5
    assert parsed.school_teams_total == 5
    assert all(not row.unofficial for row in parsed.standings)


def test_import_auto_creates_players(sample_xlsx, import_repo):
    params = FormalImportParams(
        contest_id="2026_sichuan_provincial",
        date=date(2026, 5, 18),
        contest_type="icpc_provincial",
        school_organizations=UESTC,
    )

    result = import_formal_xcpcio_xlsx(
        sample_xlsx,
        params,
        repo_root=import_repo,
        write_raw=True,
    )

    assert result.school_teams_count == 6
    assert result.standings_imported == 6
    assert len(result.players_created) == 18
    assert result.unmatched_teams == []

    roster = json.loads((import_repo / "data/raw/players/roster.json").read_text(encoding="utf-8"))
    assert len(roster) == 18
    assert roster[0]["name"] in {"梁育诚", "刘杭鑫", "吕书武", "张诗杨", "幸子豪"}

    raw = json.loads((import_repo / "data/raw/formal/2026_sichuan_provincial.json").read_text(encoding="utf-8"))
    assert len(raw["standings"]) == 6
    assert raw["standings"][0]["player_ids"]
    assert sum(1 for row in raw["standings"] if row.get("unofficial")) == 1
    assert (import_repo / "data/raw/formal/2026_sichuan_provincial.json").is_file()


def test_import_without_auto_create(sample_xlsx, import_repo):
    params = FormalImportParams(
        contest_id="2026_sichuan_provincial",
        date=date(2026, 5, 18),
        contest_type="icpc_provincial",
        school_organizations=UESTC,
        auto_create_players=False,
    )

    result = import_formal_xcpcio_xlsx(
        sample_xlsx,
        params,
        repo_root=import_repo,
        write_raw=True,
    )

    assert result.standings_imported == 0
    assert len(result.unmatched_teams) == 6
    assert result.players_created == []
    assert json.loads((import_repo / "data/raw/players/roster.json").read_text(encoding="utf-8")) == []
