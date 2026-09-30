"""tier 对外唯一读写入口（facade）。Web 与其他子模块都从这里导入。

DI 注入模式与 points api 一致：``configure_session(session)`` 供测试/内嵌
场景注入会话；未注入时各函数走默认工厂并自行管理生命周期。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from xcpc_core.db.session import make_session_factory
from xcpc_core.tier import service
from xcpc_core.tier.models import (
    AwardLevel,
    AwardLevelCreate,
    AwardLevelUpdate,
    Tier,
    TierCreate,
    TierUpdate,
)
from xcpc_core.tier.service import TierService
from xcpc_core.tier.store import TierStore

_factory: sessionmaker | None = None
_default_session: Session | None = None


def configure_session(session: Session | None) -> None:
    global _default_session
    _default_session = session


def _get_default_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory()[1]
    return _factory


def _open_service(*, session: Session | None = None) -> tuple[TierService, Session | None]:
    resolved = session or _default_session
    if resolved is not None:
        return TierService(TierStore(resolved)), None
    owned = _get_default_factory()()
    return TierService(TierStore(owned)), owned


# ---- 赛事等级 ----


def list_tiers(*, session: Session | None = None) -> list[Tier]:
    svc, owned = _open_service(session=session)
    try:
        return svc.store.list_tiers()
    finally:
        if owned:
            owned.close()


def get_tier(tier_id: int, *, session: Session | None = None) -> Tier:
    svc, owned = _open_service(session=session)
    try:
        return svc._get_tier(tier_id)
    finally:
        if owned:
            owned.close()


def create_tier(params: TierCreate, *, session: Session | None = None) -> Tier:
    svc, owned = _open_service(session=session)
    try:
        return svc.create_tier(params)
    finally:
        if owned:
            owned.close()


def update_tier(tier_id: int, params: TierUpdate, *, session: Session | None = None) -> Tier:
    svc, owned = _open_service(session=session)
    try:
        return svc.update_tier(tier_id, params)
    finally:
        if owned:
            owned.close()


def delete_tier(tier_id: int, *, session: Session | None = None) -> None:
    svc, owned = _open_service(session=session)
    try:
        svc.delete_tier(tier_id)
    finally:
        if owned:
            owned.close()


def find_tier_by_name(name: str, *, session: Session | None = None) -> Tier | None:
    svc, owned = _open_service(session=session)
    try:
        return svc.store.find_by_name(name)
    finally:
        if owned:
            owned.close()


def ensure_fallback_tier(*, session: Session | None = None) -> Tier:
    svc, owned = _open_service(session=session)
    try:
        return svc.ensure_fallback()
    finally:
        if owned:
            owned.close()


def ensure_tier_for_contest_type(
    contest_type: str, *, repo_root: Path | None = None, session: Session | None = None
) -> Tier:
    """contest_type → 赛事等级（缺失时按 config 自动建）。正式赛导入入口用。"""
    svc, owned = _open_service(session=session)
    try:
        return svc.ensure_from_config_type(contest_type, repo_root=repo_root)
    finally:
        if owned:
            owned.close()


# ---- 奖项基线 ----


def list_award_levels(*, session: Session | None = None) -> list[AwardLevel]:
    svc, owned = _open_service(session=session)
    try:
        return svc.store.list_award_levels()
    finally:
        if owned:
            owned.close()


def find_award_level_by_name(name: str, *, session: Session | None = None) -> AwardLevel | None:
    svc, owned = _open_service(session=session)
    try:
        return svc.store.find_award_by_name(name)
    finally:
        if owned:
            owned.close()


def create_award_level(params: AwardLevelCreate, *, session: Session | None = None) -> AwardLevel:
    svc, owned = _open_service(session=session)
    try:
        return svc.create_award_level(params)
    finally:
        if owned:
            owned.close()


def update_award_level(level_id: int, params: AwardLevelUpdate, *, session: Session | None = None) -> AwardLevel:
    svc, owned = _open_service(session=session)
    try:
        return svc.update_award_level(level_id, params)
    finally:
        if owned:
            owned.close()


def delete_award_level(level_id: int, *, session: Session | None = None) -> None:
    svc, owned = _open_service(session=session)
    try:
        svc.delete_award_level(level_id)
    finally:
        if owned:
            owned.close()
