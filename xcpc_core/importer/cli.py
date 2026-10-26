"""通用比赛 JSON 导入 CLI。

用法（项目根目录）::

    python -m xcpc_core.importer.cli template --entity team  > /tmp/t.json
    python -m xcpc_core.importer.cli import /tmp/t.json
    python -m xcpc_core.importer.cli import /tmp/t.json --no-auto-create --dry-run

``--dry-run`` 只校验模板与姓名匹配，不写库、不归档。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from xcpc_core.importer.contest_json import import_contest_json
from xcpc_core.importer.models import ContestJsonDocument
from xcpc_core.utils.plog import Plog

TEMPLATES: dict[str, dict[str, Any]] = {
    "team": {
        "contest_id": "2026_training_01",
        "title": "2026 秋 训练赛 01",
        "date": "2026-10-05",
        "format": "icpc",
        "entity": "team",
        "tier": "全体队员组",
        "n_teams": 12,
        "scoring": "formula",
        "counts_for_points": True,
        "counts_for_ranking": True,
        "allow_claims": True,
        "max_value": 8,
        "standings": [
            {"team_name": "队名A", "members": ["张三", "李四", "王五"], "rank": 1, "solved": 8, "penalty": 620},
            {"team_name": "队名B", "members": ["赵六", "钱七"], "rank": 2, "solved": 7, "penalty": 700},
        ],
    },
    "player": {
        "contest_id": "2026_solo_01",
        "title": "2026 秋 个人赛 01",
        "date": "2026-10-06",
        "format": "icpc",
        "entity": "player",
        "tier": "未入队新生组",
        "counts_for_points": True,
        "counts_for_ranking": True,
        "max_value": 6,
        "standings": [
            {"members": ["张三"], "rank": 1, "solved": 6, "penalty": 300},
            {"members": ["李四"], "rank": 2, "solved": 5, "penalty": 350},
        ],
    },
    "ioi": {
        "contest_id": "2026_ioi_01",
        "title": "2026 IOI 制训练",
        "date": "2026-10-07",
        "format": "ioi",
        "entity": "player",
        "tier": "全体队员组",
        "counts_for_points": False,
        "counts_for_ranking": True,
        "standings": [
            {"members": ["张三"], "rank": 1, "score": 300},
            {"members": ["李四"], "rank": 2, "score": 245},
        ],
    },
}


def _cmd_template(args: argparse.Namespace) -> int:
    print(json.dumps(TEMPLATES[args.entity], ensure_ascii=False, indent=2))
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    path = Path(args.path)
    document = json.loads(path.read_text(encoding="utf-8"))
    parsed = ContestJsonDocument.model_validate(document)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "contest_id": parsed.contest_id,
                    "title": parsed.title,
                    "format": parsed.format,
                    "entity": parsed.entity,
                    "rows": len(parsed.standings),
                    "counts_for_points": parsed.counts_for_points,
                    "counts_for_ranking": parsed.counts_for_ranking,
                    "max_value": parsed.max_value,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    plog = Plog(name="xcpc-import-json")
    try:
        result = import_contest_json(
            parsed,
            auto_create_players=not args.no_auto_create,
            default_grade=args.default_grade,
            plog=plog,
        )
    finally:
        plog.close()

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if result.unmatched_players or result.unmatched_teams:
        print(
            f"\n⚠️  {len(result.unmatched_players)} 名选手 / {len(result.unmatched_teams)} 行未导入",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xcpc-core.importer", description="通用比赛 JSON 导入")
    sub = parser.add_subparsers(dest="command", required=True)

    p_template = sub.add_parser("template", help="打印可填写的模板")
    p_template.add_argument("--entity", choices=sorted(TEMPLATES), default="team")
    p_template.set_defaults(func=_cmd_template)

    p_import = sub.add_parser("import", help="导入一份模板 JSON")
    p_import.add_argument("path")
    p_import.add_argument("--no-auto-create", action="store_true", help="不自动建档未匹配选手")
    p_import.add_argument("--default-grade", type=int, default=None, help="自动建档的入学年")
    p_import.add_argument("--dry-run", action="store_true", help="只校验，不写库不归档")
    p_import.set_defaults(func=_cmd_import)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())