"""contest unification: tier/awardlevel + contest reform + points relink

Revision ID: 0003_unify_contest
Revises: bb6e383f49c0
Create Date: 2026-09-30

比赛统一化改造（CONTEST_UNIFICATION_PLAN §2）：

1. 新建 ``tier``（赛事等级，积分/排名系数）与 ``awardlevel``（奖项基线分），
   并按 contest_weights.yaml 播种初始等级（系数 = weight/100）+ 兜底「未分级」；
2. ``contest`` 表改造：format 收敛为 icpc|ioi，新增 entity/tier_id/max_value/
   scoring/双开关/allow_claims，删除 source_type/contest_type/division/weight/
   weight_source/rated（语义由 tier 与双开关承载）；
3. ``pointsevent`` 数据并入 contest（id=``points_{旧id}``）后删表；
4. ``pointsclaim``/``pointsentry`` 的 event_id 改为 contest_id 外键，claim 新增
   award 申报列、value/rank 放宽为可空（award_only 场次不填）。

存量映射口径（方案 D6）：正式赛记录保留（tier 按 contest_type 对应、
counts_for_ranking=原 rated、counts_for_points=False、allow_claims=False）；
积分场次并入 contest（tier=未分级、counts_for_points=True、allow_claims=True）。

实现注意：运行时连接 PRAGMA foreign_keys=ON 且事务内 pragma 是 no-op，因此本迁移
不 rename/drop 有子表引用的父表——先把相关表数据全部读进内存，按「子表→父表」
顺序 drop，再按新 schema 建表回插（数据量小，内存中转可接受）。

downgrade 只还原旧表结构，不回搬数据（积分流水与比赛映射不可逆，需重灌）。
"""
from alembic import op
import sqlalchemy as sa

from xcpc_core.tier.models import FALLBACK_TIER_NAME
from xcpc_core.tier.service import builtin_config_entries

# revision identifiers, used by Alembic.
revision = '0003_unify_contest'
down_revision = '0002_points'
branch_labels = None
depends_on = None


def _seed_tier_and_award(conn: sa.Connection) -> dict[str, int]:
    """建初始赛事等级与奖项基线，返回 {等级名: id}。"""
    from sqlalchemy.orm import Session

    from xcpc_core.tier.service import seed_defaults

    session = Session(bind=conn)
    try:
        try:
            from xcpc_core.player.store import find_repo_root

            root = find_repo_root()
        except Exception:
            root = None
        seed_defaults(session, repo_root=root)
        return {name: tier_id for tier_id, name in conn.execute(sa.text("SELECT id, name FROM tier")).all()}
    finally:
        session.close()


def _as_date(raw):
    """SQLite text 列经裸 text() 查询返回 str，统一为 date 供日历工具使用。"""
    from datetime import date as date_cls

    if isinstance(raw, str):
        return date_cls.fromisoformat(raw)
    return raw


def _fetch_all(conn: sa.Connection, table: str) -> list[dict]:
    return [dict(row) for row in conn.execute(sa.text(f"SELECT * FROM {table}")).mappings()]


def _legacy_format_map(old_format: str) -> tuple[str, str]:
    """旧 format 三值 → 新 (format, entity) 二维。"""
    return {
        "team_xcpc": ("icpc", "team"),
        "solo_xcpc": ("icpc", "player"),
        "oi": ("ioi", "player"),
    }.get(old_format, ("icpc", "team"))


def _insert_contest(conn: sa.Connection, spec: dict) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO contest (id, title, date, competition_year, season, format, entity,"
            " tier_id, n_teams, school_teams_count, max_value, scoring, counts_for_points,"
            " counts_for_ranking, allow_claims, source_file)"
            " VALUES (:id, :title, :date, :competition_year, :season, :format, :entity,"
            " :tier_id, :n_teams, :school_teams_count, :max_value, :scoring, :counts_for_points,"
            " :counts_for_ranking, :allow_claims, :source_file)"
        ),
        spec,
    )


