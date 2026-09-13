"""Web 层测试基建：临时 web DB + 内存 core DB + reflex 状态链构造。

reflex 0.9.7 机制要点（均经实测）：
- State 不允许直接实例化；测试须传 ``_reflex_internal_init=True``。
- 继承 var 的读写委托给 ``parent_state`` → 状态链必须完整构造
  （LocalAuthState → AuthState → 目标 State）。
- 手工拼的链不在 root 的 substate 树里，``_mark_dirty`` 的 dirty 传播会
  因路径解析失败而炸 → autouse fixture 将其 no-op。它只影响前端 delta
  序列化，不影响被测业务逻辑与 computed var 求值（缓存失效只看 interval，
  不依赖 dirty_vars）。
- 登录态 = 往 web DB 插 ``LocalAuthSession`` + 把 ``auth_token`` 设到链根。
- 事件处理器经实例访问即为绑定好的 callable（state.py:1455 的 partial），
  直接 ``state.some_handler()`` 等于执行函数体（绕过 Socket.IO）。
- web DB 用 ``tmp_path`` 临时文件 + monkeypatch ``rxconfig.config.db_url``
  （``rx.session()`` 经 ``get_config()`` 读到同一单例，已断言验证）。
- core DB 经 ``player_api.configure_store`` 注入内存库，真实数据零接触。
"""

from __future__ import annotations

import itertools
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# xcpc_web/ 目录上 sys.path：`import rxconfig` 与 `import xcpc_web.<pkg>` 可用
_WEB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WEB_DIR))

import rxconfig  # noqa: E402

from reflex.model import ModelRegistry  # noqa: E402
from reflex.state import BaseState  # noqa: E402
from reflex_local_auth import LocalUser  # noqa: E402
from reflex_local_auth.auth_session import LocalAuthSession  # noqa: E402
from reflex_local_auth.local_auth import LocalAuthState  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session  # noqa: E402

from xcpc_core.db import tables as _core_tables  # noqa: E402, F401  注册 core 全部表
from xcpc_core.db.base import Base  # noqa: E402
from xcpc_core.player import api as player_api  # noqa: E402
from xcpc_core.player.store import PlayerStore  # noqa: E402
from xcpc_core.contest import api as contest_api  # noqa: E402
from xcpc_core.contest.store import ContestStore  # noqa: E402
from xcpc_core.team import api as team_api  # noqa: E402
from xcpc_core.team.store import TeamStore  # noqa: E402
from xcpc_core.audit import api as audit_api  # noqa: E402
from xcpc_core.board import api as board_api  # noqa: E402
from xcpc_core.importer import api as importer_api  # noqa: E402
from xcpc_core.rating import api as rating_api  # noqa: E402

from xcpc_web.states.auth import AuthState  # noqa: E402
from xcpc_web.states.auth_models import BindingRequest, UserProfile  # noqa: E402, F401


@pytest.fixture(autouse=True)
def _no_dirty_marking(monkeypatch):
    """no-op 掉 _mark_dirty（手工状态链不在 substate 树中，dirty 传播会炸）。"""
    monkeypatch.setattr(BaseState, "_mark_dirty", lambda self: None)


@pytest.fixture
def web_engine(tmp_path, monkeypatch):
    """每测试一个全新临时 web DB，并把 reflex 的 db_url 指过去。"""
    url = f"sqlite:///{tmp_path / 'web.db'}"
    monkeypatch.setattr(rxconfig.config, "db_url", url)
    engine = create_engine(url)
    ModelRegistry.get_metadata().create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def core_store():
    """内存 core DB（选手/队伍等表），注入 player_api；与真实 xcpc.db 完全隔离。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    player_api.configure_store(PlayerStore(session))
    team_api.configure_store(TeamStore(session))
    contest_api.configure_store(ContestStore(session))
    audit_api.configure_session(session)
    importer_api.configure_session(session)
    rating_api.configure_session(session)
    board_api.configure_session(session)
    yield session
    # 恢复默认（None → get_service 回落到真实库的默认 factory）
    player_api.configure_store(None)  # type: ignore[arg-type]
    team_api.configure_store(None)  # type: ignore[arg-type]
    contest_api.configure_store(None)  # type: ignore[arg-type]
    audit_api.configure_session(None)  # type: ignore[arg-type]
    importer_api.configure_session(None)
    rating_api.configure_session(None)
    board_api.configure_session(None)
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def make_user(web_engine):
    """在临时 web DB 创建 LocalUser + UserProfile。返回 (user_id, username)。"""

    def _make(
        username: str,
        *,
        role: str = "member",
        bound_player_id: str | None = None,
    ) -> tuple[int, str]:
        with Session(web_engine) as s:
            user = LocalUser(
                username=username,
                password_hash=LocalUser.hash_password("pw"),
                enabled=True,
            )
            s.add(user)
            s.flush()
            s.refresh(user)
            s.add(
                UserProfile(
                    user_id=user.id, role=role, bound_player_id=bound_player_id
                )
            )
            s.commit()
            return user.id, username

    return _make


@pytest.fixture
def build_state(web_engine):
    """构造完整状态链（LocalAuthState→AuthState→state_cls）。

    传入 ``user``（make_user 的返回值）则同时种登录会话，使
    ``is_authenticated`` 等 var 链按真实登录态求值。
    """

    counter = itertools.count(1)

    def _build(state_cls, user: tuple[int, str] | None = None):
        root = LocalAuthState(_reflex_internal_init=True, init_substates=False)
        auth = AuthState(
            parent_state=root, init_substates=False, _reflex_internal_init=True
        )
        state = (
            auth
            if state_cls is AuthState
            else state_cls(
                parent_state=auth, init_substates=False, _reflex_internal_init=True
            )
        )
        if user is not None:
            user_id, username = user
            # LocalAuthSession.session_id 有 UNIQUE 约束；同测试内多次登录同一
            # 用户（重建链）需不同 token
            token = f"tok_{username}_{next(counter)}"
            with Session(web_engine) as s:
                s.add(
                    LocalAuthSession(
                        user_id=user_id,
                        session_id=token,
                        expiration=datetime.now(timezone.utc) + timedelta(days=1),
                    )
                )
                s.commit()
            root.auth_token = token
        return state

    return _build
