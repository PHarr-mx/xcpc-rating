"""导入 DTO 前置校验：非法参数在构造/入口即报错，不等 xlsx 解析（旁路项二）。

「前置性证明」测试故意传不存在的 xlsx 路径 + 错误 contest_type：
若抛的是"未知 contest_type"而非 FileNotFoundError，即证明校验先于文件访问。
"""

import shutil
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from xcpc_core.importer import import_formal_xcpcio_xlsx, stage_formal_xlsx
from xcpc_core.importer.models import FormalImportParams, XcpcioParsedContest, XcpcioStandingRow
from xcpc_core.importer.weights import load_formal_types, load_formal_weight
from xcpc_core.player.store import find_repo_root


@pytest.fixture
def repo(tmp_path):
    """临时仓库：contest_weights.yaml 供 contest_type 查表。"""
    real_root = find_repo_root()
    (tmp_path / "data/config").mkdir(parents=True)
    for name in ("contest_weights.yaml", "school.yaml"):
        shutil.copy(real_root / f"data/config/{name}", tmp_path / f"data/config/{name}")
    return tmp_path


def _params(**overrides) -> FormalImportParams:
    base = dict(
        contest_id="v_c1",
        date=date(2026, 5, 18),
        contest_type="icpc_provincial",
        school_organizations=["西南民族大学"],
    )
    base.update(overrides)
    return FormalImportParams(**base)


def _parsed(**overrides) -> XcpcioParsedContest:
    base = dict(
        title="校验测试赛",
        total_teams=10,
        total_problems=13,
        standings_sheet="正式组",
        total_teams_sheet="所有队伍",
        standings=[
            XcpcioStandingRow(
                rank=1, organization="西南民族大学", team_name="一队",
                solved=5, penalty=100, members=["张三"],
            ),
        ],
        school_teams_total=1,
    )
    base.update(overrides)
    return XcpcioParsedContest(**base)


# ---------- FormalImportParams：纯校验（Pydantic 层） ----------


@pytest.mark.parametrize("bad_id", ["", "   ", "../evil", "a/b", "a\\b", "x..y"])
def test_params_rejects_bad_contest_id(bad_id):
    with pytest.raises(ValidationError, match="contest_id"):
        _params(contest_id=bad_id)


@pytest.mark.parametrize("bad_type", ["", "   "])
def test_params_rejects_blank_contest_type(bad_type):
    with pytest.raises(ValidationError, match="contest_type"):
        _params(contest_type=bad_type)


def test_params_allows_unknown_type_at_construction():
    """是否存在于权重表属配置校验，归入口层（见下）；构造只查纯格式。"""
    assert _params(contest_type="icpc_nonexistent").contest_type == "icpc_nonexistent"


# ---------- XcpcioParsedContest：四不变量（Pydantic 层） ----------


def test_parsed_rejects_zero_total_teams():
    with pytest.raises(ValidationError, match="无法解析 total_teams"):
        _parsed(total_teams=0)


def test_parsed_rejects_zero_total_problems():
    with pytest.raises(ValidationError, match="无法解析 total_problems"):
        _parsed(total_problems=0)


def test_parsed_rejects_no_school_teams():
    with pytest.raises(ValidationError, match="未匹配到任何本校队伍"):
        _parsed(school_teams_total=0)


def test_parsed_rejects_empty_standings():
    with pytest.raises(ValidationError, match="本校队伍均无金/银/铜奖"):
        _parsed(standings=[])


# ---------- 入口层：contest_type 对照权重表，先于文件访问 ----------


def test_load_formal_weight_lists_valid_types(repo):
    types = load_formal_types(repo_root=repo)
    assert "icpc_provincial" in types and types["icpc_provincial"]

    with pytest.raises(ValueError, match="未知 contest_type: nope.*icpc_provincial"):
        load_formal_weight("nope", repo_root=repo)


def test_import_formal_rejects_unknown_type_before_opening_file(repo, db_session):
    with pytest.raises(ValueError, match="未知 contest_type"):
        import_formal_xcpcio_xlsx(
            repo / "不存在的文件.xlsx",  # 若实现先开文件，会抛 FileNotFoundError 而非此断言目标
            _params(contest_type="icpc_nonexistent"),
            repo_root=repo,
            session=db_session,
        )


def test_stage_formal_rejects_unknown_type_before_parsing(repo, db_session):
    with pytest.raises(ValueError, match="未知 contest_type"):
        stage_formal_xlsx(
            repo / "不存在的文件.xlsx",
            _params(contest_type="icpc_nonexistent"),
            uploaded_by=1,
            repo_root=repo,
            session=db_session,
        )
