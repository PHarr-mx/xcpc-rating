"""meta 单行表的写侧助手。

``meta.data_version`` 是榜单进程内缓存的失效钥匙（读侧见 ``xcpc_core/board/api.py``）：
写路径在业务写提交前调用 :func:`bump_data_version`，提交后缓存 key 随版本号变化
自然失效。放 db 层而非 board 层，是为保持 board「只读聚合」的模块边界——
player / contest service 直接依赖 db，与 board 无导入关系。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from xcpc_core.db.tables import Meta as MetaRow


def bump_data_version(session: Session) -> int:
    """当前事务内把 ``meta.data_version`` 加一（无行则建行），返回新版本号。

    只修改并 flush、不提交——调用方（service 写方法）随业务写一起 commit，
    保证「数据变更 + 版本推进」原子生效；事务回滚时版本推进一并回滚。
    """
    now = datetime.now(timezone.utc)
    row = session.get(MetaRow, 1)
    if row is None:
        session.add(MetaRow(id=1, data_version=1, updated_at=now))
        version = 1
    else:
        row.data_version += 1
        row.updated_at = now
        version = row.data_version
    session.flush()
    return version
