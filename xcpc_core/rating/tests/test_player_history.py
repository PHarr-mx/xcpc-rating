"""player_event_history：选手个人页的参赛记录与累计 Rating（P5 core 侧）。"""

from datetime import date

from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.service import ContestService
from xcpc_core.contest.store import ContestStore
from xcpc_core.player.models import PlayerCreate
from xcpc_core.player.service import PlayerService
from xcpc_core.player.store import PlayerStore
from xcpc_core.rating.api import player_event_history

_EXPECTED_A = 1250.0  # (10-1+1)/10*1000 + 5*50，weight=100
_EXPECTED_B = 1050.0  # (10-3+1)/10*1000 + 5*50


def _seed_player(session) -> None:
    PlayerService(PlayerStore(session)).create_player(
        PlayerCreate(name="张三", handle="zs", grade=2023)
    )


def _seed_contest(session, contest_id: str, day: date, rank: int) -> None:
    ContestService(ContestStore(session)).save_contest(ContestCreate(
        id=contest_id,
        title=f"测试赛 {contest_id}",
        date=day,
        contest_type="icpc_school",
        total_teams=10,
        standings=[Standing(team_name="一队", rank=rank, solved=5, penalty=100, player_ids=["p001"])],
    ))


def test_history_cumulative_and_ordering(db_session):
    _seed_player(db_session)
    _seed_contest(db_session, "c_b", date(2026, 4, 20), rank=3)
    _seed_contest(db_session, "c_a", date(2026, 3, 15), rank=1)

    history = player_event_history("p001", session=db_session)
    assert [r.contest_id for r in history] == ["c_a", "c_b"]  # 按日期升序
    assert history[0].contribution == _EXPECTED_A
    assert history[0].rating_after == _EXPECTED_A
    assert history[1].contribution == _EXPECTED_B
    assert history[1].rating_after == _EXPECTED_A + _EXPECTED_B

    first = history[0]
    assert first.source_type == "formal"
    assert first.contest_title == "测试赛 c_a"
    assert first.rank == 1
    assert first.solved == 5
    assert first.event_id.startswith("c_a#") and first.event_id.endswith("#p001")


def test_history_empty_for_player_without_events(db_session):
    _seed_player(db_session)
    assert player_event_history("p001", session=db_session) == []


def test_history_unknown_player(db_session):
    assert player_event_history("p999", session=db_session) == []


def test_history_weight_applied(db_session):
    _seed_player(db_session)
    ContestService(ContestStore(db_session)).save_contest(ContestCreate(
        id="c_w", title="加权赛", date=date(2026, 5, 1), contest_type="icpc_provincial",
        total_teams=10, weight=70,
        standings=[Standing(team_name="一队", rank=1, solved=5, penalty=100, player_ids=["p001"])],
    ))
    (record,) = player_event_history("p001", session=db_session)
    assert record.contribution == round(_EXPECTED_A * 70 / 100, 2)
    assert record.rating_after == record.contribution
