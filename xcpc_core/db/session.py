"""SQLite 引擎与会话。

并发三件套（docs/10 §7.1，缺一不可）：
1. WAL 模式
2. busy_timeout（撞锁等待而非抛错）
3. 短事务（业务层保证，不在持有写锁时做慢活）

PRAGMA 挂在 ``connect`` 事件上**逐连接执行** —— 连接池每条新连接都要设。
``foreign_keys=ON`` 别漏：SQLite 默认不强制外键。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for parent in [current, *current.parents]:
        if (parent / "data" / "raw").is_dir():
            return parent
    raise FileNotFoundError("无法定位仓库根目录（缺少 data/raw）")


def default_db_url(repo_root: Path | None = None) -> str:
    root = repo_root or find_repo_root()
    return f"sqlite:///{root / 'data' / 'db' / 'xcpc.db'}"


def create_db_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """创建 SQLite 引擎并挂载逐连接 PRAGMA。url 缺省为 data/db/xcpc.db。"""
    url = url or default_db_url()
    if url.startswith("sqlite:///") and ":memory:" not in url:
        # 确保数据文件所在目录存在
        Path(url[len("sqlite:///"):]).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 5},
        echo=echo,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def make_session_factory(url: str | None = None, *, echo: bool = False) -> tuple[Engine, sessionmaker]:
    """创建引擎 + session 工厂。测试可传内存库（``sqlite://``）或临时文件路径。"""
    engine = create_db_engine(url, echo=echo)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, factory


def create_all(url: str | None = None, *, echo: bool = False) -> None:
    """（开发用）建全部表。schema 稳定后再引入 alembic 迁移。"""
    from xcpc_core.db.base import Base
    from xcpc_core.db import tables as _tables  # noqa: F401

    engine = create_db_engine(url, echo=echo)
    Base.metadata.create_all(engine)
    return None
