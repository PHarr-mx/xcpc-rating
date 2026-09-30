"""Alembic 迁移包：本目录即 alembic ``script_location``，同时暴露程序化入口。

- :func:`run_migrations` 是运行时唯一的 schema 建立/升级入口（``db.migrate`` 调用）。
  自愈规则：库里已有业务表但无 ``alembic_version``（alembic 引入前的存量库）
  → ``stamp head`` 只记版本、不动 DDL；全新库或已在版本管理中的库 → ``upgrade head``。
- 手工生成迁移见 :mod:`revision`（``uv run python -m xcpc_core.db.migrations.revision``）。
- 测试内存库（``sqlite://``）不走本入口：alembic 自开连接，建完即丢，请直接
  ``Base.metadata.create_all``（与 schema 一致性由漂移守护测试保证）。
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from xcpc_core.db.session import create_db_engine, default_db_url

#: 存量库判定用的标志表：存在即认为 schema 已由 create_all 建立
_MARK_TABLE = "meta"


def make_alembic_config(url: str | None = None) -> Config:
    """构建程序化 alembic 配置（无 ini 文件，cwd 无关）。"""
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent))
    cfg.set_main_option("sqlalchemy.url", url or default_db_url())
    return cfg


def _table_names(url: str) -> set[str]:
    engine = create_db_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def run_migrations(url: str | None = None) -> None:
    """把 schema 升到 head：全新库建全部表，存量库自动 stamp，均已幂等。

    仅支持文件库；内存库请走 ``Base.metadata.create_all``（模块 docstring）。
    """
    resolved = url or default_db_url()
    if ":memory:" in resolved or resolved == "sqlite://":
        raise ValueError("run_migrations 不支持内存库：测试请直接 Base.metadata.create_all")
    cfg = make_alembic_config(resolved)
    existing = _table_names(resolved)
    if _MARK_TABLE in existing and "alembic_version" not in existing:
        # alembic 引入前的存量库：表已在，补记版本号即可，不重放 DDL
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")
