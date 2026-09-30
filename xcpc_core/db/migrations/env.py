"""Alembic 环境：业务库 xcpc.db 的 schema 迁移入口。

- URL 由调用方经 ``Config.set_main_option`` 注入（见 ``run_migrations``）；
  命令行直跑时缺省回落到 ``default_db_url()``。
- ``render_as_batch=True``：SQLite 的 ALTER 受限，后续加列/改列一律走 batch。
- 引擎经 ``create_db_engine`` 创建，逐连接 PRAGMA（WAL / busy_timeout / foreign_keys）
  与运行时保持一致。
"""

from __future__ import annotations

from alembic import context

from xcpc_core.db import tables  # noqa: F401  注册全部表到 metadata
from xcpc_core.db.base import Base
from xcpc_core.db.session import create_db_engine, default_db_url

config = context.config

if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", default_db_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_db_engine(config.get_main_option("sqlalchemy.url"))
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
