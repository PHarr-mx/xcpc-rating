from __future__ import annotations

from datetime import date

from importer.config import load_default_player_grade
from importer.models import CreatedPlayer, UnmatchedPlayer
from player import create_player, find_by_name
from player.models import PlayerCreate, PlayerStatus
from player.store import PlayerStore
from utils.plog import Plog


def resolve_member_names(
    *,
    contest_id: str,
    team_name: str,
    rank: int,
    member_names: list[str],
    store: PlayerStore,
    auto_create: bool,
    default_grade: int,
    today: date,
    plog: Plog | None = None,
) -> tuple[list[str] | None, list[UnmatchedPlayer], list[CreatedPlayer]]:
    player_ids: list[str] = []
    unmatched: list[UnmatchedPlayer] = []
    created: list[CreatedPlayer] = []

    for name in member_names:
        matches = find_by_name(name, store=store)
        if len(matches) == 1:
            player_ids.append(matches[0].id)
            continue
        if len(matches) > 1:
            unmatched.append(
                UnmatchedPlayer(
                    contest_id=contest_id,
                    name=name,
                    team_name=team_name,
                    rank=rank,
                )
            )
            continue

        if not auto_create:
            unmatched.append(
                UnmatchedPlayer(
                    contest_id=contest_id,
                    name=name,
                    team_name=team_name,
                    rank=rank,
                )
            )
            continue

        player = create_player(
            PlayerCreate(name=name, grade=default_grade, status=PlayerStatus.active),
            today=today,
            store=store,
        )
        created.append(
            CreatedPlayer(
                player_id=player.id,
                name=player.name,
                team_name=team_name,
                contest_id=contest_id,
            )
        )
        player_ids.append(player.id)
        if plog:
            plog.info("自动建档选手", name=name, player_id=player.id, grade=default_grade)

    if unmatched:
        return None, unmatched, created
    return player_ids, [], created


def resolve_default_grade(params, *, repo_root) -> int:
    return load_default_player_grade(repo_root=repo_root, override=params.default_grade)
