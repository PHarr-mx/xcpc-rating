"""ProfileState：绑定申请与自助编辑的服务端规则（P2d 回归）。"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from xcpc_core.player import api as player_api
from xcpc_core.player.models import OJAccount, PlayerCreate, PlayerUpdate

from xcpc_web.states.auth_models import BindingRequest
from xcpc_web.states.profile import ProfileState


@pytest.fixture
def player(core_store):
    """内存 core DB 里造一个选手（id 自动分配 p001）。"""
    return player_api.create_player(PlayerCreate(name="测试选手", grade=2023))


@pytest.fixture
def member_state(build_state, make_user, core_store, player):
    """已登录、未绑定的 member 的 ProfileState。"""
    user = make_user("alice")
    return build_state(ProfileState, user), user, player


@pytest.fixture
def bound_state(build_state, make_user, core_store, player):
    """已登录、已绑定 player 的 member 的 ProfileState。"""
    user = make_user("bob", bound_player_id=player.id)
    return build_state(ProfileState, user), player


# ---- 绑定申请 ----


def test_bindable_players_lists_core_players(member_state):
    ps, _, p = member_state
    ids = [b["player_id"] for b in ps.bindable_players]
    assert p.id in ids


def test_submit_binding_rejects_unknown_player(member_state):
    ps, _, _ = member_state
    ps.binding_player_id = "p999_nonexist"
    ps.submit_binding()
    assert ps.binding_error == "所选选手不存在"


def test_submit_binding_success(member_state, web_engine):
    ps, (user_id, _), p = member_state
    ps.binding_player_id = p.id
    ps.binding_reason = "我是本人"
    ps.submit_binding()

    assert ps.binding_feedback.startswith("已提交")
    assert ps.binding_error == ""
    # 成功后表单清空
    assert ps.binding_player_id == ""
    with Session(web_engine) as s:
        br = s.exec(
            select(BindingRequest).where(
                BindingRequest.user_id == user_id,
                BindingRequest.player_id == p.id,
            )
        ).one()
        assert br.status == "pending"
        assert br.reason == "我是本人"


def test_submit_binding_rejects_duplicate(member_state):
    ps, _, p = member_state
    ps.binding_player_id = p.id
    ps.submit_binding()
    assert ps.binding_feedback.startswith("已提交")

    # 再次申请同一选手（成功后表单已清空，需重新填入）
    ps.binding_player_id = p.id
    ps.binding_error = ""
    ps.submit_binding()
    assert ps.binding_error == "已对该选手提交过申请，请等待 admin 审批"


def test_submit_binding_rejects_when_other_pending(member_state, core_store):
    ps, _, p1 = member_state
    ps.binding_player_id = p1.id
    ps.submit_binding()
    assert ps.binding_feedback.startswith("已提交")

    p2 = player_api.create_player(PlayerCreate(name="另一选手", grade=2024))
    ps.binding_player_id = p2.id
    ps.binding_error = ""
    ps.submit_binding()
    assert ps.binding_error == "已有待审批的绑定申请，请等待 admin 处理"


def test_bindable_players_excludes_already_requested(
    member_state, build_state, web_engine
):
    ps, user, p = member_state
    ps.binding_player_id = p.id
    ps.submit_binding()
    assert ps.binding_feedback.startswith("已提交")

    # 新会话（新实例，避开 computed var 实例缓存）应排除已申请过的选手
    ps2 = build_state(ProfileState, user)
    ids = [b["player_id"] for b in ps2.bindable_players]
    assert p.id not in ids


def test_submit_binding_unauthenticated_redirects(build_state, core_store, player):
    ps = build_state(ProfileState)  # 无登录会话
    result = ps.submit_binding()
    assert result is not None  # rx.redirect(...)


# ---- 自助编辑（未绑定拒绝）----


def test_save_profile_rejects_when_unbound(member_state):
    ps, _, _ = member_state
    ps.handle = "x"
    ps.save_profile()
    assert ps.edit_error == "未绑定选手，无法编辑资料"


def test_add_oj_rejects_when_unbound(member_state):
    ps, _, _ = member_state
    ps.oj_handle = "tourist"
    ps.add_oj_account()
    assert ps.edit_error == "未绑定选手，无法编辑资料"


def test_remove_oj_rejects_when_unbound(member_state):
    ps, _, _ = member_state
    ps.remove_oj_account("codeforces", "tourist")
    assert ps.edit_error == "未绑定选手，无法编辑资料"


# ---- 自助编辑（已绑定，正向）----


def test_bound_save_profile_writes_core(bound_state):
    ps, p = bound_state
    ps.handle = "newhandle"
    ps.aliases_text = "Acid, 神神\nAcid"  # 去重 + 中英文逗号/换行
    ps.save_profile()

    assert ps.edit_feedback == "资料已保存"
    saved = player_api.get_player(p.id)
    assert saved.handle == "newhandle"
    assert saved.aliases == ["Acid", "神神"]


def test_bound_add_oj_account(bound_state):
    ps, p = bound_state
    ps.oj_platform = "codeforces"
    ps.oj_handle = "tourist"
    ps.add_oj_account()

    assert ps.edit_feedback == "OJ 账号已添加"
    accounts = player_api.get_player(p.id).oj_accounts
    assert [(a.platform, a.handle) for a in accounts] == [("codeforces", "tourist")]


def test_bound_add_oj_duplicate_rejected(build_state, make_user, core_store, player):
    # 先预置账号，再构造会话——player var 首次访问即读到预置值
    player_api.update_player(
        player.id,
        PlayerUpdate(oj_accounts=[OJAccount(platform="codeforces", handle="aaa")]),
    )
    user = make_user("bob", bound_player_id=player.id)
    ps = build_state(ProfileState, user)

    ps.oj_platform = "codeforces"
    ps.oj_handle = "aaa"
    ps.add_oj_account()
    assert ps.edit_error == "该 OJ 账号已存在"


def test_bound_remove_oj_account(build_state, make_user, core_store, player):
    player_api.update_player(
        player.id,
        PlayerUpdate(
            oj_accounts=[
                OJAccount(platform="codeforces", handle="aaa"),
                OJAccount(platform="atcoder", handle="bbb"),
            ]
        ),
    )
    user = make_user("bob", bound_player_id=player.id)
    ps = build_state(ProfileState, user)

    ps.remove_oj_account("codeforces", "aaa")
    assert ps.edit_feedback == "OJ 账号已删除"
    remaining = player_api.get_player(player.id).oj_accounts
    assert [(a.platform, a.handle) for a in remaining] == [("atcoder", "bbb")]


def test_add_two_oj_accounts_keeps_both(bound_state):
    """同会话连续添加两个 OJ 账号，两个都应在库。

    探针：player 是 cache=True 且无 interval 的 computed var，第二次添加
    若基于旧缓存写库，会丢掉第一个账号。
    """
    ps, p = bound_state
    ps.oj_platform = "codeforces"
    ps.oj_handle = "aaa"
    ps.add_oj_account()
    assert ps.edit_feedback == "OJ 账号已添加"

    ps.oj_platform = "atcoder"
    ps.oj_handle = "bbb"
    ps.add_oj_account()
    assert ps.edit_feedback == "OJ 账号已添加"

    accounts = player_api.get_player(p.id).oj_accounts
    assert {(a.platform, a.handle) for a in accounts} == {
        ("codeforces", "aaa"),
        ("atcoder", "bbb"),
    }


# ---- 工具函数 ----


def test_parse_aliases():
    assert ProfileState._parse_aliases("Acid, 神神\nX，，Acid") == ["Acid", "神神", "X"]
    assert ProfileState._parse_aliases("  ") == []
