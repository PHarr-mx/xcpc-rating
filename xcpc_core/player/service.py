from __future__ import annotations

from datetime import date

from sqlalchemy.exc import IntegrityError

from xcpc_core.player.exceptions import (
    PlayerAlreadyExistsError,
    PlayerNotFoundError,
    PlayerValidationError,
)
from xcpc_core.player.models import Player, PlayerCreate, PlayerStatus, PlayerUpdate
from xcpc_core.player.store import PlayerStore

_UNIQUE_VIOLATION_MSG = "校内 handle 或 OJ 账号与他人重复"


class PlayerService:
    def __init__(self, store: PlayerStore | None = None) -> None:
        self.store = store or PlayerStore()

    def list_players(
        self,
        *,
        include_left: bool = True,
        status: PlayerStatus | None = None,
        grade: int | None = None,
    ) -> list[Player]:
        players = self.store.list_all()
        if not include_left:
            players = [player for player in players if player.status != PlayerStatus.left]
        if status is not None:
            players = [player for player in players if player.status == status]
        if grade is not None:
            players = [player for player in players if player.grade == grade]
        return players

    def get_player(self, player_id: str) -> Player:
        player = self.store.get(player_id)
        if player is None:
            raise PlayerNotFoundError(player_id)
        return player

    def find_by_oj(self, platform: str, handle: str) -> Player | None:
        handle = handle.strip()
        for player in self.store.list_all():
            for account in player.oj_accounts:
                if account.platform == platform and account.handle == handle:
                    return player
        return None

    def find_by_name(self, name: str, *, grade: int | None = None) -> list[Player]:
        name = name.strip()
        results: list[Player] = []
        for player in self.store.list_all():
            if grade is not None and player.grade != grade:
                continue
            if player.name == name or name in player.aliases:
                results.append(player)
        return results

    def create_player(self, data: PlayerCreate, *, today: date | None = None) -> Player:
        today = today or date.today()
        player_id = data.id or self.store.next_id()
        if self.store.get(player_id) is not None:
            raise PlayerAlreadyExistsError(player_id)

        player = Player(
            id=player_id,
            name=data.name,
            handle=data.handle,
            grade=data.grade,
            status=data.status,
            oj_accounts=data.oj_accounts,
            aliases=data.aliases,
            created_at=today,
        )
        try:
            self.store.insert(player)
        except IntegrityError as exc:
            raise PlayerValidationError(_UNIQUE_VIOLATION_MSG) from exc
        return player.with_derived_fields(today=today)

    def update_player(
        self,
        player_id: str,
        data: PlayerUpdate,
        *,
        today: date | None = None,
    ) -> Player:
        today = today or date.today()
        current = self.store.get(player_id)
        if current is None:
            raise PlayerNotFoundError(player_id)

        updated = current.model_copy(
            update={key: value for key, value in data.model_dump(exclude_unset=True).items()}
        )
        updated.updated_at = today
        try:
            self.store.update(updated)
        except IntegrityError as exc:
            raise PlayerValidationError(_UNIQUE_VIOLATION_MSG) from exc
        return updated.with_derived_fields(today=today)

    def delete_player(self, player_id: str, *, today: date | None = None) -> Player:
        today = today or date.today()
        removed = self.store.delete(player_id)
        if removed is None:
            raise PlayerNotFoundError(player_id)
        return removed

    def mark_left(self, player_id: str, *, today: date | None = None) -> Player:
        return self.update_player(
            player_id,
            PlayerUpdate(status=PlayerStatus.left),
            today=today,
        )
