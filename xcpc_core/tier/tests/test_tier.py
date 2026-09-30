"""tier 模块测试：等级/奖项 CRUD、种子、兜底与删除护栏。"""

from __future__ import annotations

import pytest

from xcpc_core.contest import api as contest_api
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore
from xcpc_core.tier import api as tier_api
from xcpc_core.tier.exceptions import (
    AwardLevelNotFoundError,
    DuplicateTierError,
    TierInUseError,
    TierNotFoundError,
)
from xcpc_core.tier.models import (
    FALLBACK_TIER_NAME,
    AwardLevelCreate,
    AwardLevelUpdate,
    TierCreate,
    TierUpdate,
)
from xcpc_core.tier.service import builtin_config_entries, seed_defaults


def test_create_and_list_tiers(db_session):
    tier = tier_api.create_tier(TierCreate(name="ICPC 省赛", coefficient=0.7), session=db_session)
    tier_api.create_tier(TierCreate(name="周训练", coefficient=1.0, sort_order=5), session=db_session)
    tiers = tier_api.list_tiers(session=db_session)
    assert [t.name for t in tiers] == ["ICPC 省赛", "周训练"]  # sort_order 升序
    assert tiers[0].coefficient == 0.7
    assert tier_api.get_tier(tier.id, session=db_session).name == "ICPC 省赛"


def test_duplicate_tier_name_rejected(db_session):
    tier_api.create_tier(TierCreate(name="校赛", coefficient=0.5), session=db_session)
    with pytest.raises(DuplicateTierError):
        tier_api.create_tier(TierCreate(name="校赛", coefficient=0.6), session=db_session)


def test_update_tier_partial(db_session):
    tier = tier_api.create_tier(TierCreate(name="邀请赛", coefficient=0.8, sort_order=3), session=db_session)
    updated = tier_api.update_tier(tier.id, TierUpdate(coefficient=0.85), session=db_session)
    assert updated.coefficient == 0.85 and updated.name == "邀请赛" and updated.sort_order == 3
    with pytest.raises(TierNotFoundError):
        tier_api.update_tier(999, TierUpdate(coefficient=1.0), session=db_session)


def test_delete_tier_guarded_by_usage(db_session):
    tier = tier_api.create_tier(TierCreate(name="在用等级", coefficient=1.0), session=db_session)
    contest_api.configure_store(ContestStore(db_session))
    contest_api.save_contest(ContestCreate(
        id="c1", title="测试赛", date=__import__("datetime").date(2026, 5, 1),
        tier_id=tier.id,
        standings=[Standing(team_name="一队", rank=1, solved=5, player_ids=["p001"])],
    ))
    with pytest.raises(TierInUseError):
        tier_api.delete_tier(tier.id, session=db_session)

    contest_api.delete_contest("c1")
    tier_api.delete_tier(tier.id, session=db_session)
    assert tier_api.list_tiers(session=db_session) == []
    with pytest.raises(TierNotFoundError):
        tier_api.delete_tier(999, session=db_session)


def test_award_level_crud(db_session):
    level = tier_api.create_award_level(AwardLevelCreate(name="gold", base_points=100), session=db_session)
    tier_api.create_award_level(AwardLevelCreate(name="silver", base_points=60), session=db_session)
    assert [a.name for a in tier_api.list_award_levels(session=db_session)] == ["gold", "silver"]
    assert tier_api.find_award_level_by_name("gold", session=db_session).base_points == 100
    updated = tier_api.update_award_level(
        level.id, AwardLevelUpdate(base_points=120.0), session=db_session
    )
    assert updated.base_points == 120.0
    tier_api.delete_award_level(level.id, session=db_session)
    with pytest.raises(AwardLevelNotFoundError):
        tier_api.update_award_level(level.id, AwardLevelUpdate(base_points=1.0), session=db_session)


def test_seed_defaults_from_config(db_session):
    """config 缺失时用内置兜底：正式赛/训练赛标签 + 未分级 + 奖项基线。"""
    seed_defaults(db_session, repo_root=None)  # repo_root=None → cwd 下找不到 config → 内置兜底
    names = {t.name for t in tier_api.list_tiers(session=db_session)}
    assert "ICPC 省赛" in names and FALLBACK_TIER_NAME in names
    awards = {a.name: a.base_points for a in tier_api.list_award_levels(session=db_session)}
    assert awards == {"gold": 100.0, "silver": 60.0, "bronze": 30.0, "honorable": 20.0}
    # 幂等
    seed_defaults(db_session, repo_root=None)
    assert len(tier_api.list_tiers(session=db_session)) == len(names)


def test_builtin_config_entries_covers_legacy_types():
    config = builtin_config_entries()
    assert config["icpc_provincial"] == ("ICPC 省赛", 0.7)
    assert config["div2"] == ("新队员组", 0.7)


def test_ensure_tier_for_contest_type(db_session):
    """contest_type → 等级：config 标签匹配既有等级则复用，缺失则自动建。"""
    tier = tier_api.ensure_tier_for_contest_type("icpc_provincial", session=db_session)
    assert tier.name == "ICPC 省赛" and tier.coefficient == 0.7
    # 幂等：同名复用
    again = tier_api.ensure_tier_for_contest_type("icpc_provincial", session=db_session)
    assert again.id == tier.id
    with pytest.raises(TierNotFoundError, match="未知赛事类型"):
        tier_api.ensure_tier_for_contest_type("nope_type", session=db_session)


def test_ensure_fallback_tier(db_session):
    tier = tier_api.ensure_fallback_tier(session=db_session)
    assert tier.name == FALLBACK_TIER_NAME and tier.coefficient == 1.0
    assert tier_api.ensure_fallback_tier(session=db_session).id == tier.id
