"""points DTO。"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ScoringKind = Literal["solved", "score"]
EventEntity = Literal["player", "team"]
ClaimStatus = Literal["staged", "approved", "rejected"]


class PointsEventCreate(BaseModel):
    title: str
    date: _date
    entity: EventEntity  # 认证主体：个人赛按选手 / 队伍赛按队
    kind: ScoringKind = "solved"  # value 语义：解题数 / 得分
    max_value: int = Field(ge=1)  # 全场最高解题数/得分
    n_teams: int = Field(ge=1)  # 参赛实体数（队数/人数）

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("title 不能为空")
        return value


class PointsEventUpdate(BaseModel):
    """可更新字段（全 None 表示无变更）。已记积分不溯及，变更只影响后续审核。"""

    title: str | None = None
    date: _date | None = None
    max_value: int | None = Field(default=None, ge=1)
    n_teams: int | None = Field(default=None, ge=1)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("title 不能为空")
        return value


class PointsEventView(BaseModel):
    id: int
    title: str
    date: _date
    entity: EventEntity
    kind: ScoringKind
    max_value: int
    n_teams: int
    created_at: datetime | None = None
    claims_staged: int = 0
    claims_total: int = 0


class PointsClaimCreate(BaseModel):
    event_id: int
    value: int = Field(ge=1)  # 资格线：解题数/得分 ≥ 1
    rank: int = Field(ge=1)
    team_id: str | None = None  # 队伍赛必填（提交者须为该队成员）
    note: str | None = None

    @model_validator(mode="after")
    def _check_value_vs_rank(self) -> "PointsClaimCreate":
        if self.value <= 0:  # 防御：Field 已挡，双保险
            raise ValueError("value 必须 ≥ 1")
        return self


class PointsClaimView(BaseModel):
    id: int
    event_id: int
    event_title: str | None = None
    entity: EventEntity
    player_id: str | None = None
    player_name: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    value: int
    rank: int
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
    """队伍积分榜行：复合分 = w_team×团队积分 + w_member×Σ(成员队外个人积分)。"""

    rank: int
    team_id: str
    name: str
    team_points: float
    member_points: float
    composite: float
    members: list[str] = Field(default_factory=list)
