"""player_event_history：选手个人页的参赛记录与累计 Rating（P5 core 侧）。"""

from datetime import date

from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.service import ContestService
from xcpc_core.contest.store import ContestStore
from xcpc_core.player.models import PlayerCreate
from xcpc_core.player.service import PlayerService
from xcpc_core.player.store import PlayerStore
from xcpc_core.rating.api import player_event_history

# (n_recorded − internal_rank + 1)/n_recorded × 800 + solved×30，weight=100（兜底等级系数 1.0）
_EXPECTED_RANK1 = 950.0  # 2 队 rank1：(2-1+1)/2*800 + 5*30
_EXPECTED_RANK2 = 550.0  # 2 队 rank2：(2-2+1)/2*800 + 5*30


def _seed_players(session) -> None:
    service = PlayerService(PlayerStore(session))
    service.create_player(PlayerCreate(name="张三", handle="zs", grade=2023))
    service.create_player(PlayerCreate(name="李四", handle="ls", grade=2023))


def _seed_contest(session, contest_id: str, day: date, rank: int) -> None:
    """两支队伍保证过「入库实体 ≥ 2」护栏；p001 的名次由 rank 指定。"""
    other_rank = 2 if rank == 1 else 1
    ContestService(ContestStore(session)).save_contest(ContestCreate(
        id=contest_id,
        title=f"测试赛 {contest_id}",
        date=day,
        standings=[
            Standing(team_name="一队", rank=rank, solved=5, penalty=100, player_ids=["p001"]),
            Standing(team_name="二队", rank=other_rank, solved=4, penalty=200, player_ids=["p002"]),
        ],
    ))


def test_history_cumulative_and_ordering(db_session):
    _seed_players(db_session)
    _seed_contest(db_session, "c_b", date(2026, 4, 20), rank=2)
    _seed_contest(db_session, "c_a", date(2026, 3, 15), rank=1)

    history = player_event_history("p001", session=db_session)
    assert [r.contest_id for r in history] == ["c_a", "c_b"]  # 按日期升序
    assert history[0].contribution == _EXPECTED_RANK1
    assert history[0].rating_after == _EXPECTED_RANK1
    assert history[1].contribution == _EXPECTED_RANK2
    assert history[1].rating_after == _EXPECTED_RANK1 + _EXPECTED_RANK2

    first = history[0]
    assert first.source_type == "contest"
    assert first.contest_title == "测试赛 c_a"
    assert first.rank == 1  # 原始名次
    assert first.solved == 5
    assert first.event_id.startswith("c_a#") and first.event_id.endswith("#p001")


def test_history_empty_for_player_without_events(db_session):
    _seed_players(db_session)
    assert player_event_history("p001", session=db_session) == []


def test_history_unknown_player(db_session):
    assert player_event_history("p999", session=db_session) == []


def test_history_weight_applied(db_session):
    from xcpc_core.tier import api as tier_api
    from xcpc_core.tier.models import TierCreate

    _seed_players(db_session)
    tier = tier_api.create_tier(TierCreate(name="测试等级", coefficient=0.7), session=db_session)
    ContestService(ContestStore(db_session)).save_contest(ContestCreate(
        id="c_w", title="加权赛", date=date(2026, 5, 1), tier_id=tier.id,
        standings=[
            Standing(team_name="一队", rank=1, solved=5, penalty=100, player_ids=["p001"]),
            Standing(team_name="二队", rank=2, solved=4, penalty=200, player_ids=["p002"]),
        ],
    ))
    (record,) = player_event_history("p001", session=db_session)
    assert record.contribution == round(_EXPECTED_RANK1 * 70 / 100, 2)
    assert record.rating_after == record.contribution
