"""表结构定义（纯 SQLAlchemy 2.0）。

对应 docs/10-数据存储与SQLite.md §4。原文档中的 ``rx.Model`` 已按 reflex 0.9.7 的弃用建议
改为 ``Base``（DeclarativeBase）。DTO 与 ORM 分离：本文件只定义 ORM，领域 DTO 见各模块 models.py。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column

from xcpc_core.db.base import Base


class Player(Base):
    __tablename__ = "player"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # p001
    name: Mapped[str] = mapped_column(String)
    handle: Mapped[str | None] = mapped_column(String, unique=True)
    grade: Mapped[int] = mapped_column(Integer, default=0)  # 0 = 未设置
    status: Mapped[str] = mapped_column(String, default="active")  # probation|active|retired|left
    created_at: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[date | None] = mapped_column(Date)


class OJAccount(Base):
    __tablename__ = "ojaccount"
    __table_args__ = (UniqueConstraint("platform", "handle", name="uq_ojaccount_platform_handle"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    platform: Mapped[str] = mapped_column(String)  # codeforces|atcoder|luogu|nowcoder
    handle: Mapped[str] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String)


class PlayerAlias(Base):
    __tablename__ = "playeralias"
    __table_args__ = (UniqueConstraint("player_id", "alias", name="uq_playeralias_player_alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    alias: Mapped[str] = mapped_column(String)


class Team(Base):
    __tablename__ = "team"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # t001
    member_key: Mapped[str] = mapped_column(String, unique=True, index=True)  # p001|p002|p003
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[date | None] = mapped_column(Date)


class TeamMember(Base):
    __tablename__ = "teammember"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("team.id"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    seat: Mapped[int] = mapped_column(Integer)


class TeamAlias(Base):
    __tablename__ = "teamalias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("team.id"), index=True)
    alias: Mapped[str] = mapped_column(String)  # 队名历史


class Contest(Base):
    __tablename__ = "contest"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String, index=True)  # formal|training
    title: Mapped[str] = mapped_column(String)
    date: Mapped[date] = mapped_column(Date, index=True)
    competition_year: Mapped[int] = mapped_column(Integer, index=True)
    season: Mapped[str] = mapped_column(String, index=True)
    contest_type: Mapped[str | None] = mapped_column(String)  # formal 用，决定权重
    format: Mapped[str] = mapped_column(String)  # team_xcpc|solo_xcpc|oi
    division: Mapped[str | None] = mapped_column(String)  # training 用，决定权重
    total_teams: Mapped[int | None] = mapped_column(Integer)  # formal 必填
    school_teams_count: Mapped[int | None] = mapped_column(Integer)
    rated: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[int] = mapped_column(Integer)  # 基准 100
    weight_source: Mapped[str] = mapped_column(String)  # config|override
    source_file: Mapped[str | None] = mapped_column(String)  # 追溯到 raw/


class Standing(Base):
    __tablename__ = "standing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contest_id: Mapped[str] = mapped_column(ForeignKey("contest.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(String)  # solo 场次为空
    team_name: Mapped[str | None] = mapped_column(String)
    rank: Mapped[int] = mapped_column(Integer)
    school_rank: Mapped[int | None] = mapped_column(Integer)
    award: Mapped[str | None] = mapped_column(String)  # gold|silver|bronze|null
    solved: Mapped[int | None] = mapped_column(Integer)  # xcpc
    penalty: Mapped[int | None] = mapped_column(Integer)  # xcpc
    score: Mapped[int | None] = mapped_column(Integer)  # oi
    manually_added: Mapped[bool] = mapped_column(Boolean, default=False)


class StandingMember(Base):
    __tablename__ = "standingmember"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    standing_id: Mapped[int] = mapped_column(ForeignKey("standing.id"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)


class OJContest(Base):
    __tablename__ = "ojcontest"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    platform: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    date: Mapped[date] = mapped_column(Date, index=True)
    rated: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[int] = mapped_column(Integer)


class OJContestResult(Base):
    __tablename__ = "ojcontestresult"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    oj_contest_id: Mapped[str] = mapped_column(ForeignKey("ojcontest.id"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    platform: Mapped[str] = mapped_column(String)
    handle: Mapped[str] = mapped_column(String)
    rank: Mapped[int | None] = mapped_column(Integer)
    rating_before: Mapped[int | None] = mapped_column(Integer)  # 缺失时按时间序推算
    rating_after: Mapped[int | None] = mapped_column(Integer)
    delta: Mapped[int | None] = mapped_column(Integer)


class OJSnapshot(Base):
    __tablename__ = "ojsnapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    platform: Mapped[str] = mapped_column(String)
    handle: Mapped[str] = mapped_column(String)
    date: Mapped[date] = mapped_column(Date, index=True)
    rating: Mapped[str | None] = mapped_column(String)  # 平台显示名，如「橙名」
    rating_numeric: Mapped[int | None] = mapped_column(Integer)
    solve_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String)  # manual_import|...


class RatingEvent(Base):
    """派生表：可由 Contest/Standing/OJ* 整表重建，不作为事实来源。"""

    __tablename__ = "ratingevent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, unique=True)
    source_type: Mapped[str] = mapped_column(String, index=True)  # formal|training|oj_contest|oj_practice
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(String)
    date: Mapped[date] = mapped_column(Date, index=True)
    competition_year: Mapped[int] = mapped_column(Integer, index=True)
    season: Mapped[str] = mapped_column(String, index=True)
    contest_type: Mapped[str | None] = mapped_column(String)
    contest_format: Mapped[str | None] = mapped_column(String)
    weight: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)  # rank/solved/penalty/score/total_teams


class Meta(Base):
    """单行表。data_version 供 Rating 缓存失效使用。"""

    __tablename__ = "meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    data_version: Mapped[int] = mapped_column(Integer, default=0)
    rating_algorithm: Mapped[str] = mapped_column(String, default="placeholder_v0")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    """审计日志。故意不加外键：用户被删除后审计记录仍须保留。"""

    __tablename__ = "auditlog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String)  # player.update|contest.import|...
    target: Mapped[str] = mapped_column(String)  # p001 / formal_2026_xxx
    diff_json: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime, index=True)


class ImportBatch(Base):
    """xlsx 上传后先落此表暂存，人工复核确认才写正式表。"""

    __tablename__ = "importbatch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uploaded_by: Mapped[int] = mapped_column(Integer)  # localuser.id（reflex-local-auth，二期）
    filename: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # staged|confirmed|discarded
    payload_json: Mapped[str] = mapped_column(Text)  # 解析结果 + 未匹配项
    created_at: Mapped[datetime | None] = mapped_column(DateTime)


class PointsEvent(Base):
    """积分场次配置（UCup 式单场分，RATING_FORMULA_PLAN.md §9）。

    max_value / n_teams 为管理员配置的公式参数；审核通过时随流水快照，
    事后改配置不溯及已记积分。
    """

    __tablename__ = "pointsevent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String)
    date: Mapped[date] = mapped_column(Date, index=True)
    entity: Mapped[str] = mapped_column(String)  # player|team（认证主体）
    kind: Mapped[str] = mapped_column(String)  # solved|score（value 语义：解题数/得分）
    max_value: Mapped[int] = mapped_column(Integer)  # 全场最高解题数/得分
    n_teams: Mapped[int] = mapped_column(Integer)  # 参赛实体数（队数/人数）
    created_by: Mapped[int] = mapped_column(Integer)  # localuser.id
    created_at: Mapped[datetime | None] = mapped_column(DateTime)


class PointsClaim(Base):
    """积分认证：staged → approved/rejected（与 ImportBatch/BindingRequest 同型）。

    唯一性（部分唯一索引，见迁移）：个人赛 (event, player)、队伍赛 (event, team)
    各只允许一条非 rejected 记录，service 层同时前置校验。
    """

    __tablename__ = "pointsclaim"
    __table_args__ = (
        Index(
            "uq_pointsclaim_event_player",
            "event_id",
            "player_id",
            unique=True,
            sqlite_where=sa_text("player_id IS NOT NULL AND status != 'rejected'"),
        ),
        Index(
            "uq_pointsclaim_event_team",
            "event_id",
            "team_id",
            unique=True,
            sqlite_where=sa_text("team_id IS NOT NULL AND status != 'rejected'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("pointsevent.id"), index=True)
    entity: Mapped[str] = mapped_column(String)  # player|team（冗余自 event，便于查询）
    player_id: Mapped[str | None] = mapped_column(ForeignKey("player.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("team.id"), index=True)
    value: Mapped[int] = mapped_column(Integer)  # 解题数/得分，资格线 ≥ 1
    rank: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # staged|approved|rejected
    submitted_by: Mapped[int] = mapped_column(Integer)  # localuser.id
    decided_by: Mapped[int | None] = mapped_column(Integer)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)


class PointsEntry(Base):
    """积分流水（双 owner）：审核通过时写入，一切积分聚合的唯一来源。

    队伍赛通过 → 1 条 team 流水 + 每名现役成员 1 条 player 流水
    （team_context=该队）；个人赛通过 → 1 条 player 流水（team_context 空）。
    队伍复合分的排除规则 = 成员流水按 team_context != 本队 过滤。
    payload_json 为公式输入快照（value/rank/max_value/n_teams），改配置不溯及。
    """

    __tablename__ = "pointsentry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_type: Mapped[str] = mapped_column(String)  # player|team
    owner_id: Mapped[str] = mapped_column(String, index=True)
    points: Mapped[float] = mapped_column(Float)
    event_id: Mapped[int] = mapped_column(ForeignKey("pointsevent.id"), index=True)
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("pointsclaim.id"))
    team_context: Mapped[str | None] = mapped_column(String)
    payload_json: Mapped[str] = mapped_column(Text)
    date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
