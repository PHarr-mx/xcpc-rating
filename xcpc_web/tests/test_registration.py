"""注册流程：_register_user 同事务写 LocalUser + UserProfile(role=member)。"""

from reflex_local_auth import LocalUser, RegistrationState
from sqlmodel import Session, select

from xcpc_web.states.auth_models import UserProfile
from xcpc_web.states.registration import ExtendedRegistrationState


def _build_registration_state():
    """RegistrationState 的 var 链与 AuthState 不同，单独构造。"""
    parent = RegistrationState(_reflex_internal_init=True, init_substates=False)
    reg = ExtendedRegistrationState(
        parent_state=parent, init_substates=False, _reflex_internal_init=True
    )
    return reg, parent


def test_register_user_writes_both_tables(web_engine):
    reg, parent = _build_registration_state()
    reg._register_user("alice", "pw12345")

    # new_user_id 经 inherited var 委托到 parent 上
    assert parent.new_user_id is not None and parent.new_user_id != -1
    with Session(web_engine) as s:
        user = s.exec(select(LocalUser).where(LocalUser.username == "alice")).one()
        assert user.enabled
        profile = s.exec(
            select(UserProfile).where(UserProfile.user_id == user.id)
        ).one()
        assert profile.role == "member"
        assert profile.bound_player_id is None
