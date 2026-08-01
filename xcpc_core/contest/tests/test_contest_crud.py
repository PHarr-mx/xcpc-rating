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
    return ContestCreate(
        id=contest_id,
        title=kw.get("title", "测试赛"),
        date=kw.get("date", date(2026, 3, 20)),
        source_type=kw.get("source_type", "formal"),
        contest_type=kw.get("contest_type", "icpc_provincial"),
        format="team_xcpc",
        total_teams=kw.get("total_teams", 86),
        school_teams_count=kw.get("school_teams_count", 8),
        weight=kw.get("weight", 70),
        standings=kw.get("standings") or [
            Standing(team_id="t001", team_name="一队", rank=1, award="gold", solved=8, penalty=600,
                     player_ids=["p001", "p002", "p003"]),
            Standing(team_id="t002", team_name="二队", rank=2, award="silver", solved=7, penalty=700,
                     player_ids=["p004"]),
        ],
    )


def test_save_and_get(db_session):
    saved = save_contest(_make_contest())
    assert saved.id == "contest_001"
    assert saved.competition_year == 2025  # 2026-03-20 → 2025 赛年
    assert saved.season == "2026-春学期"

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


def test_list_filters_source_type(db_session):
    save_contest(_make_contest(contest_id="c1", source_type="formal"))
    save_contest(_make_contest(contest_id="c2", source_type="training", contest_type=None))
    assert len(list_contests()) == 2
    assert [c.id for c in list_contests(source_type="formal")] == ["c1"]
    assert [c.id for c in list_contests(source_type="training")] == ["c2"]


def test_delete_removes_standings(db_session):
    save_contest(_make_contest())
    delete_contest("contest_001")
    assert list_contests() == []
    with pytest.raises(ContestNotFoundError):
        get_contest("contest_001")


def test_get_not_found(db_session):
    with pytest.raises(ContestNotFoundError):
        get_contest("nope")
