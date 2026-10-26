"""P-U3 通用比赛 JSON 导入（core 层，不依赖 Reflex）。

覆盖四组合（icpc|ioi × player|team）、姓名匹配/自动建队、打星、
raw 归档目录 `raw/contests/`、存档往返（import → 读回 → 再导入幂等）、
以及 DTO 前置校验。
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from xcpc_core.contest.api import get_contest, list_contests
from xcpc_core.db.tables import Contest, Player, Standing, Team
from xcpc_core.importer import import_contest_json
from xcpc_core.importer.contest_json import import_contest_json as _import_inner
from xcpc_core.importer.models import ContestJsonDocument
from xcpc_core.player.store import find_repo_root


@pytest.fixture
def repo(tmp_path):
    """临时仓库：config（tier 种子 + 学校）与两个 raw 目录。"""
    real_root = find_repo_root()
    (tmp_path / "data/config").mkdir(parents=True)
    for name in ("contest_weights.yaml", "school.yaml"):
        shutil.copy(real_root / f"data/config/{name}", tmp_path / f"data/config/{name}")
    return tmp_path


def _team_doc(**overrides) -> dict:
    base = {
        "contest_id": "json_t1",
        "title": "秋季训练赛一",
        "date": "2026-10-05",
        "format": "icpc",
        "entity": "team",
        "tier": "新队员组",
        "counts_for_ranking": True,
        "counts_for_points": False,
        "standings": [
            {"team_name": "甲队", "members": ["张三", "李四"], "rank": 1, "solved": 5, "penalty": 300},
            {"team_name": "乙队", "members": ["王五"], "rank": 2, "solved": 3, "penalty": 400},
        ],
    }
    base.update(overrides)
    return base


# ---- 四组合 ----


def test_team_icpc_imports_and_archives(repo, db_session):
    result = import_contest_json(_team_doc(), repo_root=repo, session=db_session)

    assert result.contest_id == "json_t1"
    assert result.standings_imported == 2
    assert result.tier_name == "新队员组"
    assert result.entity == "team"
    # 两名队员自动建档 + 两支队伍建立
    assert len(result.players_created) == 3
    assert len(result.teams_created) == 2
    assert not result.unmatched_players

    # raw 归档落在 P-U3 新目录，而非 raw/formal/
    archive = repo / "data/raw/contests/json_t1.json"
    assert archive.is_file()
    assert not (repo / "data/raw/formal/json_t1.json").exists()
    doc = json.loads(archive.read_text(encoding="utf-8"))
    assert doc["source_format"] == "contest_json"
    assert doc["entity"] == "team"
    assert doc["standings"][0]["player_ids"], "归档必须回填 player_ids 供重灌"


def test_player_icpc_imports_without_team(repo, db_session):
    doc = {
        "contest_id": "json_p1",
        "title": "个人赛",
        "date": "2026-10-06",
        "format": "icpc",
        "entity": "player",
        "tier": "新队员组",
        "standings": [
            {"members": ["张三"], "rank": 1, "solved": 6, "penalty": 200},
            {"members": ["王五"], "rank": 2, "solved": 4, "penalty": 300},
        ],
    }
    result = import_contest_json(doc, repo_root=repo, session=db_session)

    assert result.entity == "player"
    assert result.standings_imported == 2
    assert result.teams_created == [], "个人赛不应建队"

    rows = db_session.scalars(
        select(Standing).where(Standing.contest_id == "json_p1").order_by(Standing.rank)
    ).all()
    assert [row.team_id for row in rows] == [None, None]


def test_ioi_player_uses_score(repo, db_session):
    doc = {
        "contest_id": "json_ioi1",
        "title": "IOI 训练",
        "date": "2026-10-07",
        "format": "ioi",
        "entity": "player",
        "tier": "新队员组",
        "standings": [
            {"members": ["张三"], "rank": 1, "score": 300},
            {"members": ["王五"], "rank": 2, "score": 250},
        ],
    }
    result = import_contest_json(doc, repo_root=repo, session=db_session)
    assert result.format == "ioi"
    rows = db_session.scalars(
        select(Standing).where(Standing.contest_id == "json_ioi1").order_by(Standing.rank)
    ).all()
    assert [row.score for row in rows] == [300, 250]

    contest = get_contest("json_ioi1", store=None) if False else None  # 占位避免误用
    row = db_session.get(Contest, "json_ioi1")
    assert row.format == "ioi"
    assert row.entity == "player"


def test_ioi_team_is_rejected(repo, db_session):
    """ioi × team 无成绩口径（docs/03 §3.1 只定义三种组合），DTO 层就挡下。"""
    doc = {
        "contest_id": "json_bad",
        "title": "非法组合",
        "date": "2026-10-07",
        "format": "ioi",
        "entity": "team",
        "standings": [{"team_name": "甲队", "members": ["张三", "李四"], "score": 100}],
    }
    with pytest.raises(ValidationError, match="不支持 ioi × team"):
        ContestJsonDocument.model_validate(doc)


# ---- 姓名匹配与建队复用 ----


def test_reimport_same_team_reuses_team_and_aliases(repo, db_session):
    import_contest_json(_team_doc(), repo_root=repo, session=db_session)
    # 同队员、不同队名 → 同一队伍 + 新别名
    doc = _team_doc(
        contest_id="json_t2",
        date="2026-10-12",
        standings=[
            {"team_name": "甲队（改名）", "members": ["张三", "李四"], "rank": 3, "solved": 2, "penalty": 500},
        ],
    )
    result = import_contest_json(doc, repo_root=repo, session=db_session)

    assert result.teams_created == [], "同队员集合不应新建队伍"
    teams = db_session.scalars(select(Team)).all()
    assert len(teams) == 2  # 甲队、乙队
    from xcpc_core.db.tables import TeamAlias

    aliases = {row.alias for row in db_session.scalars(select(TeamAlias)).all()}
    assert "甲队（改名）" in aliases


def test_existing_player_not_duplicated(repo, db_session):
    import_contest_json(_team_doc(), repo_root=repo, session=db_session)
    before = len(db_session.scalars(select(Player)).all())
    import_contest_json(
        _team_doc(contest_id="json_t3", date="2026-10-13"),
        repo_root=repo,
        session=db_session,
    )
    after = len(db_session.scalars(select(Player)).all())
    assert after == before, "姓名已存在时不应重复建档"


def test_auto_create_disabled_reports_unmatched(repo, db_session):
    doc = _team_doc(
        contest_id="json_unmatched",
        standings=[{"team_name": "陌生队", "members": ["不存在的人"], "rank": 1, "solved": 1, "penalty": 100}],
    )
    with pytest.raises(ValueError, match="没有任何成绩行可导入"):
        import_contest_json(doc, auto_create_players=False, repo_root=repo, session=db_session)


# ---- 开关与 tier ----


def test_tier_by_contest_type_key(repo, db_session):
    doc = _team_doc(contest_id="json_ct", tier=None, contest_type="div1+2")
    result = import_contest_json(doc, repo_root=repo, session=db_session)
    assert result.tier_name == "全体队员组"


def test_unknown_tier_raises(repo, db_session):
    doc = _team_doc(contest_id="json_notier", tier="不存在的等级")
    with pytest.raises(ValueError, match="赛事等级不存在"):
        import_contest_json(doc, repo_root=repo, session=db_session)


def test_flags_persisted(repo, db_session):
    doc = _team_doc(
        contest_id="json_flags",
        counts_for_points=True,
        max_value=5,
        allow_claims=True,
    )
    import_contest_json(doc, repo_root=repo, session=db_session)
    row = db_session.get(Contest, "json_flags")
    assert row.counts_for_points is True
    assert row.counts_for_ranking is True
    assert row.max_value == 5
    assert row.allow_claims is True
    assert row.source_file == "raw/contests/json_flags.json"


def test_award_only_forces_no_ranking(repo, db_session):
    doc = _team_doc(
        contest_id="json_award",
        scoring="award_only",
        counts_for_points=True,
        counts_for_ranking=True,
        standings=[
            {"team_name": "甲队", "members": ["张三", "李四"], "award": "gold"},
        ],
    )
    import_contest_json(doc, repo_root=repo, session=db_session)
    row = db_session.get(Contest, "json_award")
    assert row.scoring == "award_only"
    assert row.counts_for_ranking is False, "award_only 强制不计排名"


# ---- 归档往返 ----


def test_import_from_file_path(repo, db_session):
    template = repo / "template.json"
    template.write_text(json.dumps(_team_doc(contest_id="json_from_file"), ensure_ascii=False), encoding="utf-8")

    result = import_contest_json(template, repo_root=repo, session=db_session)
    assert result.contest_id == "json_from_file"
    assert (repo / "data/raw/contests/json_from_file.json").is_file()


def test_reimport_from_archive_is_idempotent(repo, db_session):
    import_contest_json(_team_doc(), repo_root=repo, session=db_session)
    archive = repo / "data/raw/contests/json_t1.json"

    # 用归档原样再导一次（归档含 player_ids，但 DTO 只取原始字段）
    raw = json.loads(archive.read_text(encoding="utf-8"))
    raw["standings"] = [
        {"team_name": row["team_name"], "members": row["member_names"], "rank": row["rank"],
         "solved": row["solved"], "penalty": row["penalty"]}
        for row in raw["standings"]
    ]
    before_teams = len(db_session.scalars(select(Team)).all())
    before_players = len(db_session.scalars(select(Player)).all())

    import_contest_json(raw, repo_root=repo, session=db_session)

    assert len(db_session.scalars(select(Team)).all()) == before_teams
    assert len(db_session.scalars(select(Player)).all()) == before_players
    rows = db_session.scalars(select(Standing).where(Standing.contest_id == "json_t1")).all()
    assert len(rows) == 2, "重复导入应整批替换而非累加"


# ---- DTO 前置校验 ----


def test_entity_player_requires_single_member(repo):
    with pytest.raises(ValidationError, match="恰好 1 人"):
        ContestJsonDocument.model_validate({
            "contest_id": "json_bad2", "title": "t", "date": "2026-10-01",
            "entity": "player",
            "standings": [{"members": ["张三", "李四"], "rank": 1, "solved": 1}],
        })


def test_team_rejects_more_than_three_members(repo):
    with pytest.raises(ValidationError, match="最多 3 人"):
        ContestJsonDocument.model_validate({
            "contest_id": "json_bad3", "title": "t", "date": "2026-10-01",
            "entity": "team",
            "standings": [{"team_name": "x", "members": ["a", "b", "c", "d"], "rank": 1, "solved": 1}],
        })


def test_contest_id_path_traversal_rejected(repo):
    with pytest.raises(ValidationError, match="非法字符"):
        ContestJsonDocument.model_validate({
            "contest_id": "../evil", "title": "t", "date": "2026-10-01",
            "standings": [{"team_name": "x", "members": ["a"], "rank": 1, "solved": 1}],
        })


def test_tier_and_contest_type_mutually_exclusive(repo):
    with pytest.raises(ValidationError, match="只能二选一"):
        ContestJsonDocument.model_validate({
            "contest_id": "json_bad4", "title": "t", "date": "2026-10-01",
            "tier": "新队员组", "contest_type": "div1+2",
            "standings": [{"team_name": "x", "members": ["a"], "rank": 1, "solved": 1}],
        })


def test_ranking_needs_rank(repo):
    with pytest.raises(ValidationError, match="至少有一行提供 rank"):
        ContestJsonDocument.model_validate({
            "contest_id": "json_bad5", "title": "t", "date": "2026-10-01",
            "counts_for_ranking": True,
            "standings": [{"team_name": "x", "members": ["a"], "solved": 1}],
        })


def test_points_formula_derives_max_value(repo):
    doc = ContestJsonDocument.model_validate(_team_doc(
        contest_id="json_derive", counts_for_points=True, max_value=None,
    ))
    assert doc.max_value == 5, "应按全场最高解题数推导 max_value"

# ---- 姓名歧义的人工决议 ----


def _ambiguous_doc(**overrides):
    base = _team_doc(
        contest_id="json_amb",
        tier="新队员组",
        standings=[{"team_name": "甲队", "members": ["重名者"], "rank": 1, "solved": 3}],
    )
    base.update(overrides)
    return base


@pytest.fixture
def two_same_name(db_session):
    from xcpc_core.db.tables import Player as PlayerRow

    db_session.add_all([
        PlayerRow(id="pA", name="重名者", grade=2024, status="active"),
        PlayerRow(id="pB", name="重名者", grade=2025, status="active"),
    ])
    db_session.commit()
    return db_session


def test_ambiguity_without_decision_skips_row(repo, two_same_name):
    with pytest.raises(ValueError, match="没有任何成绩行可导入"):
        import_contest_json(_ambiguous_doc(), repo_root=repo, session=two_same_name)


def test_decision_by_player_id_resolves(repo, two_same_name):
    result = import_contest_json(
        _ambiguous_doc(), decisions={"重名者": {"player_id": "pB"}},
        repo_root=repo, session=two_same_name,
    )
    assert result.standings_imported == 1
    assert not result.unmatched_players

    from xcpc_core.db.tables import StandingMember

    ids = two_same_name.scalars(select(StandingMember.player_id)).all()
    assert list(ids) == ["pB"], "决议指定的选手必须被采用"


def test_decision_new_forces_creation(repo, two_same_name):
    before = len(two_same_name.scalars(select(Player)).all())
    result = import_contest_json(
        _ambiguous_doc(), decisions={"重名者": {"action": "new", "grade": 2026}},
        repo_root=repo, session=two_same_name,
    )
    after = len(two_same_name.scalars(select(Player)).all())
    assert after == before + 1, "action=new 应强制新建，不猜已有重名者"
    assert result.standings_imported == 1
    assert result.players_created


def test_decision_new_without_grade_uses_default(repo, two_same_name):
    """grade 缺省时应回落到 default_grade，不能 int(None) 崩。"""
    result = import_contest_json(
        _ambiguous_doc(), decisions={"重名者": {"action": "new"}},
        default_grade=2023, repo_root=repo, session=two_same_name,
    )
    assert result.standings_imported == 1
    created_id = result.players_created[0].player_id
    player = two_same_name.get(Player, created_id)
    assert player.grade == 2023


def test_invalid_decision_falls_back_to_normal_matching(repo, db_session):
    """决议格式不对（无 player_id 也无 action）→ 回退常规匹配，而非整行失败。"""
    from xcpc_core.db.tables import Player as PlayerRow

    db_session.add(PlayerRow(id="pX", name="唯一者", grade=2024, status="active"))
    db_session.commit()
    doc = _team_doc(
        contest_id="json_baddeg", tier="新队员组",
        standings=[{"team_name": "甲队", "members": ["唯一者"], "rank": 1, "solved": 2}],
    )
    result = import_contest_json(
        doc, decisions={"唯一者": {"garbage": True}}, repo_root=repo, session=db_session
    )
    assert result.standings_imported == 1
    assert not result.unmatched_players
