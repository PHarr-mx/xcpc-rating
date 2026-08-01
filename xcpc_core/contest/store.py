"""比赛 SQLAlchemy repository：ORM 行 ↔ 领域 DTO 的转换边界。

Contest（formal/training 合表）与 Standing 为一对多。保存比赛时整批替换 standings，
天然支持「重复导入以最新为准」的语义（见 docs/03 §9）。
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xcpc_core.contest.exceptions import ContestNotFoundError
from xcpc_core.contest.models import Contest, Standing
from xcpc_core.db.tables import Contest as ContestRow
from xcpc_core.db.tables import Standing as StandingRow
from xcpc_core.db.tables import StandingMember as StandingMemberRow


class ContestStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- 读 ----

    def get(self, contest_id: str) -> Contest | None:
        row = self.session.get(ContestRow, contest_id)
        return self._to_dto(row) if row is not None else None

    def list_all(self, *, source_type: str | None = None) -> list[Contest]:
        stmt = select(ContestRow).order_by(ContestRow.date.desc(), ContestRow.id)
        if source_type is not None:
            stmt = stmt.where(ContestRow.source_type == source_type)
        return [self._to_dto(row) for row in self.session.scalars(stmt)]

    def list_standings(self, contest_id: str) -> list[Standing]:
        rows = self.session.scalars(
            select(StandingRow)
            .where(StandingRow.contest_id == contest_id)
            .order_by(StandingRow.rank, StandingRow.id)
        ).all()
        return [self._to_standing_dto(row) for row in rows]

    # ---- 写 ----

    def insert(self, contest: Contest, standings: list[Standing]) -> None:
        self.session.add(self._to_row(contest))
        self._write_standings(contest.id, standings)
        self._commit()

    def update(self, contest: Contest, standings: list[Standing]) -> None:
        row = self.session.get(ContestRow, contest.id)
        if row is None:
            raise ContestNotFoundError(contest.id)
        row.source_type = contest.source_type
        row.title = contest.title
        row.date = contest.date
        row.competition_year = contest.competition_year
        row.season = contest.season
        row.contest_type = contest.contest_type
        row.format = contest.format
        row.division = contest.division
        row.total_teams = contest.total_teams
        row.school_teams_count = contest.school_teams_count
        row.rated = contest.rated
        row.weight = contest.weight
        row.weight_source = contest.weight_source
        row.source_file = contest.source_file
        self._clear_standings(contest.id)
        self._write_standings(contest.id, standings)
        self._commit()

    def delete(self, contest_id: str) -> None:
        row = self.session.get(ContestRow, contest_id)
        if row is None:
            return
        self._clear_standings(contest_id)
        self.session.delete(row)
        self._commit()

    # ---- 内部：ORM ↔ DTO ----

    def _to_dto(self, row: ContestRow) -> Contest:
        return Contest(
            id=row.id,
            source_type=row.source_type,
            title=row.title,
            date=row.date,
            competition_year=row.competition_year,
            season=row.season,
            contest_type=row.contest_type,
            format=row.format,
            division=row.division,
            total_teams=row.total_teams,
            school_teams_count=row.school_teams_count,
            rated=row.rated,
            weight=row.weight,
            weight_source=row.weight_source,
            source_file=row.source_file,
        )

    def _to_standing_dto(self, row: StandingRow) -> Standing:
        player_ids = list(self.session.scalars(
            select(StandingMemberRow.player_id)
            .where(StandingMemberRow.standing_id == row.id)
            .order_by(StandingMemberRow.id)
        ))
        return Standing(
            team_id=row.team_id,
            team_name=row.team_name,
            rank=row.rank,
            school_rank=row.school_rank,
            award=row.award,
            solved=row.solved,
            penalty=row.penalty,
            score=row.score,
            manually_added=row.manually_added,
            player_ids=player_ids,
        )

    def _to_row(self, contest: Contest) -> ContestRow:
        return ContestRow(
            id=contest.id,
            source_type=contest.source_type,
            title=contest.title,
            date=contest.date,
            competition_year=contest.competition_year,
            season=contest.season,
            contest_type=contest.contest_type,
            format=contest.format,
            division=contest.division,
            total_teams=contest.total_teams,
            school_teams_count=contest.school_teams_count,
            rated=contest.rated,
            weight=contest.weight,
            weight_source=contest.weight_source,
            source_file=contest.source_file,
        )

    def _write_standings(self, contest_id: str, standings: list[Standing]) -> None:
        for item in standings:
            standing = StandingRow(
                contest_id=contest_id,
                team_id=item.team_id,
                team_name=item.team_name,
                rank=item.rank,
                school_rank=item.school_rank,
                award=item.award,
                solved=item.solved,
                penalty=item.penalty,
                score=item.score,
                manually_added=item.manually_added,
            )
            self.session.add(standing)
            self.session.flush()  # 取得 standing.id 供成员引用
            for player_id in item.player_ids:
                self.session.add(StandingMemberRow(standing_id=standing.id, player_id=player_id))

    def _clear_standings(self, contest_id: str) -> None:
        standing_ids = list(self.session.scalars(
            select(StandingRow.id).where(StandingRow.contest_id == contest_id)
        ))
        if standing_ids:
            self.session.execute(
                delete(StandingMemberRow).where(StandingMemberRow.standing_id.in_(standing_ids))
            )
            self.session.execute(
                delete(StandingRow).where(StandingRow.contest_id == contest_id)
            )

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
