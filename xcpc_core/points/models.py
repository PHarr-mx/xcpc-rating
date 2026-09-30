"""points DTO（改挂统一 contest，CONTEST_UNIFICATION_PLAN §2.5/§2.6）。"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

EventEntity = Literal["player", "team"]
ClaimStatus = Literal["staged", "approved", "rejected"]


class PointsClaimCreate(BaseModel):
    """提交认证：formula 场次填 value+rank；award_only 场次填 award（service 按 scoring 校验）。"""

    contest_id: str = Field(min_length=1)
    value: int | None = Field(default=None, ge=1)  # 解题数/得分，formula 场次必填
    rank: int | None = Field(default=None, ge=1)
    award: str | None = None  # award_only 场次必填（须在 awardlevel 内）
    team_id: str | None = None  # 队伍赛必填（提交者须为该队成员）
    note: str | None = None

    @model_validator(mode="after")
    def _check_claim_shape(self) -> "PointsClaimCreate":
        has_result = self.value is not None or self.rank is not None
        if has_result and self.award is not None:
            raise ValueError("value/rank 与 award 不能同时填写")
        if self.value is not None and self.rank is None:
            raise ValueError("填写解题数/得分时必须同时填写名次")
        if self.rank is not None and self.value is None:
            raise ValueError("填写名次时必须同时填写解题数/得分")
        return self


class PointsClaimView(BaseModel):
    id: int
    contest_id: str
    contest_title: str | None = None
    scoring: str | None = None
    entity: EventEntity
    player_id: str | None = None
    player_name: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    value: int | None = None
    rank: int | None = None
    award: str | None = None
    note: str | None = None
    status: ClaimStatus
    submitted_by: int
    decided_by: int | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None


class IndividualPointsRow(BaseModel):
    """个人积分榜行：个人流水直加（不含队伍复合分）。"""

    rank: int
    player_id: str
    name: str
    points: float
    entry_count: int


class TeamPointsRow(BaseModel):
    """队伍积分榜行：复合分 = w_team×团队积分 + w_member×Σ(成员个人积分−本队所得)。"""

    rank: int
    team_id: str
    name: str
    team_points: float
    member_points: float
    composite: float
    members: list[str] = Field(default_factory=list)
