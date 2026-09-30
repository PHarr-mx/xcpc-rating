from __future__ import annotations

from datetime import date

import pytest

from xcpc_core.contest import api as contest_api
from xcpc_core.contest.api import delete_contest, get_contest, list_contests, save_contest
from xcpc_core.contest.exceptions import ContestNotFoundError
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore


@pytest.fixture(autouse=True)
def _use_test_store(db_session):
    """把 api 默认 store 指向测试内存库，避免落到 data/db/xcpc.db。"""
    contest_api.configure_store(ContestStore(db_session))
    yield
    contest_api.configure_store(None)


def _make_contest(*, contest_id: str = "contest_001", **kw) -> ContestCreate:
    params = dict(
        id=contest_id,
        title=kw.get("title", "测试赛"),
        date=kw.get("date", date(2026, 3, 20)),
        format=kw.get("format", "icpc"),
        entity=kw.get("entity", "team"),
        tier_id=kw.get("tier_id"),
        n_teams=kw.get("n_teams", 86),
        school_teams_count=kw.get("school_teams_count", 8),
        max_value=kw.get("max_value"),
        scoring=kw.get("scoring", "formula"),
        counts_for_points=kw.get("counts_for_points", False),
        counts_for_ranking=kw.get("counts_for_ranking", True),
        allow_claims=kw.get("allow_claims", True),
        standings=kw.get("standings") or [
            Standing(team_id="t001", team_name="一队", rank=1, award="gold", solved=8, penalty=600,
                     player_ids=["p001", "p002", "p003"]),
            Standing(team_id="t002", team_name="二队", rank=2, award="silver", solved=7, penalty=700,
                     player_ids=["p004"]),
        ],
    )
    return ContestCreate(**params)


def test_save_and_get(db_session):
    saved = save_contest(_make_contest())
    assert saved.id == "contest_001"
    assert saved.competition_year == 2025  # 2026-03-20 → 2025 赛年
    assert saved.season == "2026-春学期"
    # 未指定 tier → 兜底「未分级」；默认 formula 且进排名、不记积分
    assert saved.tier_id is not None
    assert saved.scoring == "formula"
    assert saved.counts_for_ranking is True
    assert saved.counts_for_points is False

    detail = get_contest("contest_001")
    assert detail.contest.title == "测试赛"
    assert len(detail.standings) == 2
    assert detail.standings[0].rank == 1
    assert detail.standings[0].player_ids == ["p001", "p002", "p003"]


def test_save_replaces_standings_on_reimport(db_session):
    save_contest(_make_contest())
    # 重导入：同一 contest_id，成绩只剩一支队伍 → 应整批替换
    save_contest(_make_contest(standings=[
        Standing(team_id="t001", team_name="一队", rank=1, award="gold", solved=8, penalty=600,
                 player_ids=["p001"]),
    ]))
    detail = get_contest("contest_001")
    assert len(detail.standings) == 1
    assert detail.standings[0].player_ids == ["p001"]


def test_list_filters_tier(db_session):
    from xcpc_core.tier import api as tier_api
    from xcpc_core.tier.models import TierCreate

    tier = tier_api.create_tier(TierCreate(name="测试等级", coefficient=1.0), session=db_session)
    save_contest(_make_contest(contest_id="c1", tier_id=tier.id))
    save_contest(_make_contest(contest_id="c2"))
    assert len(list_contests()) == 2
    assert [c.id for c in list_contests(tier_id=tier.id)] == ["c1"]


def test_delete_removes_standings(db_session):
    save_contest(_make_contest())
    delete_contest("contest_001")
    assert list_contests() == []
    with pytest.raises(ContestNotFoundError):
        get_contest("contest_001")


def test_get_not_found(db_session):
    with pytest.raises(ContestNotFoundError):
        get_contest("nope")


def test_award_only_forces_ranking_off(db_session):
    """未公开完整排名的比赛：只能记积分，强制不进排名。"""
    saved = save_contest(_make_contest(
        contest_id="c_award",
        scoring="award_only",
        counts_for_points=True,
        counts_for_ranking=True,  # 传入 True 也被强制压回 False
        max_value=None,
        standings=[Standing(team_id="t001", team_name="一队", rank=None, award="gold",
                            player_ids=["p001", "p002", "p003"])],
    ))
    assert saved.scoring == "award_only"
    assert saved.counts_for_ranking is False
    assert saved.max_value is None
    detail = get_contest("c_award")
    assert detail.standings[0].rank is None  # award_only 行可无名次


def test_points_capable_formula_requires_max_value(db_session):
    """记积分的 formula 场次必须提供 max_value ≥ 1。"""
    with pytest.raises(ValueError, match="max_value"):
        save_contest(_make_contest(contest_id="c_novalue", counts_for_points=True))
    with pytest.raises(ValueError, match="max_value"):
        save_contest(_make_contest(contest_id="c_zero", counts_for_points=True, max_value=0))
    with pytest.raises(ValueError, match="id"):
        save_contest(_make_contest(contest_id="../evil"))


def test_ranking_requires_formula(db_session):
    """counts_for_ranking=True 只能配 formula（award_only 已被强制排除）。"""
    saved = save_contest(_make_contest(contest_id="c_ok", scoring="formula", counts_for_ranking=True))
    assert saved.counts_for_ranking is True
