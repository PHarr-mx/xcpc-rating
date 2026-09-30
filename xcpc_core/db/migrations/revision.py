"""生成 schema 迁移脚本（开发用）。

用法：

    uv run python -m xcpc_core.db.migrations.revision -m "add foo column"

前提：默认业务库（``default_db_url()``）已 upgrade 到 head——autogenerate 拿
``tables.py`` 的 metadata 与「head 状态的真实库」做 diff。**生成后必须人工核对
脚本内容再提交**（autogenerate 对 server_default / 约束还原不完美）。
"""

from __future__ import annotations

import argparse

from alembic import command

from xcpc_core.db.migrations import make_alembic_config


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="autogenerate 一份 alembic 迁移脚本")
    parser.add_argument("-m", "--message", required=True, help="迁移说明（写入 docstring）")
    args = parser.parse_args(argv)
    command.revision(make_alembic_config(), message=args.message, autogenerate=True)


if __name__ == "__main__":
    main()
