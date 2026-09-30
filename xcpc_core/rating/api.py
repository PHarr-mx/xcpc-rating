"""Rating 对外接口：从 DB 生成事件 → AtCoder 式重放引擎计算（P-U2 起）。

榜单与选手历史共用一套重放语义：
- 生涯 = 全史重放；赛年/赛季 = 窗口内以全 Center 重放（docs/04 §2.1 定案）
- ``rating_after`` 为 AtCoder 式 Rating（首场 = perf − 1200 起步，负分照实显示）；
  ``rating_delta`` 为该场 Rating 变化（首场相对 0 起点计）
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from xcpc_core.db.session import make_session_factory
from xcpc_core.db.tables import Contest as ContestRow
from xcpc_core.rating.engine import RatingEngine  # noqa: F401  旧逐事件路径保留（OJ 未来用）
from xcpc_core.rating.events import build_events_from_contests
from xcpc_core.rating.models import PeriodFilter, PlayerEventRecord, PlayerScore, RatingResult, ReplayEventScore
from xcpc_core.rating.replay import AtcoderReplayEngine

_factory: sessionmaker | None = None
_default_session: Session | None = None


def _get_default_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory


def configure_session(session: Session | None) -> None:
    """为当前进程设置默认数据源会话（测试注入用；DI 模式镜像 importer/audit）。"""
    global _default_session
    _default_session = session


def compute_rating(
    *,
    mode: str = "all",
    period: PeriodFilter | None = None,
    session: Session | None = None,
) -> RatingResult:
    """计算一个 mode × period 的榜单结果（AtCoder 式重放）。

    period 缺省为生涯（全史重放）；赛年/赛季为窗口内全 Center 重放。
    rating 取该选手重放序列最后一场的 rating_after。
    """
    close = False
    if session is None:
        session = _get_default_factory()()
        close = True
    try:
        events = build_events_from_contests(session)
    finally:
        if close:
            session.close()
    period = period or PeriodFilter()
    series = AtcoderReplayEngine().compute_series(events, period=period)
    scores = [
        PlayerScore(
            player_id=player_id,
            rating=round(values[-1].rating_after, 2),
            event_count=len(values),
        )
        for player_id, values in series.items()
    ]
    scores.sort(key=lambda row: (-row.rating, row.player_id))
    return RatingResult(mode=mode, period=period, scores=scores)


def player_event_history(
    player_id: str,
    *,
    mode: str = "all",
    session: Session | None = None,
) -> list[PlayerEventRecord]:
    """按选手聚合全部事件的参赛记录与逐场 Rating（个人页用）。

    语义与榜单重放一致（同一套 AtcoderReplayEngine）：记录按 (date, contest_id)
    升序；``rating_delta`` 为该场 Rating 变化（首场相对 0 起点）；
    ``rating_after`` 为累计到该场后的 AtCoder 式 Rating。无事件的选手返回空列表。
    """
    owns = False
    resolved = session or _default_session
    if resolved is None:
        resolved = _get_default_factory()()
        owns = True
    try:
        events = build_events_from_contests(resolved)
        if not events:
            return []
        series = AtcoderReplayEngine().compute_series(events)
        player_series: list[ReplayEventScore] = series.get(player_id, [])
        if not player_series:
            return []

        # 场次分组与重放排序保持一致：按 (min date, contest_id) 升序
        by_contest: dict[str, list] = defaultdict(list)
        for event in events:
            by_contest[event.event_id.split("#", 1)[0]].append(event)
        ordered_contests = sorted(
            by_contest, key=lambda cid: (min(e.date for e in by_contest[cid]), cid)
        )
        my_contests = [
            cid for cid in ordered_contests
            if any(e.player_id == player_id for e in by_contest[cid])
        ]
        if len(my_contests) != len(player_series):
            # 打星（参与方程不入历史）的场次不会出现在 series 里，这里只防对齐错位
            raise ValueError("重放序列与参赛场次数量不一致，事件流可能被并发修改")

        titles: dict[str, str] = {}
        for row in resolved.scalars(select(ContestRow).where(ContestRow.id.in_(my_contests))):
            titles[row.id] = row.title
    finally:
        if owns:
            resolved.close()

    records: list[PlayerEventRecord] = []
    prev_rating = 0.0
    for contest_id, score in zip(my_contests, player_series):
        event = next(e for e in by_contest[contest_id] if e.player_id == player_id)
        payload = event.payload
        # contest_id 约定为 event_id 前缀（{contest_id}#{standing_id}#{player_id}），
        # 与 contest.store.delete_contest 的派生事件清理约定一致
        records.append(PlayerEventRecord(
            event_id=event.event_id,
            contest_id=contest_id,
            contest_title=titles.get(contest_id),
            date=event.date,
            source_type=event.source_type,
            contest_type=event.contest_type,
            contest_format=event.contest_format,
            team_id=event.team_id,
            rank=payload.get("rank"),
            solved=payload.get("solved"),
            penalty=payload.get("penalty"),
            score=payload.get("score"),
            award=payload.get("award"),
            rating_delta=round(score.rating_after - prev_rating, 2),
            rating_after=round(score.rating_after, 2),
        ))
        prev_rating = score.rating_after
    return records