def _contest_specs(
    contest_rows: list[dict],
    standing_rows: list[dict],
    event_rows: list[dict],
    tier_ids: dict[str, int],
) -> list[dict]:
    """存量 contest + pointsevent → 新 contest 行参数。"""
    from xcpc_core.utils.calendar import competition_year, season_label

    fallback_id = tier_ids[FALLBACK_TIER_NAME]
    config = builtin_config_entries()
    max_values: dict[str, int] = {}
    for row in standing_rows:
        value = row.get("solved") if row.get("solved") is not None else row.get("score")
        if value is not None:
            contest_id = row["contest_id"]
            max_values[contest_id] = max(max_values.get(contest_id, 0), value)

    specs: list[dict] = []
    for row in contest_rows:
        key = row.get("contest_type") if row["source_type"] == "formal" else row.get("division")
        label = config.get(key, (None, 0.0))[0] if key else None
        fmt, entity = _legacy_format_map(row["format"])
        specs.append({
            "id": row["id"],
            "title": row["title"],
            "date": row["date"],
            "competition_year": row["competition_year"],
            "season": row["season"],
            "format": fmt,
            "entity": entity,
            "tier_id": tier_ids.get(label, fallback_id),
            "n_teams": row.get("total_teams"),
            "school_teams_count": row.get("school_teams_count"),
            "max_value": max_values.get(row["id"]),
            "scoring": "formula",
            "counts_for_points": False,
            "counts_for_ranking": bool(row["rated"]),
            "allow_claims": False,  # 导入的正式赛不走申报通道
            "source_file": row.get("source_file"),
        })

    for ev in event_rows:
        event_date = _as_date(ev["date"])
        specs.append({
            "id": f"points_{ev['id']}",  # 积分场次并入统一比赛：保留可读的来源前缀
            "title": ev["title"],
            "date": ev["date"],
            "competition_year": competition_year(event_date),
            "season": season_label(event_date),
            "format": "icpc" if ev["kind"] == "solved" else "ioi",
            "entity": ev["entity"],
            "tier_id": fallback_id,
            "n_teams": ev["n_teams"],
            "school_teams_count": None,
            "max_value": ev["max_value"],
            "scoring": "formula",
            "counts_for_points": True,
            "counts_for_ranking": False,
            "allow_claims": True,
            "source_file": None,
        })
    return specs


