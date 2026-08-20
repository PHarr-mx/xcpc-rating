"""AuthState var 链：登录态 / 角色 / 绑定状态的 computed var 求值。"""

from xcpc_web.states.auth import AuthState


def test_unauthenticated(build_state):
    st = build_state(AuthState)
    assert st.is_authenticated is False
    assert st.profile is None
    assert st.is_admin is False
    assert st.bound_player_id is None
    assert st.is_bound is False


def test_member(build_state, make_user):
    user = make_user("alice")
    st = build_state(AuthState, user)
    assert st.is_authenticated is True
    assert st.authenticated_user.username == "alice"
    assert st.is_admin is False
    assert st.is_bound is False


def test_admin(build_state, make_user):
    user = make_user("root", role="admin")
    st = build_state(AuthState, user)
    assert st.is_authenticated is True
    assert st.is_admin is True


def test_bound_member(build_state, make_user):
    user = make_user("bob", bound_player_id="p001")
    st = build_state(AuthState, user)
    assert st.bound_player_id == "p001"
    assert st.is_bound is True
