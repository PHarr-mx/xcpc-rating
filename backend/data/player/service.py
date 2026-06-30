from __future__ import annotations

from datetime import date

from player.exceptions import (
    PlayerAlreadyExistsError,
    PlayerNotFoundError,
    PlayerValidationError,
)
from player.models import OJAccount, Player, PlayerCreate, PlayerStatus, PlayerUpdate
from player.store import PlayerStore


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
        players = self.store.load_all()
        if not include_left:
            players = [player for player in players if player.status != PlayerStatus.left]
        if status is not None:
            players = [player for player in players if player.status == status]
        if grade is not None:
            players = [player for player in players if player.grade == grade]
        return players

    def get_player(self, player_id: str) -> Player:
        for player in self.store.load_all():
            if player.id == player_id:
                return player
        raise PlayerNotFoundError(player_id)

    def find_by_oj(self, platform: str, handle: str) -> Player | None:
        handle = handle.strip()
        for player in self.store.load_all():
            for account in player.oj_accounts:
                if account.platform == platform and account.handle == handle:
                    return player
        return None

    def find_by_name(self, name: str, *, grade: int | None = None) -> list[Player]:
        name = name.strip()
        results: list[Player] = []
        for player in self.store.load_all():
            if grade is not None and player.grade != grade:
                continue
            if player.name == name or name in player.aliases:
                results.append(player)
        return results

    def create_player(self, data: PlayerCreate, *, today: date | None = None) -> Player:
        today = today or date.today()
        players = self.store.load_all()
        player_id = data.id or self.store.next_id(players)
        if any(player.id == player_id for player in players):
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
        self._validate_unique_constraints(player, players)
        players.append(player)
        self.store.save_all(players, today=today)
        return player.with_derived_fields(today=today)

    def update_player(
        self,
        player_id: str,
        data: PlayerUpdate,
        *,
        today: date | None = None,
    ) -> Player:
        today = today or date.today()
        players = self.store.load_all()
        index = self._index_of(players, player_id)
        current = players[index]

        updated = current.model_copy(
            update={key: value for key, value in data.model_dump(exclude_unset=True).items()}
        )
        others = players[:index] + players[index + 1 :]
        self._validate_unique_constraints(updated, others)
        players[index] = updated
        self.store.save_all(players, today=today)
        return updated.with_derived_fields(today=today)

    def delete_player(self, player_id: str, *, today: date | None = None) -> Player:
        today = today or date.today()
        players = self.store.load_all()
        index = self._index_of(players, player_id)
        removed = players.pop(index)
        self.store.save_all(players, today=today)
        return removed

    def mark_left(self, player_id: str, *, today: date | None = None) -> Player:
        return self.update_player(
            player_id,
            PlayerUpdate(status=PlayerStatus.left),
            today=today,
        )

    def _index_of(self, players: list[Player], player_id: str) -> int:
        for index, player in enumerate(players):
            if player.id == player_id:
                return index
        raise PlayerNotFoundError(player_id)

    def _validate_unique_constraints(self, player: Player, others: list[Player]) -> None:
        if player.handle:
            for other in others:
                if other.handle and other.handle == player.handle:
                    raise PlayerValidationError(f"校内 handle 已存在: {player.handle}")

        for account in player.oj_accounts:
            for other in others:
                for other_account in other.oj_accounts:
                    if (
                        account.platform == other_account.platform
                        and account.handle == other_account.handle
                    ):
                        raise PlayerValidationError(
                            f"OJ 账号已绑定其他选手: {account.platform}/{account.handle}"
                        )

        for other in others:
            if other.id == player.id:
                raise PlayerAlreadyExistsError(player.id)
