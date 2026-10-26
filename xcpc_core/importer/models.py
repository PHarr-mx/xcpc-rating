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


# ---- P-U3 通用比赛 JSON 导入 ----


class ContestJsonStandingRow(BaseModel):
    """通用 JSON 模板的一行成绩。

    entity=team 时 members 为 1–3 名队员；entity=player 时恰好 1 人。
    ``unofficial=True`` 表示打星（参与 Rating 方程但不入任何历史）。
    """

    team_name: str | None = None
    members: list[str] = Field(default_factory=list)
    rank: int | None = Field(default=None, ge=1)
    school_rank: int | None = Field(default=None, ge=1)
    award: str | None = None
    solved: int | None = Field(default=None, ge=0)
    penalty: int | None = Field(default=None, ge=0)
    score: int | None = Field(default=None, ge=0)
    unofficial: bool = False

    @model_validator(mode="after")
    def _members_present(self) -> "ContestJsonStandingRow":
        if not self.members:
            raise ValueError("members 不能为空（个人赛填一人）")
        return self


class ContestJsonDocument(BaseModel):
    """通用比赛 JSON 模板（`data/raw/contests/{contest_id}.json`）。

    与正式赛 raw 归档的差别：本模板**面向人工填写**，只有原始信息（姓名、名次、
    成绩），玩家 ID / 队伍 ID 由导入时的姓名匹配与建队推导后补入归档。
    """

    contest_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    date: date
    format: Literal["icpc", "ioi"] = "icpc"
    entity: Literal["player", "team"] = "team"
    tier: str | None = None  # 赛事等级名（如「全体队员组」）；缺省落到「未分级」
    contest_type: str | None = None  # 备选：config 中的类型 key（如 div1+2），解析为 tier
    n_teams: int | None = Field(default=None, ge=1)
    max_value: int | None = Field(default=None, ge=1)
    scoring: Literal["formula", "award_only"] = "formula"
    counts_for_points: bool = False
    counts_for_ranking: bool = True
    allow_claims: bool = True
    standings: list[ContestJsonStandingRow] = Field(min_length=1)

    @field_validator("contest_id")
    @classmethod
    def _contest_id_safe(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("contest_id 不能为空")
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"contest_id 含非法字符（/ \\ ..）: {value}")
        return value.strip()

    @model_validator(mode="after")
    def _check_shape(self) -> "ContestJsonDocument":
        # docs/03 §3.1：只有 icpc×team、icpc×player、ioi×player 三种组合有定义
        if self.format == "ioi" and self.entity == "team":
            raise ValueError("不支持 ioi × team 组合（IOI 赛制为个人，请改用 format=icpc 或 entity=player）")

        # 形式与行形状必须自洽：个人赛每行恰好 1 人，团队赛 1–3 人
        for index, row in enumerate(self.standings, start=1):
            if self.entity == "player" and len(row.members) != 1:
                raise ValueError(
                    f"第 {index} 行：entity=player 时 members 必须恰好 1 人，实际 {len(row.members)} 人"
                )
            if self.entity == "team" and len(row.members) > 3:
                raise ValueError(
                    f"第 {index} 行：entity=team 时 members 最多 3 人，实际 {len(row.members)} 人"
                )
            # award_only 场次的行只有奖项，不校验成绩字段
            if self.scoring == "award_only":
                if not row.award:
                    raise ValueError(f"第 {index} 行：award_only 场次必须提供 award")
                continue
            if self.format == "ioi" and row.score is None and row.rank is None:
                raise ValueError(f"第 {index} 行：ioi 场次需要 score 或 rank")
            if self.format == "icpc" and row.solved is None and row.rank is None:
                raise ValueError(f"第 {index} 行：icpc 场次需要 solved 或 rank")

        if self.counts_for_ranking and self.scoring == "formula":
            if not any(row.rank is not None for row in self.standings):
                raise ValueError("counts_for_ranking 场次必须至少有一行提供 rank")
        if self.counts_for_points and self.scoring == "formula":
            if self.max_value is None:
                derived = max(
                    (value for row in self.standings for value in (row.solved, row.score) if value is not None),
                    default=None,
                )
                if derived is None or derived < 1:
                    raise ValueError("记积分的 formula 场次必须提供 max_value（或可推导的非零最高分）")
                self.max_value = derived
        return self

    @model_validator(mode="after")
    def _tier_source_unique(self) -> "ContestJsonDocument":
        if self.tier and self.contest_type:
            raise ValueError("tier 与 contest_type 只能二选一")
        return self


class ContestJsonImportResult(BaseModel):
    contest_id: str
    title: str
    format: str
    entity: str
    tier_name: str
    n_teams: int
    standings_imported: int
    players_created: list[CreatedPlayer] = Field(default_factory=list)
    teams_created: list[str] = Field(default_factory=list)
    unmatched_players: list[UnmatchedPlayer] = Field(default_factory=list)
    unmatched_teams: list[UnmatchedTeam] = Field(default_factory=list)
    raw_path: str
    source_file: str

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
