"""points 对外唯一读写入口（facade）。Web 与其他子模块都从这里导入。

DI 注入模式与 importer.api 一致：``configure_session(session)`` 供测试/内嵌
场景注入会话；未注入时各函数走默认工厂并自行管理生命周期。
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from sqlalchemy.orm import Session

from xcpc_core.points import service
from xcpc_core.points.models import (
    IndividualPointsRow,
    PointsClaimCreate,
    PointsClaimView,
    PointsEventCreate,
    PointsEventUpdate,
    PointsEventView,
    TeamPointsRow,
)

_default_session: Session | None = None


def configure_session(session: Session | None) -> None:
    global _default_session
    _default_session = session


def _session(session: Session | None) -> Session | None:
    return session or _default_session


def create_event(*, params: PointsEventCreate, created_by: int, session: Session | None = None) -> PointsEventView:
    return service.create_event(_session(session), params=params, created_by=created_by)


def update_event(*, event_id: int, params: PointsEventUpdate, session: Session | None = None) -> PointsEventView:
    return service.update_event(_session(session), event_id=event_id, params=params)


def get_event(event_id: int, *, session: Session | None = None) -> PointsEventView:
    return service.get_event(_session(session), event_id)


def list_events(*, session: Session | None = None) -> list[PointsEventView]:
    return service.list_events(_session(session))


def submit_claim(
    *,
    params: PointsClaimCreate,
    submitted_by: int,
    submitter_player_id: str,
    session: Session | None = None,
) -> PointsClaimView:
    return service.submit_claim(
        _session(session), params=params, submitted_by=submitted_by, submitter_player_id=submitter_player_id
    )


def list_claims(
    *,
    event_id: int | None = None,
    status: Literal["staged", "approved", "rejected"] | None = None,
    session: Session | None = None,
) -> list[PointsClaimView]:
    return service.list_claims(_session(session), event_id=event_id, status=status)


def my_claims(*, player_id: str, session: Session | None = None) -> list[PointsClaimView]:
    return service.my_claims(_session(session), player_id=player_id)


def player_teams(*, player_id: str, session: Session | None = None) -> list[dict]:
    return service.player_teams(_session(session), player_id=player_id)


def review_claim(
    *,
    claim_id: int,
    decision: Literal["approved", "rejected"],
    decided_by: int,
    session: Session | None = None,
) -> PointsClaimView:
    return service.review_claim(_session(session), claim_id=claim_id, decision=decision, decided_by=decided_by)


def individual_leaderboard(
    *, start: date | None = None, end: date | None = None, session: Session | None = None
) -> list[IndividualPointsRow]:
    return service.individual_leaderboard(_session(session), start=start, end=end)


def team_leaderboard(
    *,
    w_team: float = service.DEFAULT_W_TEAM,
    w_member: float = service.DEFAULT_W_MEMBER,
    start: date | None = None,
    end: date | None = None,
    session: Session | None = None,
) -> list[TeamPointsRow]:
    return service.team_leaderboard(_session(session), w_team=w_team, w_member=w_member, start=start, end=end)
