from __future__ import annotations

from datetime import date

from team.exceptions import (
    TeamAlreadyExistsError,
    TeamNotFoundError,
    TeamValidationError,
)
from team.models import Team, TeamCreate, TeamUpdate
from team.store import TeamStore, make_member_key, make_team_id


class TeamService:
    def __init__(self, store: TeamStore | None = None) -> None:
        self.store = store or TeamStore()

    def list_teams(
        self,
        *,
        is_school_team: bool | None = None,
    ) -> list[Team]:
        teams = self.store.load_all()
        if is_school_team is not None:
            teams = [team for team in teams if team.is_school_team == is_school_team]
        return teams

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

        team_id = make_team_id(member_key)
        teams = self.store.load_all()

        if any(team.id == team_id for team in teams):
            raise TeamValidationError(f"队伍 ID 冲突: {team_id}")

        names = [data.display_name] if data.display_name else []
        if data.names:
            names = data.names

        team = Team(
            id=team_id,
            member_key=member_key,
            members=data.members,
            size=len(data.members),
            names=names,
            display_name=data.display_name or (names[0] if names else ""),
            is_school_team=data.is_school_team,
            first_seen=today,
            last_seen=today,
            created_at=today,
        )
        teams.append(team)
        self.store.save_all(teams, today=today)
        return team.with_derived_fields(today=today)

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

        updates: dict = {}

        if data.name is not None:
            name = data.name.strip()
            if name and name not in current.names:
                updates["names"] = current.names + [name]

        if data.display_name is not None:
            updates["display_name"] = data.display_name.strip()

        if data.is_school_team is not None:
            updates["is_school_team"] = data.is_school_team

        if not updates:
            return current.with_derived_fields(today=today)

        updated = current.model_copy(update=updates)
        teams[index] = updated
        self.store.save_all(teams, today=today)
        return updated.with_derived_fields(today=today)

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