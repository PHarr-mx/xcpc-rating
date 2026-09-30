"""tier 命令行：赛事等级与奖项基线的查看与维护。

用法（项目根目录）::

    python -m xcpc_core.tier.cli list
    python -m xcpc_core.tier.cli create --name "ICPC 省赛" --coefficient 0.7
    python -m xcpc_core.tier.cli update 1 --coefficient 0.8
    python -m xcpc_core.tier.cli delete 1
    python -m xcpc_core.tier.cli award list
    python -m xcpc_core.tier.cli award create --name gold --base-points 100
"""

from __future__ import annotations

import argparse

from xcpc_core.tier import api as tier_api
from xcpc_core.tier.exceptions import TierError
from xcpc_core.tier.models import AwardLevelCreate, AwardLevelUpdate, TierCreate, TierUpdate
from xcpc_core.utils.plog import Plog


def _print_tiers() -> None:
    rows = tier_api.list_tiers()
    if not rows:
        print("（暂无赛事等级）")
        return
    print(f"{'ID':>4}  {'名称':<20} {'系数':>6}  排序  关联比赛数")
    for tier in rows:
        print(f"{tier.id:>4}  {tier.name:<20} {tier.coefficient:>6.2f}  {tier.sort_order:>4}")


def _print_awards() -> None:
    rows = tier_api.list_award_levels()
    if not rows:
        print("（暂无奖项等级）")
        return
    print(f"{'ID':>4}  {'名称':<12} {'基线分':>8}  排序")
    for level in rows:
        print(f"{level.id:>4}  {level.name:<12} {level.base_points:>8.1f}  {level.sort_order:>4}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m xcpc_core.tier.cli", description="赛事等级管理")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="列出赛事等级")
    sub.add_parser("awards", help="列出奖项等级")

    create = sub.add_parser("create", help="新建赛事等级")
    create.add_argument("--name", required=True)
    create.add_argument("--coefficient", type=float, required=True)
    create.add_argument("--sort-order", type=int, default=0)

    update = sub.add_parser("update", help="更新赛事等级")
    update.add_argument("tier_id", type=int)
    update.add_argument("--name")
    update.add_argument("--coefficient", type=float)
    update.add_argument("--sort-order", type=int)

    delete = sub.add_parser("delete", help="删除赛事等级")
    delete.add_argument("tier_id", type=int)

    award = sub.add_parser("award", help="奖项等级操作")
    award_sub = award.add_subparsers(dest="award_command", required=True)
    award_sub.add_parser("list")
    award_create = award_sub.add_parser("create")
    award_create.add_argument("--name", required=True)
    award_create.add_argument("--base-points", type=float, required=True)
    award_create.add_argument("--sort-order", type=int, default=0)
    award_update = award_sub.add_parser("update")
    award_update.add_argument("level_id", type=int)
    award_update.add_argument("--name")
    award_update.add_argument("--base-points", type=float)
    award_update.add_argument("--sort-order", type=int)
    award_delete = award_sub.add_parser("delete")
    award_delete.add_argument("level_id", type=int)

    args = parser.parse_args(argv)
    plog = Plog(name="xcpc-tier")
    try:
        if args.command == "list":
            _print_tiers()
        elif args.command == "awards":
            _print_awards()
        elif args.command == "create":
            tier = tier_api.create_tier(TierCreate(
                name=args.name, coefficient=args.coefficient, sort_order=args.sort_order
            ))
            print(f"已创建赛事等级: {tier.name} (id={tier.id}, 系数 {tier.coefficient})")
        elif args.command == "update":
            tier = tier_api.update_tier(args.tier_id, TierUpdate(
                name=args.name, coefficient=args.coefficient, sort_order=args.sort_order
            ))
            print(f"已更新赛事等级: {tier.name} (id={tier.id}, 系数 {tier.coefficient})")
        elif args.command == "delete":
            tier_api.delete_tier(args.tier_id)
            print(f"已删除赛事等级: id={args.tier_id}")
        elif args.command == "award":
            if args.award_command == "list":
                _print_awards()
            elif args.award_command == "create":
                level = tier_api.create_award_level(AwardLevelCreate(
                    name=args.name, base_points=args.base_points, sort_order=args.sort_order
                ))
                print(f"已创建奖项等级: {level.name} (id={level.id}, 基线 {level.base_points})")
            elif args.award_command == "update":
                level = tier_api.update_award_level(args.level_id, AwardLevelUpdate(
                    name=args.name, base_points=args.base_points, sort_order=args.sort_order
                ))
                print(f"已更新奖项等级: {level.name} (id={level.id}, 基线 {level.base_points})")
            elif args.award_command == "delete":
                tier_api.delete_award_level(args.level_id)
                print(f"已删除奖项等级: id={args.level_id}")
    except TierError as exc:
        print(f"错误: {exc}")
        return 1
    finally:
        plog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
