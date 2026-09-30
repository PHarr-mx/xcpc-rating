"""统一比赛 DTO（CONTEST_UNIFICATION_PLAN §2.3）。

赛制（icpc|ioi）× 参与形式（player|team）× 赛事等级（tier_id）三维决定一场比赛；
双开关 counts_for_points / counts_for_ranking 决定进积分流水 / Rating 重放。
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ContestFormat = Literal["icpc", "ioi"]
ContestEntity = Literal["player", "team"]
ContestScoring = Literal["formula", "award_only"]


class Standing(BaseModel):
    """一场比赛中的成绩行（DTO）。contest_id 由 store 落库时统一写入，不在 DTO 中。

    award_only 场次允许只有 award、无 solved/rank 的行（rank 可空）。
    """

    team_id: str | None = None
    team_name: str | None = None
    rank: int | None = None
    school_rank: int | None = None
    award: str | None = None  # gold|silver|bronze|…
    solved: int | None = None  # icpc
    penalty: int | None = None  # icpc
    score: int | None = None  # ioi
    manually_added: bool = False
    player_ids: list[str] = Field(default_factory=list)


class ContestBase(BaseModel):
    title: str = Field(min_length=1)
    date: date
    format: ContestFormat = "icpc"
    entity: ContestEntity = "team"
    tier_id: int | None = None  # 缺省时 service 落到「未分级」兜底等级
    n_teams: int | None = None  # 参赛实体数（队数/人数）
    school_teams_count: int | None = None
    max_value: int | None = None  # 全场最高解题数/得分（formula 场次的公式参数）
    scoring: ContestScoring = "formula"
    counts_for_points: bool = False
    counts_for_ranking: bool = True
    allow_claims: bool = True
    source_file: str | None = None  # 追溯到 raw/

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title 不能为空")
        return value

    @model_validator(mode="after")
    def _check_scoring_flags(self) -> "ContestBase":
        if self.scoring == "award_only":
            # 未公开完整排名的比赛：强制只能记积分，不能记排名（方案 §2.3 约束）
            self.counts_for_ranking = False
        if self.counts_for_points:
            if self.scoring == "formula":
                if self.max_value is None or self.max_value < 1:
                    raise ValueError("记积分的 formula 场次必须提供 max_value ≥ 1")
            else:  # award_only：max_value 无意义
                self.max_value = None
        return self


class ContestCreate(ContestBase):
    """新建/保存比赛参数。competition_year/season 由 date 推导，不入参。"""

    id: str = Field(min_length=1)
    standings: list[Standing] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_safe(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("id 不能为空")
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError("id 不能包含路径分隔符或 ..")
        return value.strip()


class Contest(ContestBase):
    id: str
    competition_year: int
    season: str


class ContestDetail(BaseModel):
    contest: Contest
    standings: list[Standing]
