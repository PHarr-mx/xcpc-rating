"""队伍 SQLAlchemy repository：ORM 行 ↔ 领域 DTO 的转换边界。

队伍身份由队员集合（``member_key``）决定，与队名无关。
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xcpc_core.db.session import find_repo_root
from xcpc_core.db.tables import Team as TeamRow
from xcpc_core.db.tables import TeamAlias as TeamAliasRow
from xcpc_core.db.tables import TeamMember as TeamMemberRow
from xcpc_core.team.exceptions import TeamNotFoundError
from xcpc_core.team.models import Team

__all__ = ["TeamStore", "find_repo_root", "make_member_key"]


def make_member_key(members: list[str]) -> str:
    return "|".join(sorted(members))


class TeamStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- 读 ----

    def list_all(self) -> list[Team]:
        rows = self.session.scalars(select(TeamRow).order_by(TeamRow.id)).all()
        return [self._to_dto(row) for row in rows]

    def get(self, team_id: str) -> Team | None:
        row = self.session.get(TeamRow, team_id)
        return self._to_dto(row) if row is not None else None

    # ---- 写 ----

    def insert(self, team: Team) -> None:
        self.session.add(TeamRow(
            id=team.id,
            member_key=team.member_key,
            size=team.size,
            created_at=team.created_at,
            updated_at=team.updated_at,
        ))
        self._write_nested(team.id, team.members, team.aliases)
        self._commit()

    def update(self, team: Team) -> None:
        row = self.session.get(TeamRow, team.id)
        if row is None:
            raise TeamNotFoundError(team.id)
        row.member_key = team.member_key
        row.size = team.size
        row.updated_at = team.updated_at
        self._clear_nested(team.id)
        self._write_nested(team.id, team.members, team.aliases)
        self._commit()

    def delete(self, team_id: str) -> Team | None:
        row = self.session.get(TeamRow, team_id)
        if row is None:
            return None
        dto = self._to_dto(row)
        self._clear_nested(team_id)
        self.session.delete(row)
        self._commit()
        return dto

    def next_id(self) -> str:
        max_seq = 0
        for tid in self.session.scalars(select(TeamRow.id)):
            if tid.startswith("t") and tid[1:].isdigit():
                max_seq = max(max_seq, int(tid[1:]))
        return f"t{max_seq + 1:03d}"

    # ---- 内部：ORM ↔ DTO ----

    def _to_dto(self, row: TeamRow) -> Team:
        members = list(self.session.scalars(
            select(TeamMemberRow.player_id)
            .where(TeamMemberRow.team_id == row.id)
            .order_by(TeamMemberRow.seat)
        ))
        aliases = list(self.session.scalars(
            select(TeamAliasRow.alias).where(TeamAliasRow.team_id == row.id).order_by(TeamAliasRow.id)
        ))
        return Team(
            id=row.id,
            member_key=row.member_key,
            members=members,
            size=row.size,
            aliases=aliases,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _write_nested(self, team_id: str, members: list[str], aliases: list[str]) -> None:
        for seat, player_id in enumerate(members):
            self.session.add(TeamMemberRow(team_id=team_id, player_id=player_id, seat=seat))
        for alias in aliases:
            self.session.add(TeamAliasRow(team_id=team_id, alias=alias))

    def _clear_nested(self, team_id: str) -> None:
        self.session.execute(delete(TeamMemberRow).where(TeamMemberRow.team_id == team_id))
        self.session.execute(delete(TeamAliasRow).where(TeamAliasRow.team_id == team_id))

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
