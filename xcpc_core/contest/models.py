from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["formal", "training"]
ContestFormat = Literal["team_xcpc", "solo_xcpc", "oi"]


class Standing(BaseModel):
    """一场比赛中的成绩行（DTO）。contest_id 由 store 落库时统一写入，不在 DTO 中。"""

    team_id: str | None = None
    team_name: str | None = None
    rank: int
    school_rank: int | None = None
    award: str | None = None  # gold|silver|bronze|null
    solved: int | None = None  # xcpc
    penalty: int | None = None  # xcpc
    score: int | None = None  # oi
    manually_added: bool = False
    player_ids: list[str] = Field(default_factory=list)


class ContestBase(BaseModel):
    source_type: SourceType = "formal"
    title: str = Field(min_length=1)
    date: date
    contest_type: str | None = None  # formal 用，决定权重
    format: ContestFormat = "team_xcpc"
    division: str | None = None  # training 用，决定权重
    total_teams: int | None = None  # formal 必填
    school_teams_count: int | None = None
    rated: bool = True
    weight: int = 100  # 基准 100
    weight_source: str = "config"  # config|override
    source_file: str | None = None  # 追溯到 raw/


class ContestCreate(ContestBase):
    """新建/保存比赛参数。competition_year/season 由 date 推导，不入参。"""

    id: str = Field(min_length=1)
    standings: list[Standing] = Field(default_factory=list)


class Contest(ContestBase):
    id: str
    competition_year: int
    season: str


class ContestDetail(BaseModel):
    contest: Contest
    standings: list[Standing]
