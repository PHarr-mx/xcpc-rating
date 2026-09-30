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
from xcpc_core.db.tables import RatingEvent as RatingEventRow


class ContestStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- 读 ----

    def get(self, contest_id: str) -> Contest | None:
        row = self.session.get(ContestRow, contest_id)
        return self._to_dto(row) if row is not None else None

    def list_all(self, *, tier_id: int | None = None) -> list[Contest]:
        stmt = select(ContestRow).order_by(ContestRow.date.desc(), ContestRow.id)
        if tier_id is not None:
            stmt = stmt.where(ContestRow.tier_id == tier_id)
        return [self._to_dto(row) for row in self.session.scalars(stmt)]

    def list_standings(self, contest_id: str) -> list[Standing]:
        rows = self.session.scalars(
            select(StandingRow)
            .where(StandingRow.contest_id == contest_id)
            # award_only 行可无名次：rank 为空的排后面，有名次的按名次升序
            .order_by(StandingRow.rank.is_not(None), StandingRow.rank, StandingRow.id)
        ).all()
        return [self._to_standing_dto(row) for row in rows]

    # ---- 写 ----

    def insert(self, contest: Contest, standings: list[Standing], *, commit: bool = True) -> None:
        self.session.add(self._to_row(contest))
        self._write_standings(contest.id, standings)
        if commit:
            self._commit()

    def update(self, contest: Contest, standings: list[Standing], *, commit: bool = True) -> None:
        row = self.session.get(ContestRow, contest.id)
        if row is None:
            raise ContestNotFoundError(contest.id)
        row.title = contest.title
        row.date = contest.date
        row.competition_year = contest.competition_year
        row.season = contest.season
        row.format = contest.format
        row.entity = contest.entity
        row.tier_id = contest.tier_id
        row.n_teams = contest.n_teams
        row.school_teams_count = contest.school_teams_count
        row.max_value = contest.max_value
        row.scoring = contest.scoring
        row.counts_for_points = contest.counts_for_points
        row.counts_for_ranking = contest.counts_for_ranking
        row.allow_claims = contest.allow_claims
        row.source_file = contest.source_file
        self._clear_standings(contest.id)
        self._write_standings(contest.id, standings)
        if commit:
            self._commit()

    def delete(self, contest_id: str, *, commit: bool = True) -> None:
        row = self.session.get(ContestRow, contest_id)
        if row is None:
            return
        self._clear_standings(contest_id)
        # RatingEvent 是由 Contest/Standing 派生的非事实表，event_id
        # 约定以 ``{contest_id}#`` 开头；删除比赛时同步清理，避免旧事件继续进入榜单。
        for event in self.session.scalars(select(RatingEventRow)).all():
            if event.event_id.startswith(f"{contest_id}#"):
                self.session.delete(event)
        self.session.delete(row)
        if commit:
            self._commit()

    # ---- 内部：ORM ↔ DTO ----

    def _to_dto(self, row: ContestRow) -> Contest:
        return Contest(
            id=row.id,
            title=row.title,
            date=row.date,
            competition_year=row.competition_year,
            season=row.season,
            format=row.format,
            entity=row.entity,
            tier_id=row.tier_id,
            n_teams=row.n_teams,
            school_teams_count=row.school_teams_count,
            max_value=row.max_value,
            scoring=row.scoring,
            counts_for_points=row.counts_for_points,
            counts_for_ranking=row.counts_for_ranking,
            allow_claims=row.allow_claims,
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
            title=contest.title,
            date=contest.date,
            competition_year=contest.competition_year,
            season=contest.season,
            format=contest.format,
            entity=contest.entity,
            tier_id=contest.tier_id,
            n_teams=contest.n_teams,
            school_teams_count=contest.school_teams_count,
            max_value=contest.max_value,
            scoring=contest.scoring,
            counts_for_points=contest.counts_for_points,
            counts_for_ranking=contest.counts_for_ranking,
            allow_claims=contest.allow_claims,
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
