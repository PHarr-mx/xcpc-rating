from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING, Callable

from team import api
from team.exceptions import TeamError
from team.models import TeamCreate, TeamUpdate
from utils import Plog

if TYPE_CHECKING:
    from argparse import Namespace


def _print_teams(teams: list, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps([team.model_dump(mode="json") for team in teams], ensure_ascii=False, indent=2))
        return
    if not teams:
        print("(无)")
        return
    for team in teams:
        members_str = ", ".join(team.members)
        aliases_str = " | ".join(team.aliases) if team.aliases else "(无别名)"
        print(f"{team.id}\t{aliases_str}\t[{members_str}]\t{team.size}人")


def cmd_list(args: Namespace, plog: Plog) -> int:
    plog.info("列出队伍")
    teams = api.list_teams()
    plog.info("查询完成", count=len(teams))
    _print_teams(teams, as_json=args.json)
    return 0


def cmd_get(args: Namespace, plog: Plog) -> int:
    plog.info("查询队伍", team_id=args.team_id)
    team = api.get_team(args.team_id)
    print(json.dumps(team.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def cmd_find(args: Namespace, plog: Plog) -> int:
    plog.info("按队员查找", members=args.members)
    team = api.find_by_members(args.members)
    if team:
        plog.info("查找完成", team_id=team.id, aliases=team.aliases)
        _print_teams([team], as_json=args.json)
    else:
        plog.info("未找到匹配队伍")
        _print_teams([], as_json=args.json)
    return 0


def cmd_create(args: Namespace, plog: Plog) -> int:
    plog.info("新建队伍", members=args.members, aliases=args.aliases)
    team = api.create_team(
        TeamCreate(
            members=args.members,
            aliases=args.aliases,
        )
    )
    plog.info("队伍已创建", team_id=team.id, aliases=team.aliases)
    if args.json:
        print(json.dumps(team.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        aliases_str = " | ".join(team.aliases)
        print(f"已创建: {team.id} {aliases_str}")
    return 0


def cmd_update(args: Namespace, plog: Plog) -> int:
    plog.info("更新队伍", team_id=args.team_id)
    team = api.update_team(args.team_id, TeamUpdate(alias=args.alias))
    plog.info("队伍已更新", team_id=team.id, aliases=team.aliases)
    if args.json:
        print(json.dumps(team.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        aliases_str = " | ".join(team.aliases)
        print(f"已更新: {team.id} {aliases_str}")
    return 0


def cmd_delete(args: Namespace, plog: Plog) -> int:
    plog.info("删除队伍", team_id=args.team_id)
    team = api.delete_team(args.team_id)
    plog.info("队伍已删除", team_id=team.id, aliases=team.aliases)
    if args.json:
        print(json.dumps(team.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        aliases_str = " | ".join(team.aliases)
        print(f"已删除: {team.id} {aliases_str}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xcpc-team", description="队伍增删改查")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出队伍")

    get_parser = subparsers.add_parser("get", help="查询单个队伍")
    get_parser.add_argument("team_id")

    find_parser = subparsers.add_parser("find", help="按队员查找队伍")
    find_parser.add_argument("--members", nargs="+", required=True, metavar="PLAYER_ID")

    create_parser = subparsers.add_parser("create", help="新建队伍")
    create_parser.add_argument("--members", nargs="+", required=True, metavar="PLAYER_ID")
    create_parser.add_argument("--aliases", nargs="+", metavar="ALIAS", help="队伍别名")

    update_parser = subparsers.add_parser("update", help="更新队伍")
    update_parser.add_argument("team_id")
    update_parser.add_argument("--alias", required=True, help="追加别名")

    delete_parser = subparsers.add_parser("delete", help="从名册删除队伍")
    delete_parser.add_argument("team_id")

    return parser


_COMMANDS: dict[str, Callable[[Namespace, Plog], int]] = {
    "list": cmd_list,
    "get": cmd_get,
    "find": cmd_find,
    "create": cmd_create,
    "update": cmd_update,
    "delete": cmd_delete,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    plog = Plog(name="xcpc-team")
    plog.info("命令开始", command=args.command)

    try:
        handler = _COMMANDS[args.command]
        return handler(args, plog)
    except TeamError as exc:
        plog.error(str(exc))
        return 1
    except json.JSONDecodeError as exc:
        plog.error("JSON 解析失败", detail=str(exc))
        return 1
    finally:
        plog.close()


if __name__ == "__main__":
    raise SystemExit(main())