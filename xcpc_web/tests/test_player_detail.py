"""选手详情页（P5）：on_load 加载、404、绑定本人入口、OJ 外链。"""

import warnings

from reflex.istate.data import RouterData

from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.service import ContestService
from xcpc_core.contest.store import ContestStore
from xcpc_core.player.models import PlayerCreate
from xcpc_core.rating import api as rating_api
from xcpc_web.components.oj_link import oj_links
from xcpc_web.config import oj_profile_url
from xcpc_web.states.player_detail import PlayerDetailState


def _make_state(build_state, user=None, player_id: str | None = None) -> PlayerDetailState:
    """构造 PlayerDetailState（完整状态链），并按需注入动态路由参数。"""
    st = build_state(PlayerDetailState, user)
    if player_id is not None:
        # 动态路由参数在运行时与 query 合并进 page.params（base_state_processor 行为）
        root = st
        while root.parent_state is not None:
            root = root.parent_state
        root.router_data = {"pathname": f"/players/{player_id}", "query": {"player_id": player_id}}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # RouterData.page 已弃用，0.9.7 仍可用
            object.__setattr__(root, "router", RouterData.from_router_data(root.router_data))
    return st


def _seed_player_with_event(session) -> None:
    from xcpc_core.player.service import PlayerService
    from xcpc_core.player.store import PlayerStore

    PlayerService(PlayerStore(session)).create_player(
        PlayerCreate(name="张三", handle="zs", grade=2023)
    )
    ContestService(ContestStore(session)).save_contest(ContestCreate(
        id="c1", title="省赛", date=__import__("datetime").date(2026, 5, 1),
        contest_type="icpc_school", total_teams=10, weight=100,
        standings=[Standing(team_name="一队", rank=1, solved=5, penalty=100, player_ids=["p001"])],
    ))


def test_on_load_loads_player_and_history(build_state, core_store):
    _seed_player_with_event(core_store)
    st = _make_state(build_state, player_id="p001")
    st.on_load()
    assert st.not_found is False
    assert st.player is not None
    assert st.player["name"] == "张三"
    assert st.player["grade_label"] == "2023级"
    assert st.player["status_label"] == "现役"
    assert len(st.history) == 1
    assert st.history[0]["contest_id"] == "c1"
    assert st.history[0]["rating_after"] == 1250.0
    assert st.chart_points == [{"date": st.history[0]["date"], "rating_after": 1250.0}]


def test_on_load_missing_player_shows_not_found(build_state, core_store):
    st = _make_state(build_state, player_id="p999")
    st.on_load()
    assert st.not_found is True
    assert st.player is None
    assert st.history == []


def test_on_load_without_param(build_state, core_store):
    st = _make_state(build_state, player_id=None)
    st.on_load()
    assert st.not_found is True


def test_is_self_only_for_bound_owner(build_state, make_user, core_store):
    """绑定本人 → is_self True（编辑入口可见）；他人/未绑定 → False。"""
    from xcpc_core.player.service import PlayerService
    from xcpc_core.player.store import PlayerStore

    PlayerService(PlayerStore(core_store)).create_player(
        PlayerCreate(name="张三", handle="zs", grade=2023)
    )
    owner = make_user("owner", bound_player_id="p001")
    other = make_user("other")

    st_owner = _make_state(build_state, user=owner, player_id="p001")
    assert st_owner.is_self is True

    st_other = _make_state(build_state, user=other, player_id="p001")
    assert st_other.is_self is False

    st_guest = _make_state(build_state, user=None, player_id="p001")
    assert st_guest.is_self is False


def test_is_self_false_for_other_player(build_state, make_user, core_store):
    """绑定的是 p001，但看的是 p002 → False。"""
    from xcpc_core.player.service import PlayerService
    from xcpc_core.player.store import PlayerStore

    service = PlayerService(PlayerStore(core_store))
    service.create_player(PlayerCreate(name="张三", handle="zs", grade=2023))
    service.create_player(PlayerCreate(name="李四", handle="ls", grade=2024))
    owner = make_user("owner", bound_player_id="p001")

    st = _make_state(build_state, user=owner, player_id="p002")
    st.on_load()
    assert st.is_self is False
    assert st.player["name"] == "李四"


def test_oj_profile_url_templates():
    assert oj_profile_url("codeforces", "zs") == "https://codeforces.com/profile/zs"
    assert oj_profile_url("luogu", "123456") == "https://www.luogu.com.cn/user/123456"
    assert oj_profile_url("nowcoder", "abc") is None  # 未登记平台不出链
    assert oj_profile_url("codeforces", "") is None


def test_oj_view_precomputed(build_state, core_store):
    """State 侧预算 OJ 视图：display/url 就绪，牛客无 url。"""
    from xcpc_core.player.models import OJAccount
    from xcpc_core.player.service import PlayerService
    from xcpc_core.player.store import PlayerStore

    PlayerService(PlayerStore(core_store)).create_player(PlayerCreate(
        name="张三", handle="zs", grade=2023,
        oj_accounts=[OJAccount(platform="codeforces", handle="zs_cf"), OJAccount(platform="nowcoder", handle="nb")],
    ))
    st = _make_state(build_state, player_id="p001")
    st.on_load()
    accounts = st.oj_accounts
    assert accounts[0] == {"display": "Codeforces: zs_cf", "url": "https://codeforces.com/profile/zs_cf"}
    assert accounts[1] == {"display": "牛客: nb", "url": ""}
    # 组件可构建（foreach + cond 渲染分支）
    assert oj_links(st.oj_accounts) is not None
