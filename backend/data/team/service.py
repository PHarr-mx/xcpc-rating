from __future__ import annotations

from datetime import date

from team.exceptions import (
    TeamAlreadyExistsError,
    TeamNotFoundError,
    TeamValidationError,
)
from team.models import Team, TeamCreate, TeamUpdate
from team.store import TeamStore, make_member_key


class TeamService:
    def __init__(self, store: TeamStore | None = None) -> None:
        self.store = store or TeamStore()

    def list_teams(self) -> list[Team]:
        return self.store.load_all()

    def get_team(self, team_id: str) -> Team:
        for team in self.store.load_all():
            if team.id == team_id:
                return team
        raise TeamNotFoundError(team_id)

    def find_by_member_key(self, member_key: str) -> Team | None:
        for team in self.store.load_all():
            if team.member_key == member_key:
                return team
        return None

    def find_by_members(self, members: list[str]) -> Team | None:
        return self.find_by_member_key(make_member_key(members))

    def create_team(self, data: TeamCreate, *, today: date | None = None) -> Team:
        today = today or date.today()
        member_key = make_member_key(data.members)

        existing = self.find_by_member_key(member_key)
        if existing is not None:
            raise TeamAlreadyExistsError(member_key)

        teams = self.store.load_all()
        team_id = data.id or self.store.next_id(teams)

        if any(team.id == team_id for team in teams):
            raise TeamValidationError(f"队伍 ID 冲突: {team_id}")

        team = Team(
            id=team_id,
            member_key=member_key,
            members=data.members,
            size=len(data.members),
            aliases=data.aliases,
            created_at=today,
        )
        teams.append(team)
        self.store.save_all(teams, today=today)
        return team.with_derived_fields(today=today)

    def add_alias(self, team_id: str, alias: str, *, today: date | None = None) -> Team:
        """向已有队伍追加一个别名。"""
        today = today or date.today()
        alias = alias.strip()
        if not alias:
            raise TeamValidationError("别名不能为空")

        teams = self.store.load_all()
        index = self._index_of(teams, team_id)
        current = teams[index]

        if alias in current.aliases:
            return current

        updated = current.model_copy(
            update={"aliases": current.aliases + [alias]}
        )
        teams[index] = updated
        self.store.save_all(teams, today=today)
        return updated.with_derived_fields(today=today)

    def update_team(
        self,
        team_id: str,
        data: TeamUpdate,
        *,
        today: date | None = None,
    ) -> Team:
        today = today or date.today()
        teams = self.store.load_all()
        index = self._index_of(teams, team_id)
        current = teams[index]

        if data.alias is not None:
            alias = data.alias.strip()
            if alias and alias not in current.aliases:
                updated = current.model_copy(
                    update={"aliases": current.aliases + [alias]}
                )
                teams[index] = updated
                self.store.save_all(teams, today=today)
                return updated.with_derived_fields(today=today)

        return current.with_derived_fields(today=today)

    def delete_team(self, team_id: str, *, today: date | None = None) -> Team:
        today = today or date.today()
        teams = self.store.load_all()
        index = self._index_of(teams, team_id)
        removed = teams.pop(index)
        self.store.save_all(teams, today=today)
        return removed

    def _index_of(self, teams: list[Team], team_id: str) -> int:
        for index, team in enumerate(teams):
            if team.id == team_id:
                return index
        raise TeamNotFoundError(team_id)