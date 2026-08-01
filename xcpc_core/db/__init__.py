"""数据库基础设施：Base、表定义、session。

说明：core 的表用纯 SQLAlchemy 2.0 定义（不依赖 reflex）。
reflex 0.9.2 起弃用 ``rx.Model``（0.9.7 上 ``table=True`` 子类化已损坏），官方建议直接使用
SQLAlchemy / SQLModel。见 docs/10-数据存储与SQLite.md §3。
"""

from xcpc_core.db.base import Base
from xcpc_core.db import tables as _tables  # noqa: F401  确保表注册进 Base.metadata

__all__ = ["Base"]
