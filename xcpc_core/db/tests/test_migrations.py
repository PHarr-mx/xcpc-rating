"""alembic 迁移守护测试：fresh upgrade / 模型-迁移漂移 / 存量库 stamp 幂等。

漂移测试是这套体系能「活」的关键：谁改了 tables.py 不写迁移，这里直接红。
"""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text

from xcpc_core.db import tables
from xcpc_core.db.base import Base
from xcpc_core.db.migrations import run_migrations
from xcpc_core.db.session import create_db_engine, make_session_factory


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'xcpc.db'}"


def _head_revision(engine) -> str | None:
    with engine.connect() as conn:
        if "alembic_version" not in inspect(conn).get_table_names():
            return None
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def test_migrations_reject_memory_db():
    with pytest.raises(ValueError, match="create_all"):
        run_migrations(url="sqlite://")


def test_upgrade_head_on_fresh_db(db_url):
    run_migrations(url=db_url)

    engine, factory = make_session_factory(url=db_url)
    try:
        names = set(inspect(engine).get_table_names())
        expected = {t.name for t in Base.metadata.sorted_tables}
        assert expected <= names
        assert _head_revision(engine) == "0001_baseline"

        with factory() as session:
            session.add(tables.Player(id="p001", name="张三"))
            session.add(tables.Meta(id=1, data_version=0))
            session.commit()
            assert session.get(tables.Player, "p001").name == "张三"
    finally:
        engine.dispose()

    run_migrations(url=db_url)  # 已在 head：no-op，不报错
    engine = create_db_engine(url=db_url)
    try:
        assert _head_revision(engine) == "0001_baseline"
    finally:
        engine.dispose()


def test_models_match_migrations_no_drift(db_url):
    """metadata 与「迁移建出来的库」零差异；改 tables.py 不写迁移会让本测试失败。"""
    run_migrations(url=db_url)

    engine = create_db_engine(url=db_url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn, opts={"render_as_batch": True})
            diffs = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diffs == [], f"tables.py 与迁移脚本出现漂移: {diffs}"


def test_legacy_db_stamped_and_idempotent(db_url):
    """alembic 引入前的存量库（create_all 直建）：只补版本号，不动 DDL 不丢数据。"""
    engine, factory = make_session_factory(url=db_url)
    try:
        Base.metadata.create_all(engine)
        with factory() as session:
            session.add(tables.Player(id="p001", name="存量库选手"))
            session.commit()
    finally:
        engine.dispose()

    run_migrations(url=db_url)
    run_migrations(url=db_url)  # 重跑幂等

    engine = create_db_engine(url=db_url)
    try:
        assert _head_revision(engine) == "0001_baseline"
        names = set(inspect(engine).get_table_names())
        assert names >= {"player", "meta", "alembic_version"}
    finally:
        engine.dispose()

    engine, factory = make_session_factory(url=db_url)
    try:
        with factory() as session:
            assert session.get(tables.Player, "p001").name == "存量库选手"
    finally:
        engine.dispose()
