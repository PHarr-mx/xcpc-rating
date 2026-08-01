from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from xcpc_core.db.base import Base
from xcpc_core.db import tables  # noqa: F401  注册全部表


@pytest.fixture
def db_session():
    """内存 SQLite（StaticPool 共享同一连接），每测试重建。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
