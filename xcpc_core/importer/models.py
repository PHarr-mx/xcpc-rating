from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SourceFormat = Literal["xcpcio_xlsx"]


class AwardThresholds(BaseModel):
    gold: tuple[int, int] | None = None
    silver: tuple[int, int] | None = None
    bronze: tuple[int, int] | None = None
    source: Literal["formal_medals", "percentile"]


class XcpcioStandingRow(BaseModel):
    rank: int
    school_rank: int | None = None
    organization: str
    team_name: str
    solved: int
    penalty: int
    award: str | None = None
    members: list[str] = Field(min_length=1, max_length=3)
    unofficial: bool = False


class XcpcioParsedContest(BaseModel):
    """xlsx 解析结果 DTO。四个不变量由本模型保证，任何构造路径均不可绕过。"""

    source_format: SourceFormat = "xcpcio_xlsx"
    title: str
    total_teams: int
    total_problems: int
    standings_sheet: str
    total_teams_sheet: str
    standings: list[XcpcioStandingRow]
    school_teams_total: int
    award_thresholds: AwardThresholds | None = None

    @model_validator(mode="after")
    def _check_invariants(self) -> "XcpcioParsedContest":
        if self.total_teams <= 0:
            raise ValueError("无法解析 total_teams")
        if self.total_problems <= 0:
            raise ValueError("无法解析 total_problems")
        if self.school_teams_total <= 0:
            raise ValueError("未匹配到任何本校队伍，请检查 school_organizations 或工作表名称")
        if not self.standings:
            raise ValueError("本校队伍均无金/银/铜奖，未写入任何成绩")
        return self


class FormalImportParams(BaseModel):
    contest_id: str
    date: date
    contest_type: str
    format: Literal["team_xcpc"] = "team_xcpc"
    school_organizations: list[str] = Field(min_length=1)
    standings_sheet: str = "正式组"
    total_teams_sheet: str = "所有队伍"
    include_unofficial: bool = True
    auto_create_players: bool = True
    default_grade: int | None = None
    weight_override: int | None = None
    weight_override_reason: str | None = None

    @field_validator("contest_id")
    @classmethod
    def _contest_id_safe(cls, value: str) -> str:
        """contest_id 直接拼进 data/raw/formal/{id}.json，禁止空白与路径穿越。"""
        if not value or not value.strip():
            raise ValueError("contest_id 不能为空")
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"contest_id 含非法字符（/ \\ ..）: {value}")
        return value

    @field_validator("contest_type")
    @classmethod
    def _contest_type_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("contest_type 不能为空")
        return value


class UnmatchedPlayer(BaseModel):
    contest_id: str
    name: str
    team_name: str
    rank: int
    candidates: list[dict[str, str]] = Field(default_factory=list)


class UnmatchedTeam(BaseModel):
    contest_id: str
    team_name: str
    members: list[str]
    rank: int
    reason: str


class StagedStanding(BaseModel):
    """解析阶段的一行成绩；player_ids 只包含自动唯一匹配的选手。"""

    row: XcpcioStandingRow
    player_ids: list[str] = Field(default_factory=list)
    unresolved_names: list[str] = Field(default_factory=list)


class StagedImportPayload(BaseModel):
    """ImportBatch.payload_json 的稳定 DTO。"""

    version: int = 1
    params: FormalImportParams
    parsed: XcpcioParsedContest
    contest_meta: dict[str, Any] = Field(default_factory=dict)
    standings: list[StagedStanding] = Field(default_factory=list)
    unmatched_players: list[UnmatchedPlayer] = Field(default_factory=list)
    unmatched_teams: list[UnmatchedTeam] = Field(default_factory=list)


class ImportBatchSummary(BaseModel):
    batch_id: int
    filename: str
    status: str
    contest_id: str
    title: str
    total_teams: int
    school_teams_count: int
    award_thresholds: AwardThresholds | None = None
    standings_count: int
    unmatched_players: list[UnmatchedPlayer] = Field(default_factory=list)
    unmatched_teams: list[UnmatchedTeam] = Field(default_factory=list)


class ImportBatchDetail(BaseModel):
    batch_id: int
    uploaded_by: int
    filename: str
    status: str
    created_at: Any | None = None
    payload: StagedImportPayload


class CreatedPlayer(BaseModel):
    player_id: str
    name: str
    team_name: str
    contest_id: str


class FormalImportResult(BaseModel):
    contest_id: str
    title: str
    total_teams: int
    school_teams_count: int
    standings_imported: int
    players_created: list[CreatedPlayer] = Field(default_factory=list)
    unmatched_players: list[UnmatchedPlayer]
    unmatched_teams: list[UnmatchedTeam]
    raw_path: str
    source_file: str

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AddFormalTeamParams(BaseModel):
    contest_id: str
    team_name: str
    member_names: list[str] = Field(min_length=1, max_length=3)
    rank: int = Field(ge=1)
    solved: int = Field(ge=0)
    penalty: int = Field(ge=0)
    award: Literal["gold", "silver", "bronze"] | None = None
    school_rank: int | None = Field(default=None, ge=1)
    unofficial: bool = True
    auto_create_players: bool = True
    default_grade: int | None = None
    note: str | None = None


class AddFormalTeamResult(BaseModel):
    contest_id: str
    team_id: str
    award: str
    replaced: bool
    players_created: list[CreatedPlayer] = Field(default_factory=list)
    unmatched_players: list[UnmatchedPlayer] = Field(default_factory=list)
    raw_path: str
    source_file: str

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