def upgrade() -> None:
    from xcpc_core.db.tables import Contest, PointsClaim, PointsEntry, Standing, StandingMember

    conn = op.get_bind()

    # 1. 等级表先行（contest.tier_id 的父表）
    op.create_table(
        'tier',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('coefficient', sa.Float(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'awardlevel',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('base_points', sa.Float(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    tier_ids = _seed_tier_and_award(conn)

    # 2. 数据全部进内存（涉及 contest 的五张表，子表在前）
    entry_rows = _fetch_all(conn, "pointsentry")
    claim_rows = _fetch_all(conn, "pointsclaim")
    event_rows = _fetch_all(conn, "pointsevent")
    member_rows = _fetch_all(conn, "standingmember")
    standing_rows = _fetch_all(conn, "standing")
    contest_rows = _fetch_all(conn, "contest")

    # 3. 子表 → 父表 逐个 drop（FK ON 下父表带子引用时 drop 会被隐式 DELETE 卡住）
    op.drop_table("pointsentry")
    op.drop_table("pointsclaim")
    op.drop_table("pointsevent")
    op.drop_table("standingmember")
    op.drop_table("standing")
    op.drop_table("contest")

    # 4. 按新 schema 重建（tables.py 同型）并回插
    op.create_table(
        'contest',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('competition_year', sa.Integer(), nullable=False),
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('format', sa.String(), nullable=False),
        sa.Column('entity', sa.String(), nullable=False),
        sa.Column('tier_id', sa.Integer(), nullable=True),
        sa.Column('n_teams', sa.Integer(), nullable=True),
        sa.Column('school_teams_count', sa.Integer(), nullable=True),
        sa.Column('max_value', sa.Integer(), nullable=True),
        sa.Column('scoring', sa.String(), nullable=False),
        sa.Column('counts_for_points', sa.Boolean(), nullable=False),
        sa.Column('counts_for_ranking', sa.Boolean(), nullable=False),
        sa.Column('allow_claims', sa.Boolean(), nullable=False),
        sa.Column('source_file', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['tier_id'], ['tier.id'],),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('contest', schema=None) as batch_op:
        batch_op.create_index('ix_contest_date', ['date'], unique=False)
        batch_op.create_index('ix_contest_competition_year', ['competition_year'], unique=False)
        batch_op.create_index('ix_contest_season', ['season'], unique=False)
        batch_op.create_index('ix_contest_tier_id', ['tier_id'], unique=False)

    op.create_table(
        'standing',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contest_id', sa.String(), nullable=False),
        sa.Column('team_id', sa.String(), nullable=True),
        sa.Column('team_name', sa.String(), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('school_rank', sa.Integer(), nullable=True),
        sa.Column('award', sa.String(), nullable=True),
        sa.Column('solved', sa.Integer(), nullable=True),
        sa.Column('penalty', sa.Integer(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('manually_added', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['contest_id'], ['contest.id'],),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('standing', schema=None) as batch_op:
        batch_op.create_index('ix_standing_contest_id', ['contest_id'], unique=False)

    op.create_table(
        'standingmember',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('standing_id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['player_id'], ['player.id'],),
        sa.ForeignKeyConstraint(['standing_id'], ['standing.id'],),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('standingmember', schema=None) as batch_op:
        batch_op.create_index('ix_standingmember_standing_id', ['standing_id'], unique=False)
        batch_op.create_index('ix_standingmember_player_id', ['player_id'], unique=False)

    op.create_table(
        'pointsclaim',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contest_id', sa.String(), nullable=False),
        sa.Column('entity', sa.String(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=True),
        sa.Column('team_id', sa.String(), nullable=True),
        sa.Column('value', sa.Integer(), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('award', sa.String(), nullable=True),
        sa.Column('note', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('submitted_by', sa.Integer(), nullable=False),
        sa.Column('decided_by', sa.Integer(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['contest_id'], ['contest.id'],),
        sa.ForeignKeyConstraint(['player_id'], ['player.id'],),
        sa.ForeignKeyConstraint(['team_id'], ['team.id'],),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('pointsclaim', schema=None) as batch_op:
        batch_op.create_index('ix_pointsclaim_contest_id', ['contest_id'], unique=False)
        batch_op.create_index('ix_pointsclaim_player_id', ['player_id'], unique=False)
        batch_op.create_index('ix_pointsclaim_team_id', ['team_id'], unique=False)
        batch_op.create_index(
            'uq_pointsclaim_event_player', ['contest_id', 'player_id'], unique=True,
            sqlite_where=sa.text("player_id IS NOT NULL AND status != 'rejected'"),
        )
        batch_op.create_index(
            'uq_pointsclaim_event_team', ['contest_id', 'team_id'], unique=True,
            sqlite_where=sa.text("team_id IS NOT NULL AND status != 'rejected'"),
        )

    op.create_table(
        'pointsentry',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('owner_type', sa.String(), nullable=False),
        sa.Column('owner_id', sa.String(), nullable=False),
        sa.Column('points', sa.Float(), nullable=False),
        sa.Column('contest_id', sa.String(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=True),
        sa.Column('team_context', sa.String(), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['claim_id'], ['pointsclaim.id'],),
        sa.ForeignKeyConstraint(['contest_id'], ['contest.id'],),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('pointsentry', schema=None) as batch_op:
        batch_op.create_index('ix_pointsentry_date', ['date'], unique=False)
        batch_op.create_index('ix_pointsentry_contest_id', ['contest_id'], unique=False)
        batch_op.create_index('ix_pointsentry_owner_id', ['owner_id'], unique=False)

    # 5. 回插：contest（存量 + pointsevent 并入）→ standing/member → claim/entry
    for spec in _contest_specs(contest_rows, standing_rows, event_rows, tier_ids):
        _insert_contest(conn, spec)

    for row in standing_rows:
        conn.execute(
            sa.text(
                "INSERT INTO standing (id, contest_id, team_id, team_name, rank, school_rank,"
                " award, solved, penalty, score, manually_added)"
                " VALUES (:id, :contest_id, :team_id, :team_name, :rank, :school_rank,"
                " :award, :solved, :penalty, :score, :manually_added)"
            ),
            row,
        )
    for row in member_rows:
        conn.execute(
            sa.text(
                "INSERT INTO standingmember (id, standing_id, player_id)"
                " VALUES (:id, :standing_id, :player_id)"
            ),
            row,
        )

    event_id_map = {ev["id"]: f"points_{ev['id']}" for ev in event_rows}
    for row in claim_rows:
        conn.execute(
            sa.text(
                "INSERT INTO pointsclaim (id, contest_id, entity, player_id, team_id, value,"
                " rank, award, note, status, submitted_by, decided_by, decided_at, created_at)"
                " VALUES (:id, :contest_id, :entity, :player_id, :team_id, :value,"
                " :rank, NULL, :note, :status, :submitted_by, :decided_by, :decided_at, :created_at)"
            ),
            {**row, "contest_id": event_id_map[row["event_id"]]},
        )
    for row in entry_rows:
        conn.execute(
            sa.text(
                "INSERT INTO pointsentry (id, owner_type, owner_id, points, contest_id, claim_id,"
                " team_context, payload_json, date, created_at)"
                " VALUES (:id, :owner_type, :owner_id, :points, :contest_id, :claim_id,"
                " :team_context, :payload_json, :date, :created_at)"
            ),
            {**row, "contest_id": event_id_map[row["event_id"]]},
        )

    # 可用性自检：ORM 模型必须能映射新表（漂移测试另有 schema 级守护）
    for model in (Contest, Standing, StandingMember, PointsClaim, PointsEntry):
        assert model.__tablename__


def downgrade() -> None:
    """只还原旧表结构，不回搬数据（映射不可逆）；积分数据需重灌。"""
    with op.batch_alter_table('pointsentry', schema=None) as batch_op:
        batch_op.drop_index('ix_pointsentry_owner_id')
        batch_op.drop_index('ix_pointsentry_contest_id')
        batch_op.drop_index('ix_pointsentry_date')
    op.drop_table('pointsentry')

    with op.batch_alter_table('pointsclaim', schema=None) as batch_op:
        batch_op.drop_index('uq_pointsclaim_event_team', sqlite_where=sa.text("team_id IS NOT NULL AND status != 'rejected'"))
        batch_op.drop_index('uq_pointsclaim_event_player', sqlite_where=sa.text("player_id IS NOT NULL AND status != 'rejected'"))
        batch_op.drop_index('ix_pointsclaim_team_id')
        batch_op.drop_index('ix_pointsclaim_player_id')
        batch_op.drop_index('ix_pointsclaim_contest_id')
    op.drop_table('pointsclaim')

    op.create_table(
        'pointsevent',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('entity', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('max_value', sa.Integer(), nullable=False),
        sa.Column('n_teams', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('pointsevent', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pointsevent_date'), ['date'], unique=False)

    with op.batch_alter_table('contest', schema=None) as batch_op:
        batch_op.drop_index('ix_contest_tier_id')
        batch_op.drop_index('ix_contest_season')
        batch_op.drop_index('ix_contest_competition_year')
        batch_op.drop_index('ix_contest_date')
    op.drop_table('contest')
    op.create_table(
        'contest',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('competition_year', sa.Integer(), nullable=False),
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('contest_type', sa.String(), nullable=True),
        sa.Column('format', sa.String(), nullable=False),
        sa.Column('division', sa.String(), nullable=True),
        sa.Column('total_teams', sa.Integer(), nullable=True),
        sa.Column('school_teams_count', sa.Integer(), nullable=True),
        sa.Column('rated', sa.Boolean(), nullable=False),
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.Column('weight_source', sa.String(), nullable=False),
        sa.Column('source_file', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('contest', schema=None) as batch_op:
        batch_op.create_index('ix_contest_date', ['date'], unique=False)
        batch_op.create_index('ix_contest_competition_year', ['competition_year'], unique=False)
        batch_op.create_index('ix_contest_season', ['season'], unique=False)
        batch_op.create_index('ix_contest_source_type', ['source_type'], unique=False)

    op.drop_table('awardlevel')
    op.drop_table('tier')
