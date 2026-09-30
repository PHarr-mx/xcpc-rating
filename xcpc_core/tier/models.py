"""tier 模块 DTO：赛事等级（积分/排名系数）与奖项基线分。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

FALLBACK_TIER_NAME = "未分级"
AWARD_LABELS = {"gold": "金奖", "silver": "银奖", "bronze": "铜奖", "honorable": "优胜奖"}


class TierBase(BaseModel):
    name: str = Field(min_length=1)
    coefficient: float = Field(gt=0)  # 积分/排名系数
    sort_order: int = 0

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name 不能为空")
        return value.strip()


class TierCreate(TierBase):
    pass


class TierUpdate(BaseModel):
    """可更新字段（全 None 表示无变更）。"""

    name: str | None = None
    coefficient: float | None = Field(default=None, gt=0)
    sort_order: int | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name 不能为空")
        return value.strip() if value is not None else None


class Tier(TierBase):
    id: int


class AwardLevelBase(BaseModel):
    name: str = Field(min_length=1)  # gold|silver|bronze|honorable…
    base_points: float = Field(ge=0)  # 基线分，奖项分 = base_points × tier.coefficient
    sort_order: int = 0

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name 不能为空")
        return value.strip()


class AwardLevelCreate(AwardLevelBase):
    pass


class AwardLevelUpdate(BaseModel):
    name: str | None = None
    base_points: float | None = Field(default=None, ge=0)
    sort_order: int | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name 不能为空")
        return value.strip() if value is not None else None


class AwardLevelUpdate(BaseModel):
    """可更新字段（全 None 表示无变更）。"""

    name: str | None = None
    base_points: float | None = Field(default=None, ge=0)
    sort_order: int | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name 不能为空")
        return value.strip() if value is not None else None


class AwardLevel(AwardLevelBase):
    id: int
