from __future__ import annotations

from datetime import date

from sqlalchemy.exc import IntegrityError

from xcpc_core.team.exceptions import (
    TeamAlreadyExistsError,
    TeamNotFoundError,
    TeamValidationError,
)
from xcpc_core.team.models import Team, TeamCreate, TeamUpdate
from xcpc_core.team.store import TeamStore, make_member_key


class TeamService:
    def __init__(self, store: TeamStore | None = None) -> None:
        self.store = store or TeamStore()

    def list_teams(self) -> list[Team]:
        return self.store.list_all()

    def get_team(self, team_id: str) -> Team:
        team = self.store.get(team_id)
        if team is None:
            raise TeamNotFoundError(team_id)
        return team

    def find_by_member_key(self, member_key: str) -> Team | None:
        for team in self.store.list_all():
            if team.member_key == member_key:
                return team
        return None

    def find_by_members(self, members: list[str]) -> Team | None:
        return self.find_by_member_key(make_member_key(members))

    def create_team(self, data: TeamCreate, *, today: date | None = None) -> Team:
        today = today or date.today()
        member_key = make_member_key(data.members)
        if self.find_by_member_key(member_key) is not None:
            raise TeamAlreadyExistsError(member_key)

        team_id = data.id or self.store.next_id()
        if self.store.get(team_id) is not None:
            raise TeamValidationError(f"队伍 ID 冲突: {team_id}")

        team = Team(
            id=team_id,
            member_key=member_key,
            members=data.members,
            size=len(data.members),
            aliases=data.aliases,
            created_at=today,
        )
        try:
            self.store.insert(team)
        except IntegrityError as exc:
            raise TeamAlreadyExistsError(member_key) from exc
        return team.with_derived_fields(today=today)

    def add_alias(self, team_id: str, alias: str, *, today: date | None = None) -> Team:
        """向已有队伍追加一个别名。"""
        today = today or date.today()
        alias = alias.strip()
        if not alias:
            raise TeamValidationError("别名不能为空")

        current = self.store.get(team_id)
        if current is None:
            raise TeamNotFoundError(team_id)
        if alias in current.aliases:
            return current

        updated = current.model_copy(update={"aliases": current.aliases + [alias]})
        self.store.update(updated)
        return updated.with_derived_fields(today=today)

    def update_team(
        self,
        team_id: str,
        data: TeamUpdate,
        *,
        today: date | None = None,
    ) -> Team:
        today = today or date.today()
        current = self.store.get(team_id)
        if current is None:
            raise TeamNotFoundError(team_id)

        if data.alias is not None:
            alias = data.alias.strip()
            if alias and alias not in current.aliases:
                updated = current.model_copy(update={"aliases": current.aliases + [alias]})
                self.store.update(updated)
                return updated.with_derived_fields(today=today)

        return current.with_derived_fields(today=today)

    def delete_team(self, team_id: str, *, today: date | None = None) -> Team:
        today = today or date.today()
        removed = self.store.delete(team_id)
        if removed is None:
            raise TeamNotFoundError(team_id)
        return removed
