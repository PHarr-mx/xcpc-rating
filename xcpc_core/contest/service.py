from __future__ import annotations

from datetime import date

from xcpc_core.contest.exceptions import ContestNotFoundError
from xcpc_core.contest.models import Contest, ContestCreate, ContestDetail
from xcpc_core.contest.store import ContestStore
from xcpc_core.utils.calendar import competition_year, season_label


class ContestService:
    def __init__(self, store: ContestStore | None = None) -> None:
        self.store = store or ContestStore()

    def save_contest(self, data: ContestCreate, *, today: date | None = None) -> Contest:
        """保存比赛（含成绩）。已存在则整批替换 standings——重复导入以最新为准。"""
        contest = Contest(
            id=data.id,
            source_type=data.source_type,
            title=data.title,
            date=data.date,
            competition_year=competition_year(data.date),
            season=season_label(data.date),
            contest_type=data.contest_type,
            format=data.format,
            division=data.division,
            total_teams=data.total_teams,
            school_teams_count=data.school_teams_count,
            rated=data.rated,
            weight=data.weight,
            weight_source=data.weight_source,
            source_file=data.source_file,
        )
        if self.store.get(data.id) is None:
            self.store.insert(contest, data.standings)
        else:
            self.store.update(contest, data.standings)
        return contest

    def get_contest(self, contest_id: str) -> ContestDetail:
        contest = self.store.get(contest_id)
        if contest is None:
            raise ContestNotFoundError(contest_id)
        return ContestDetail(contest=contest, standings=self.store.list_standings(contest_id))

    def list_contests(self, *, source_type: str | None = None) -> list[Contest]:
        return self.store.list_all(source_type=source_type)

    def delete_contest(self, contest_id: str) -> None:
        self.store.delete(contest_id)
