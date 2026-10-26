"""建号与批量建号（五期：不允许自助注册，账号由管理员统一创建）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from reflex_local_auth import RegistrationState
from reflex_local_auth.auth_session import LocalAuthSession
from reflex_local_auth.user import LocalUser
from sqlalchemy import select
from sqlmodel import Session

from xcpc_core.db.tables import AuditLog
from xcpc_core.player import api as player_api

from xcpc_web.states.admin.users import AdminUsersState
from xcpc_web.states.auth_models import UserProfile
from xcpc_web.states.registration import ExtendedRegistrationState


def _chain(user_id: int | None = None, token: str = "reg-tok"):
    """构造 LocalAuthState → RegistrationState → ExtendedRegistrationState 链。

    ``auth_token`` 挂在 **LocalAuthState**（链根）上——LocalAuthState 的
    直接父级是 State，RegistrationState 并不持有该 var。
    """
    from reflex_local_auth.local_auth import LocalAuthState

    root = LocalAuthState(_reflex_internal_init=True, init_substates=False)
    mid = RegistrationState(parent_state=root, init_substates=False, _reflex_internal_init=True)
    ext = ExtendedRegistrationState(
        parent_state=mid, init_substates=False, _reflex_internal_init=True
    )
    if user_id is not None:
        root.auth_token = token
    return ext, mid, root


# ---- 单人建号：权限 ----


def _build_registration_state(user=None):
    """RegistrationState 的 var 链与 AuthState 不同，单独构造。

    ``user`` 为 ``make_user`` 的返回值时，把会话种到链根以形成登录态。
    """
    parent = RegistrationState(_reflex_internal_init=True, init_substates=False)
    reg = ExtendedRegistrationState(
        parent_state=parent, init_substates=False, _reflex_internal_init=True
    )
    if user is not None:
        # 复用 conftest 的登录技巧：token 设到链根
        import itertools


        with Session(user[2]) as s:  # (id, username, engine) 视 make_user 返回而定
            pass
    return reg, parent


def test_anonymous_cannot_register(make_user):
    """未登录调用建号 → 重定向到登录，且不建号。"""
    reg, mid, _root = _chain()
    result = reg.handle_registration(
        {"username": "intruder", "password": "pw123456", "confirm_password": "pw123456"}
    )
    assert result is not None
    assert mid.new_user_id == -1


def test_member_cannot_register(build_state, make_user, web_engine, core_store):
    """普通 member 调用建号 → 被拒。"""
    member = make_user("plain")
    # RegistrationState 不在 build_state 的链上；改用其自身链 + 手动种会话
    with Session(web_engine) as s:
        s.add(LocalAuthSession(
            user_id=member[0],
            session_id="reg-test-member",
            expiration=datetime.now(timezone.utc) + timedelta(days=1),
        ))
        s.commit()

    reg, mid, _root = _chain(member[0], "reg-test-member")
    assert reg.is_admin is False
    reg.handle_registration(
        {"username": "should_fail", "password": "pw123456", "confirm_password": "pw123456"}
    )

    with Session(web_engine) as s:
        found = s.scalars(
            select(LocalUser).where(LocalUser.username == "should_fail")
        ).one_or_none()
    assert found is None, "非管理员不得建号"


def test_admin_can_register_and_audits(build_state, make_user, web_engine, core_store):
    """admin 建号成功，并写 user.create 审计。"""
    admin = make_user("root", role="admin")
    with Session(web_engine) as s:
        s.add(LocalAuthSession(
            user_id=admin[0],
            session_id="reg-test-admin",
            expiration=datetime.now(timezone.utc) + timedelta(days=1),
        ))
        s.commit()

    reg, mid, _root = _chain(admin[0], "reg-test-admin")
    assert reg.is_admin is True
    reg.handle_registration(
        {"username": "newbie", "password": "pw123456", "confirm_password": "pw123456"}
    )

    with Session(web_engine) as s:
        user = s.scalars(select(LocalUser).where(LocalUser.username == "newbie")).one()
        profile = s.scalars(
            select(UserProfile).where(UserProfile.user_id == user.id)
        ).one()
    assert profile.role == "member"

    actions = [r.action for r in core_store.scalars(select(AuditLog)).all()]
    assert "user.create" in actions


# ---- 批量建号 ----


@pytest.fixture
def roster(core_store):
    from xcpc_core.db.tables import Player

    core_store.add_all([
        Player(id="p001", name="张三"),
        Player(id="p002", name="李四"),
    ])
    core_store.commit()
    return core_store


def test_non_admin_cannot_batch(build_state, make_user, web_engine, roster):
    st = build_state(AdminUsersState, make_user("plain"))
    assert st.submit_batch() is not None
    assert st.batch_rows == []


def test_batch_creates_multiple(build_state, make_user, web_engine, roster):
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_default_password("InitPass1")
    st.set_batch_text("alice\nbob\ncarol")
    assert st.submit_batch() is None

    assert "成功 3 个" in st.admin_feedback
    with Session(web_engine) as s:
        names = {u[0] for u in s.exec(select(LocalUser.username)).all()}
    assert {"alice", "bob", "carol"} <= names


def test_batch_per_line_password_and_binding(build_state, make_user, web_engine, roster):
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_default_password("DefaultPw1")
    st.set_batch_text("alice,OwnPass123,p001\nbob")
    st.submit_batch()

    with Session(web_engine) as s:
        alice = s.scalars(select(LocalUser).where(LocalUser.username == "alice")).one()
        alice_profile = s.scalars(
            select(UserProfile).where(UserProfile.user_id == alice.id)
        ).one()
    assert alice_profile.bound_player_id == "p001", "第三列应写入绑定"

    assert alice.verify("OwnPass123"), "第二列应作为该行密码"
    assert alice.verify("DefaultPw1") is False


def test_batch_skips_duplicate_username(build_state, make_user, web_engine, roster):
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_default_password("DefaultPw1")
    st.set_batch_text("dup")       # root 已是 admin，这个名字不冲突
    st.submit_batch()

    st.set_batch_text("dup")       # 再建一次 → 跳过
    st.submit_batch()

    statuses = [r["status"] for r in st.batch_rows]
    assert "skipped" in statuses
    assert "用户名已存在" in " ".join(r["message"] for r in st.batch_rows)


def test_batch_reports_failures_per_line(build_state, make_user, web_engine, roster):
    """一行失败不影响其他行：短密码行失败，其余仍成功。"""
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_default_password("DefaultPw1")
    st.set_batch_text("good1\nbad,123\ngood2")   # bad 行密码 3 位
    st.submit_batch()

    by_user = {r["username"]: r["status"] for r in st.batch_rows}
    assert by_user["good1"] == "created"
    assert by_user["good2"] == "created"
    assert by_user["bad"] == "failed"

    with Session(web_engine) as s:
        names = {u[0] for u in s.exec(select(LocalUser.username)).all()}
    assert "bad" not in names


def test_batch_rejects_blank_input(build_state, make_user, web_engine, roster):
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_text("   \n\n  ")
    st.submit_batch()
    assert "请至少填写一行" in st.admin_error


def test_batch_ignores_comment_lines(build_state, make_user, web_engine, roster):
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_default_password("DefaultPw1")
    st.set_batch_text("# 这是注释\nrealuser")
    st.submit_batch()

    assert len(st.batch_rows) == 1
    assert st.batch_rows[0]["username"] == "realuser"


def test_batch_rejects_already_bound_player(build_state, make_user, web_engine, roster):
    """选手已被他人绑定时，该行失败（不静默覆盖）。"""
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_default_password("DefaultPw1")
    st.set_batch_text("first,,p001")
    st.submit_batch()
    assert st.batch_rows[0]["status"] == "created"

    st.set_batch_text("second,,p001")
    st.submit_batch()
    assert st.batch_rows[0]["status"] == "failed"
    assert "已被" in st.batch_rows[0]["message"]


def test_batch_handles_fullwidth_comma(build_state, make_user, web_engine, roster):
    """中文逗号也能分隔（用户常从表格粘贴）。"""
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_default_password("DefaultPw1")
    st.set_batch_text("zhangsan，OwnPass9，p002")
    st.submit_batch()

    assert st.batch_rows[0]["status"] == "created"
    with Session(web_engine) as s:
        u = s.scalars(select(LocalUser).where(LocalUser.username == "zhangsan")).one()
        prof = s.scalars(select(UserProfile).where(UserProfile.user_id == u.id)).one()
    assert prof.bound_player_id == "p002"


def test_batch_writes_audit(build_state, make_user, web_engine, roster):
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_default_password("DefaultPw1")
    st.set_batch_text("audited1\naudited2")
    st.submit_batch()

    actions = [r.action for r in roster.scalars(select(AuditLog)).all()]
    assert "user.batch_create" in actions


def test_clear_batch_resets_state(build_state, make_user, web_engine, roster):
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.set_batch_default_password("DefaultPw1")
    st.set_batch_text("x1")
    st.submit_batch()
    assert st.batch_rows

    st.clear_batch()
    assert st.batch_rows == []
    assert st.batch_text == ""