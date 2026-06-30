from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from importer import AddFormalTeamParams, add_formal_team, import_formal_xcpcio_xlsx
from importer.formal_store import raw_contest_basename, raw_contest_rel_path, raw_contest_path
from importer.models import FormalImportParams
from player.store import find_repo_root

SMU = ["西南民族大学"]


@pytest.fixture
def sample_xlsx() -> Path:
    path = find_repo_root() / "第十八届四川省大学生程序设计竞赛 - 正式赛.xlsx"
    if not path.is_file():
        pytest.skip("样例 xlsx 不在仓库根目录")
    return path


@pytest.fixture
def import_repo(tmp_path, sample_xlsx) -> Path:
    shutil.copytree(find_repo_root() / "data" / "config", tmp_path / "data" / "config")
    (tmp_path / "data" / "raw" / "formal").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "players").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "players" / "roster.json").write_text("[]\n", encoding="utf-8")

    import_formal_xcpcio_xlsx(
        sample_xlsx,
        FormalImportParams(
            contest_id="2026_sichuan_provincial",
            date=date(2026, 5, 18),
            contest_type="icpc_provincial",
            school_organizations=SMU,
        ),
        repo_root=tmp_path,
    )
    return tmp_path


def test_add_formal_team_rejects_non_awarded_score(import_repo):
    with pytest.raises(ValueError, match="未达到金/银/铜奖线"):
        add_formal_team(
            AddFormalTeamParams(
                contest_id="2026_sichuan_provincial",
                team_name="左脑攻击右脑，暴力代替思考",
                member_names=["李汶航", "陈子川", "滕召宇"],
                rank=212,
                solved=2,
                penalty=238,
                unofficial=True,
            ),
            repo_root=import_repo,
        )


def test_add_formal_team_manual_unaffiliated_star(import_repo):
    before = json.loads(raw_contest_path(import_repo, "2026_sichuan_provincial").read_text(encoding="utf-8"))
    assert len(before["standings"]) == 7

    result = add_formal_team(
        AddFormalTeamParams(
            contest_id="2026_sichuan_provincial",
            team_name="左脑攻击右脑，暴力代替思考",
            member_names=["李汶航", "陈子川", "滕召宇"],
            rank=212,
            solved=2,
            penalty=122,
            unofficial=True,
            note="打星队，Organization 未挂靠本校",
        ),
        repo_root=import_repo,
    )

    assert result.replaced is False
    assert result.award == "bronze"
    assert len(result.players_created) == 3

    after = json.loads(raw_contest_path(import_repo, "2026_sichuan_provincial").read_text(encoding="utf-8"))
    assert len(after["standings"]) == 8
    assert after["school_teams_awarded"] == 8
    assert after["school_teams_manual"] == 1
    added = next(row for row in after["standings"] if row["team_name"] == "左脑攻击右脑，暴力代替思考")
    assert added["manually_added"] is True
    assert added["player_ids"]


def test_add_formal_team_replaces_same_roster(import_repo):
    params = AddFormalTeamParams(
        contest_id="2026_sichuan_provincial",
        team_name="左脑攻击右脑，暴力代替思考",
        member_names=["李汶航", "陈子川", "滕召宇"],
        rank=212,
        solved=2,
        penalty=122,
        unofficial=True,
    )
    add_formal_team(params, repo_root=import_repo)
    result = add_formal_team(
        params.model_copy(update={"rank": 210, "note": "更新排名"}),
        repo_root=import_repo,
    )

    assert result.replaced is True
    after = json.loads(raw_contest_path(import_repo, "2026_sichuan_provincial").read_text(encoding="utf-8"))
    assert len(after["standings"]) == 8
    entry = next(row for row in after["standings"] if row["team_name"] == params.team_name)
    assert entry["rank"] == 210
    assert entry["note"] == "更新排名"


def test_raw_contest_path_strips_formal_prefix():
    assert raw_contest_basename("formal_2026_sichuan_provincial") == "2026_sichuan_provincial"
    assert raw_contest_basename("2026_sichuan_provincial") == "2026_sichuan_provincial"
    assert raw_contest_rel_path("formal_2026_sichuan_provincial") == "raw/formal/2026_sichuan_provincial.json"
