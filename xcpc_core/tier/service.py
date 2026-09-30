"""tier 业务逻辑：赛事等级 / 奖项基线 CRUD + 种子与兜底。

- 初始种子（迁移 0003 与 ensure_* 共用）：
  - 赛事等级 = contest_weights.yaml 的 formal_types + training_divisions（系数 = weight/100）
    + 兜底「未分级」；
  - 奖项基线 = 金(gold)100 / 银(silver)60 / 铜(bronze)30 / 优胜(honorable)20；
- 删除护栏：仍被比赛引用的等级 / 仍被认证引用的奖项不允许删除。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from xcpc_core.tier.exceptions import (
    AwardLevelInUseError,
    AwardLevelNotFoundError,
    TierInUseError,
    TierNotFoundError,
)
from xcpc_core.tier.models import (
    AWARD_LABELS,  # noqa: F401  对外再导出（display 标签与模型同源）
    FALLBACK_TIER_NAME,
    AwardLevel,
    AwardLevelCreate,
    AwardLevelUpdate,
    Tier,
    TierCreate,
    TierUpdate,
)
from xcpc_core.tier.store import TierStore

DEFAULT_AWARD_LEVELS: list[tuple[str, float, int]] = [
    ("gold", 100.0, 1),
    ("silver", 60.0, 2),
    ("bronze", 30.0, 3),
    ("honorable", 20.0, 4),
]


def load_config_weights(repo_root: Path | None = None) -> dict[str, tuple[str, float]]:
    """读 contest_weights.yaml，返回 {类型key: (中文标签, 系数)}，formal + training 合并。"""
    root = repo_root or Path.cwd()
    path = root / "data" / "config" / "contest_weights.yaml"
    entries: dict[str, tuple[str, float]] = {}
    if not path.is_file():
        return entries
    import yaml

    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    for section in ("formal_types", "training_divisions"):
        for key, entry in (data.get(section) or {}).items():
            weight = float(entry.get("weight", 100))
            entries[str(key)] = (str(entry.get("label", key)), weight / 100.0)
    return entries


def builtin_config_entries() -> dict[str, tuple[str, float]]:
    """contest_weights.yaml 不可用时（纯迁移环境）的内置兜底。"""
    return {
        "icpc_regional": ("ICPC 区域赛", 1.0),
        "ccpc_national": ("CCPC 国赛", 1.0),
        "icpc_invitational": ("ICPC 邀请赛", 0.8),
        "ccpc_invitational": ("CCPC 邀请赛", 0.8),
        "icpc_online": ("ICPC 网络赛", 0.9),
        "ccpc_online": ("CCPC 网络赛", 0.9),
        "icpc_provincial": ("ICPC 省赛", 0.7),
        "ccpc_provincial": ("CCPC 省赛", 0.7),
        "icpc_school": ("ICPC 校赛", 0.5),
        "icpc_team_school": ("ICPC 组队校赛", 0.6),
        "div1+2": ("全体队员组", 1.0),
        "div1": ("老队员组", 0.95),
        "div2": ("新队员组", 0.7),
        "div3": ("未入队新生组", 0.6),
    }


def seed_defaults(session: Session, *, repo_root: Path | None = None) -> None:
    """按 config 建初始赛事等级与奖项基线（已存在跳过）。迁移 0003 调用。"""
    store = TierStore(session)
    config = load_config_weights(repo_root) or builtin_config_entries()
    known = {tier.name for tier in store.list_tiers()}
    order = 1
    for label, coefficient in config.values():
        if label not in known:
            store.insert(TierCreate(name=label, coefficient=coefficient, sort_order=order), commit=False)
        order += 1
    if FALLBACK_TIER_NAME not in known:
        store.insert(TierCreate(name=FALLBACK_TIER_NAME, coefficient=1.0, sort_order=999), commit=False)
    for name, base_points, sort_order in DEFAULT_AWARD_LEVELS:
        if store.find_award_by_name(name) is None:
            store.insert_award_level(
                AwardLevelCreate(name=name, base_points=base_points, sort_order=sort_order), commit=False
            )
    session.commit()


class TierService:
    def __init__(self, store: TierStore) -> None:
        self.store = store

    # ---- 赛事等级 ----

    def create_tier(self, params: TierCreate) -> Tier:
        return self.store.insert(params)

    def update_tier(self, tier_id: int, params: TierUpdate) -> Tier:
        changes = params.model_dump(exclude_none=True)
        if not changes:
            return self._get_tier(tier_id)
        row = self.store.get(tier_id)
        if row is None:
            raise TierNotFoundError(f"赛事等级不存在: {tier_id}")
        return self.store.update(
            tier_id,
            name=changes.get("name", row.name),
            coefficient=changes.get("coefficient", row.coefficient),
            sort_order=changes.get("sort_order", row.sort_order),
        )

    def delete_tier(self, tier_id: int) -> None:
        if self.store.get(tier_id) is None:
            raise TierNotFoundError(f"赛事等级不存在: {tier_id}")
        if self.store.count_contests(tier_id) > 0:
            raise TierInUseError("该赛事等级仍被比赛引用，请先调整相关比赛")
        self.store.delete(tier_id)

    def _get_tier(self, tier_id: int) -> Tier:
        row = self.store.get(tier_id)
        if row is None:
            raise TierNotFoundError(f"赛事等级不存在: {tier_id}")
        return row

    def ensure_fallback(self) -> Tier:
        """「未分级」兜底等级（系数 1.0），不存在则建。"""
        tier = self.store.find_by_name(FALLBACK_TIER_NAME)
        if tier is not None:
            return tier
        return self.store.insert(TierCreate(name=FALLBACK_TIER_NAME, coefficient=1.0, sort_order=999))

    def ensure_from_config_type(self, contest_type: str, *, repo_root: Path | None = None) -> Tier:
        """把 contest_type（如 icpc_provincial）解析为赛事等级，缺失时按 config 自动建。

        正式赛导入走这里：config 仍是「类型 → 标签/权重」的权威来源，等级表缺失时
        自动补建（与迁移 0003 的种子口径一致），导入不因管理端删档而中断。
        """
        tier = self.store.find_by_name(contest_type)
        if tier is not None:
            return tier
        config = load_config_weights(repo_root) or builtin_config_entries()
        if contest_type not in config:
            raise TierNotFoundError(f"未知赛事类型: {contest_type}（config 中无对应等级）")
        label, coefficient = config[contest_type]
        existing = self.store.find_by_name(label)
        if existing is not None:
            return existing
        order = len(self.store.list_tiers()) + 1
        return self.store.insert(TierCreate(name=label, coefficient=coefficient, sort_order=order))

    # ---- 奖项基线 ----

    def create_award_level(self, params: AwardLevelCreate) -> AwardLevel:
        return self.store.insert_award_level(params)

    def update_award_level(self, level_id: int, params: AwardLevelUpdate) -> AwardLevel:
        changes = params.model_dump(exclude_none=True)
        if not changes:
            return self._get_award(level_id)
        row = self.store.get_award_level(level_id)
        if row is None:
            raise AwardLevelNotFoundError(f"奖项等级不存在: {level_id}")
        return self.store.update_award_level(
            level_id,
            name=changes.get("name", row.name),
            base_points=changes.get("base_points", row.base_points),
            sort_order=changes.get("sort_order", row.sort_order),
        )

    def delete_award_level(self, level_id: int) -> None:
        if self.store.get_award_level(level_id) is None:
            raise AwardLevelNotFoundError(f"奖项等级不存在: {level_id}")
        # award 以字符串存于 standing.award / pointsclaim.award，无外键；删除前人工把关
        self.store.delete_award_level(level_id)

    def _get_award(self, level_id: int) -> AwardLevel:
        row = self.store.get_award_level(level_id)
        if row is None:
            raise AwardLevelNotFoundError(f"奖项等级不存在: {level_id}")
        return row
