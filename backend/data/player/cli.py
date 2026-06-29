from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING, Callable

from player import api
from player.exceptions import PlayerError
from player.models import OJAccount, PlayerCreate, PlayerStatus, PlayerUpdate
from utils import Plog

if TYPE_CHECKING:
    from argparse import Namespace


def _parse_oj_accounts(raw: str | None) -> list[OJAccount]:
    if not raw:
        return []
    items = json.loads(raw)
    return [OJAccount.model_validate(item) for item in items]


def _print_players(players: list, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps([player.model_dump(mode="json") for player in players], ensure_ascii=False, indent=2))
        return
    if not players:
        print("(无)")
        return
    for player in players:
        handle = player.handle or "-"
        print(f"{player.id}\t{player.name}\t{handle}\t{player.grade}\t{player.status.value}")


def cmd_list(args: Namespace, plog: Plog) -> int:
    plog.info("列出选手", visible_only=args.visible_only, status=args.status, grade=args.grade)
    players = api.list_players(
        include_left=not args.visible_only,
        status=PlayerStatus(args.status) if args.status else None,
        grade=args.grade,
    )
    plog.info("查询完成", count=len(players))
    _print_players(players, as_json=args.json)
    return 0


def cmd_get(args: Namespace, plog: Plog) -> int:
    plog.info("查询选手", player_id=args.player_id)
    player = api.get_player(args.player_id)
    print(json.dumps(player.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def cmd_find(args: Namespace, plog: Plog) -> int:
    if args.name:
        plog.info("按姓名查找", name=args.name, grade=args.grade)
        players = api.find_by_name(args.name, grade=args.grade)
    else:
        platform, handle = args.oj
        plog.info("按 OJ 账号查找", platform=platform, handle=handle)
        player = api.find_by_oj(platform, handle)
        players = [player] if player else []
    plog.info("查找完成", count=len(players))
    _print_players(players, as_json=args.json)
    return 0


def cmd_create(args: Namespace, plog: Plog) -> int:
    plog.info("新建选手", name=args.name, grade=args.grade, player_id=args.id)
    player = api.create_player(
        PlayerCreate(
            id=args.id,
            name=args.name,
            handle=args.handle,
            grade=args.grade,
            status=PlayerStatus(args.status),
            aliases=args.aliases or [],
            oj_accounts=_parse_oj_accounts(args.oj_accounts),
        )
    )
    plog.info("选手已创建", player_id=player.id, name=player.name)
    if args.json:
        print(json.dumps(player.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(f"已创建: {player.id} {player.name}")
    return 0


def cmd_update(args: Namespace, plog: Plog) -> int:
    plog.info("更新选手", player_id=args.player_id)
    payload: dict = {}
    if args.name is not None:
        payload["name"] = args.name
    if args.handle is not None:
        payload["handle"] = args.handle
    if args.grade is not None:
        payload["grade"] = args.grade
    if args.status is not None:
        payload["status"] = PlayerStatus(args.status)
    if args.aliases is not None:
        payload["aliases"] = args.aliases
    if args.oj_accounts is not None:
        payload["oj_accounts"] = _parse_oj_accounts(args.oj_accounts)
    player = api.update_player(args.player_id, PlayerUpdate(**payload))
    plog.info("选手已更新", player_id=player.id, name=player.name)
    if args.json:
        print(json.dumps(player.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(f"已更新: {player.id} {player.name}")
    return 0


def cmd_delete(args: Namespace, plog: Plog) -> int:
    plog.info("删除选手", player_id=args.player_id)
    player = api.delete_player(args.player_id)
    plog.info("选手已删除", player_id=player.id, name=player.name)
    if args.json:
        print(json.dumps(player.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(f"已删除: {player.id} {player.name}")
    return 0


def cmd_mark_left(args: Namespace, plog: Plog) -> int:
    plog.info("标记离队", player_id=args.player_id)
    player = api.mark_left(args.player_id)
    plog.info("选手已标记离队", player_id=player.id, name=player.name)
    if args.json:
        print(json.dumps(player.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(f"已标记离队: {player.id} {player.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xcpc-player", description="选手增删改查")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出选手")
    list_parser.add_argument("--visible-only", action="store_true", help="排除离队选手")
    list_parser.add_argument("--status", choices=[item.value for item in PlayerStatus])
    list_parser.add_argument("--grade", type=int)

    get_parser = subparsers.add_parser("get", help="查询单个选手")
    get_parser.add_argument("player_id")

    find_parser = subparsers.add_parser("find", help="按姓名或 OJ 账号查找")
    find_group = find_parser.add_mutually_exclusive_group(required=True)
    find_group.add_argument("--name")
    find_group.add_argument("--oj", nargs=2, metavar=("PLATFORM", "HANDLE"))
    find_parser.add_argument("--grade", type=int)

    create_parser = subparsers.add_parser("create", help="新建选手")
    create_parser.add_argument("--id")
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--handle")
    create_parser.add_argument("--grade", type=int, required=True)
    create_parser.add_argument("--status", choices=[item.value for item in PlayerStatus], default="active")
    create_parser.add_argument("--aliases", nargs="*")
    create_parser.add_argument("--oj-accounts", help='JSON 数组，如 \'[{"platform":"codeforces","handle":"abc"}]\'')

    update_parser = subparsers.add_parser("update", help="更新选手")
    update_parser.add_argument("player_id")
    update_parser.add_argument("--name")
    update_parser.add_argument("--handle")
    update_parser.add_argument("--grade", type=int)
    update_parser.add_argument("--status", choices=[item.value for item in PlayerStatus])
    update_parser.add_argument("--aliases", nargs="*")
    update_parser.add_argument("--oj-accounts", help="JSON 数组，传入则整体替换")

    delete_parser = subparsers.add_parser("delete", help="从名册删除选手")
    delete_parser.add_argument("player_id")

    mark_left_parser = subparsers.add_parser("mark-left", help="将选手标记为离队（软删除）")
    mark_left_parser.add_argument("player_id")

    return parser


_COMMANDS: dict[str, Callable[[Namespace, Plog], int]] = {
    "list": cmd_list,
    "get": cmd_get,
    "find": cmd_find,
    "create": cmd_create,
    "update": cmd_update,
    "delete": cmd_delete,
    "mark-left": cmd_mark_left,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    plog = Plog(name="xcpc-player")
    plog.info("命令开始", command=args.command)

    try:
        handler = _COMMANDS[args.command]
        return handler(args, plog)
    except PlayerError as exc:
        plog.error(str(exc))
        return 1
    except json.JSONDecodeError as exc:
        plog.error("JSON 解析失败", detail=str(exc))
        return 1
    finally:
        plog.close()


if __name__ == "__main__":
    raise SystemExit(main())
