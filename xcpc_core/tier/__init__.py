"""tier 模块：赛事等级与奖项基线（CONTEST_UNIFICATION_PLAN §2.1/§2.2）。

赛事等级决定积分系数与排名权重；奖项基线分 × 等级系数 = 奖项分。
对外入口见 ``api``（DI 注入模式与 points/audit 一致）。
"""

from xcpc_core.tier.api import (
    configure_session,
    create_award_level,
    create_tier,
    delete_award_level,
    delete_tier,
    ensure_fallback_tier,
    ensure_tier_for_contest_type,
    find_award_level_by_name,
    find_tier_by_name,
    get_tier,
    list_award_levels,
    list_tiers,
    update_award_level,
    update_tier,
)
from xcpc_core.tier.exceptions import (
    AwardLevelInUseError,
    AwardLevelNotFoundError,
    DuplicateAwardLevelError,
    DuplicateTierError,
    TierError,
    TierInUseError,
    TierNotFoundError,
)
from xcpc_core.tier.models import (
    AWARD_LABELS,
    FALLBACK_TIER_NAME,
    AwardLevel,
    AwardLevelCreate,
    AwardLevelUpdate,
    Tier,
    TierCreate,
    TierUpdate,
)
from xcpc_core.tier.service import TierService, seed_defaults
from xcpc_core.tier.store import TierStore

__all__ = [
    "AWARD_LABELS",
    "AwardLevel",
    "AwardLevelCreate",
    "AwardLevelInUseError",
    "AwardLevelNotFoundError",
    "AwardLevelUpdate",
    "DuplicateAwardLevelError",
    "DuplicateTierError",
    "FALLBACK_TIER_NAME",
    "Tier",
    "TierCreate",
    "TierError",
    "TierInUseError",
    "TierNotFoundError",
    "TierService",
    "TierStore",
    "TierUpdate",
    "configure_session",
    "create_award_level",
    "create_tier",
    "delete_award_level",
    "delete_tier",
    "ensure_fallback_tier",
    "ensure_tier_for_contest_type",
    "find_award_level_by_name",
    "find_tier_by_name",
    "get_tier",
    "list_award_levels",
    "list_tiers",
    "seed_defaults",
    "update_award_level",
    "update_tier",
]
