from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["formal", "training", "oj_contest", "oj_practice"]
PeriodType = Literal["career", "competition_year", "season"]
BoardMode = Literal["formal_only", "all"]


class RatingEvent(BaseModel):
    """统一事件模型（docs/03 §6）：异构记录归一化后的 Rating 输入。"""

    event_id: str
    source_type: SourceType
    date: date
    competition_year: int
    season: str
    contest_type: str | None = None
    contest_format: str | None = None  # team_xcpc|solo_xcpc|oi
    player_id: str
    team_id: str | None = None
    payload: dict = Field(default_factory=dict)  # rank/solved/penalty/score/delta/total_teams...
    weight: int = 100  # 基准 100


class PeriodFilter(BaseModel):
    """时间维度：生涯 / 赛年 / 赛季（docs/07 §3）。"""

    type: PeriodType = "career"
    id: str | int | None = None  # None for career
    start: date | None = None
    end: date | None = None


class EventScore(BaseModel):
    """单次事件对某选手的得分贡献（占位公式下即该事件得分，已含权重）。"""

    date: date
    score: float


class PlayerScore(BaseModel):
    player_id: str
    rating: float
    event_count: int


class RatingResult(BaseModel):
    """一个 mode × period 组合下的榜单聚合结果。"""

    mode: BoardMode = "all"
    period: PeriodFilter
    scores: list[PlayerScore]  # 按 rating 降序，同分按 player_id


class PlayerEventRecord(BaseModel):
    """选手个人页的参赛记录：一次事件 + 逐场累计 Rating（现公式下为得分累加）。"""

    event_id: str
    contest_id: str
    contest_title: str | None = None
    date: date
    source_type: SourceType
    contest_type: str | None = None
    contest_format: str | None = None
    team_id: str | None = None
    rank: int | None = None
    solved: int | None = None
    penalty: int | None = None
    score: int | None = None  # oi 用的题目分值，与 contribution（rating 贡献）区分
    award: str | None = None
    contribution: float  # 本场对 rating 的贡献（已含权重）
    rating_after: float  # 按日期升序累计到本场后的 rating
