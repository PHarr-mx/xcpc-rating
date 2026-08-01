"""选手 SQLAlchemy repository：ORM 行 ↔ 领域 DTO 的转换边界。

DTO 见 models.py；ORM 表见 xcpc_core/db/tables.py。service 层只接触 DTO，不持有 ORM 实例。
唯一性由 DB 约束兜底，冲突以 ``IntegrityError`` 抛出，由 service 层转成领域异常。
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xcpc_core.db.session import find_repo_root
from xcpc_core.db.tables import OJAccount as OJAccountRow
from xcpc_core.db.tables import Player as PlayerRow
from xcpc_core.db.tables import PlayerAlias as PlayerAliasRow
from xcpc_core.player.exceptions import PlayerNotFoundError
from xcpc_core.player.models import OJAccount, Player, PlayerStatus

__all__ = ["PlayerStore", "find_repo_root"]


class PlayerStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- 读 ----

    def list_all(self) -> list[Player]:
        rows = self.session.scalars(select(PlayerRow).order_by(PlayerRow.id)).all()
        return [self._to_dto(row) for row in rows]

    def get(self, player_id: str) -> Player | None:
        row = self.session.get(PlayerRow, player_id)
        return self._to_dto(row) if row is not None else None

    # ---- 写 ----

    def insert(self, player: Player) -> None:
        self.session.add(PlayerRow(
            id=player.id,
            name=player.name,
            handle=player.handle,
            grade=player.grade,
            status=player.status.value,
            created_at=player.created_at,
            updated_at=player.updated_at,
        ))
        self._write_nested(player.id, player.oj_accounts, player.aliases)
        self._commit()

    def update(self, player: Player) -> None:
        row = self.session.get(PlayerRow, player.id)
        if row is None:
            raise PlayerNotFoundError(player.id)
        row.name = player.name
        row.handle = player.handle
        row.grade = player.grade
        row.status = player.status.value
        row.updated_at = player.updated_at
        self._clear_nested(player.id)
        self._write_nested(player.id, player.oj_accounts, player.aliases)
        self._commit()

    def delete(self, player_id: str) -> Player | None:
        row = self.session.get(PlayerRow, player_id)
        if row is None:
            return None
        dto = self._to_dto(row)
        self._clear_nested(player_id)
        self.session.delete(row)
        self._commit()
        return dto

    def next_id(self) -> str:
        max_seq = 0
        for pid in self.session.scalars(select(PlayerRow.id)):
            if pid.startswith("p") and pid[1:].isdigit():
                max_seq = max(max_seq, int(pid[1:]))
        return f"p{max_seq + 1:03d}"

    # ---- 内部：ORM ↔ DTO ----

    def _to_dto(self, row: PlayerRow) -> Player:
        accounts = self.session.scalars(
            select(OJAccountRow).where(OJAccountRow.player_id == row.id).order_by(OJAccountRow.id)
        ).all()
        aliases = list(self.session.scalars(
            select(PlayerAliasRow.alias).where(PlayerAliasRow.player_id == row.id).order_by(PlayerAliasRow.id)
        ))
        return Player(
            id=row.id,
            name=row.name,
            handle=row.handle,
            grade=row.grade,
            status=PlayerStatus(row.status),
            oj_accounts=[OJAccount(platform=a.platform, handle=a.handle, user_id=a.user_id) for a in accounts],
            aliases=aliases,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _write_nested(self, player_id: str, accounts: list[OJAccount], aliases: list[str]) -> None:
        for account in accounts:
            self.session.add(OJAccountRow(
                player_id=player_id,
                platform=account.platform,
                handle=account.handle,
                user_id=account.user_id,
            ))
        for alias in aliases:
            self.session.add(PlayerAliasRow(player_id=player_id, alias=alias))

    def _clear_nested(self, player_id: str) -> None:
        self.session.execute(delete(OJAccountRow).where(OJAccountRow.player_id == player_id))
        self.session.execute(delete(PlayerAliasRow).where(PlayerAliasRow.player_id == player_id))

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
