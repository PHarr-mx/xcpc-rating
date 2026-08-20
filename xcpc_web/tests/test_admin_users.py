"""Admin 绑定审批状态：守卫、正向、异常路径（P2e 第 2/3 层 + P2f）。"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import select as sa_select
from sqlmodel import Session, select

from xcpc_core.audit import api as audit_api
from xcpc_core.db.tables import AuditLog
from xcpc_core.player import api as player_api
from xcpc_core.player.models import PlayerCreate

from xcpc_web.states.admin.users import AdminUsersState
from xcpc_web.states.auth_models import BindingRequest, UserProfile


# ---- 夹具 ----

@pytest.fixture
def player(core_store):
    return player_api.create_player(PlayerCreate(name="甲", grade=2023))


def _make_req(web_engine, user_id, player_id, status="pending"):
    with Session(web_engine) as s:
        r = BindingRequest(user_id=user_id, player_id=player_id, status=status)
        s.add(r)
        s.flush()
        s.refresh(r)
        s.commit()
        return r.id


# ---- 第 3 层守卫：computed var ----


def test_pending_requests_empty_for_non_admin(build_state, make_user, web_engine):
    st = build_state(AdminUsersState, make_user("alice"))
    assert st.pending_requests == []


def test_users_empty_for_non_admin(build_state, make_user):
    st = build_state(AdminUsersState, make_user("alice"))
    assert st.users == []


# ---- 第 1 层守卫：on_load ----


def test_on_load_non_admin_redirects(build_state, make_user):
    st = build_state(AdminUsersState, make_user("alice"))
    assert st.on_load() is not None  # rx.redirect("/")


def test_on_load_admin_pass(build_state, make_user):
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    assert st.on_load() is None


# ---- 第 2 层守卫：事件校验 ----


def test_approve_non_admin_redirects(build_state, make_user, web_engine):
    st = build_state(AdminUsersState, make_user("alice"))
    ret = st.approve(999)
    assert ret is not None  # rx.redirect


def test_approve_unknown_request(build_state, make_user):
    """不存在申请 → 错误提示，非静默。"""
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.approve(99999)
    assert st.admin_error == "申请不存在"


def test_approve_already_processed(build_state, make_user, web_engine, player):
    """已处理的申请不能重复操作。"""
    rid = _make_req(web_engine, make_user("alice")[0], player.id, status="approved")
    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.approve(rid)
    assert st.admin_error == "该申请已被处理，请刷新页面"


# ---- 正向：approve ----


def test_approve_binds_player(build_state, make_user, web_engine, player):
    u1 = make_user("alice")
    rid = _make_req(web_engine, u1[0], player.id)
    adm = make_user("root", role="admin")
    st = build_state(AdminUsersState, adm)
    st.approve(rid)
    assert st.admin_feedback == f"已批准绑定：{player.id}"
    with Session(web_engine) as s:
        req = s.get(BindingRequest, rid)
        assert req.status == "approved"
        assert req.reviewed_by == adm[0]  # admin user_id
        assert req.reviewed_at is not None
        up = s.exec(select(UserProfile).where(UserProfile.user_id == u1[0])).one()
        assert up.bound_player_id == player.id


def test_approve_writes_audit_log(
    build_state, make_user, web_engine, player, core_store
):
    """approve 后在 core 库产生 AuditLog 行。"""
    audit_api.configure_session(core_store)
    u1 = make_user("alice")
    rid = _make_req(web_engine, u1[0], player.id)
    adm = make_user("root", role="admin")
    st = build_state(AdminUsersState, adm)

    st.approve(rid)

    rows = core_store.execute(sa_select(AuditLog)).scalars().all()
    assert len(rows) == 1
    log = rows[0]
    assert log.action == "binding.approve"
    assert log.target == player.id
    assert log.user_id == adm[0]


def test_approve_cancels_other_pending(
    build_state, make_user, web_engine, player, core_store
):
    """一个用户有多个 pending 申请时，批准一个，其余自动驳回。"""
    u1 = make_user("alice")
    p2 = player_api.create_player(PlayerCreate(name="乙", grade=2024))
    rid1 = _make_req(web_engine, u1[0], player.id)  # 批准这个
    rid2 = _make_req(web_engine, u1[0], p2.id)  # 自动驳回

    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.approve(rid1)

    with Session(web_engine) as s:
        r1 = s.get(BindingRequest, rid1)
        assert r1.status == "approved"
        r2 = s.get(BindingRequest, rid2)
        assert r2.status == "rejected"


# ---- 异常：边界检查 ----


def test_approve_player_already_owned(
    build_state, make_user, web_engine, player
):
    """选手已被别人绑定时拒绝。"""
    make_user("owner", bound_player_id=player.id)
    u2 = make_user("applicant")
    rid = _make_req(web_engine, u2[0], player.id)

    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.approve(rid)
    assert st.admin_error == "该选手已绑定其他用户"


def test_approve_applicant_already_bound(
    build_state, make_user, web_engine, player
):
    """申请者已绑定别的选手时拒绝。"""
    u1 = make_user("alice", bound_player_id="p_other")
    rid = _make_req(web_engine, u1[0], player.id)

    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.approve(rid)
    assert st.admin_error == "该用户已绑定其他选手"


def test_approve_multiple_for_same_player(
    build_state, make_user, web_engine, player
):
    """两个人争同一个选手：第一个批了，第二个报错。"""
    u1 = make_user("alice")
    u2 = make_user("bob")
    rid1 = _make_req(web_engine, u1[0], player.id)
    rid2 = _make_req(web_engine, u2[0], player.id)

    st = build_state(AdminUsersState, make_user("root", role="admin"))
    st.approve(rid1)
    assert st.admin_feedback.startswith("已批准")
    st.approve(rid2)
    assert st.admin_error == "该选手已绑定其他用户"


# ---- reject ----


def test_reject_sets_status(build_state, make_user, web_engine, player, core_store):
    audit_api.configure_session(core_store)
    u1 = make_user("alice")
    rid = _make_req(web_engine, u1[0], player.id)
    adm = make_user("root", role="admin")

    st = build_state(AdminUsersState, adm)
    st.reject(rid)
    assert st.admin_feedback == f"已驳回申请：{player.id}"
    with Session(web_engine) as s:
        req = s.get(BindingRequest, rid)
        assert req.status == "rejected"
        assert req.reviewed_by == adm[0]
        assert req.reviewed_at is not None
    rows = core_store.execute(sa_select(AuditLog)).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "binding.reject"
