"""Admin 概览状态：计数与守卫（P2e 第 1/3 层）。"""

from sqlmodel import Session, select

from xcpc_web.states.admin.overview import AdminOverviewState
from xcpc_web.states.auth_models import BindingRequest


def _make_pending(web_engine, user_id, player_id, status="pending"):
    with Session(web_engine) as s:
        s.add(BindingRequest(user_id=user_id, player_id=player_id, status=status))
        s.commit()


def test_counts_as_admin(build_state, make_user, web_engine):
    u1, _ = make_user("alice", role="member")
    make_user("bob", role="member", bound_player_id="p001")
    _make_pending(web_engine, u1, "p002")

    st = build_state(AdminOverviewState, make_user("root", role="admin"))
    assert st.pending_count == 1
    assert st.member_count == 2
    assert st.bound_count == 1


def test_counts_zero_for_non_admin(build_state, make_user, web_engine):
    """第 3 层：非 admin 计数返回 0，不泄露数据。"""
    u1, _ = make_user("alice")
    _make_pending(web_engine, u1, "p999")

    st = build_state(AdminOverviewState, make_user("member_user"))
    assert st.pending_count == 0
    assert st.member_count == 0
    assert st.bound_count == 0


def test_on_load_non_admin_redirects(build_state, make_user):
    """第 1 层：非 admin on_load 重定向到 /。"""
    st = build_state(AdminOverviewState, make_user("member_user"))
    result = st.on_load()
    assert result is not None  # rx.redirect("/")


def test_on_load_admin_not_redirect(build_state, make_user):
    st = build_state(AdminOverviewState, make_user("root", role="admin"))
    assert st.on_load() is None
