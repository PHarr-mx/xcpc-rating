"""BoardState 的 URL query 同步（docs/14 P1 任务 6）。

- on_load：从 URL query（router_data["query"] → page.params）恢复筛选状态；
  非法值忽略回落默认。
- set_*_sync_url：筛选变化后返回 rx.redirect（客户端导航、replace 不留历史）。
- set_*：纯状态变更（不含 URL 同步），保持原有语义。

测试中 router 的注入方式照抄 reflex_base/event/processor/base_state_processor.py
的运行时行为：先赋 state.router_data，再把 RouterData.from_router_data(...) 赋给 state.router。
"""

import warnings

import pytest
from reflex.istate.data import RouterData

from xcpc_web.states.board import BoardState


def _make_board_state(query: dict | None = None) -> BoardState:
    """构造 BoardState；传 query 则模拟浏览器带参打开榜单页。

    router 是 BaseState 层的继承 var（真实存于根），conftest 的链根是
    LocalAuthState 所以能正常赋值；这里 BoardState 直接当根用时，
    object.__setattr__ 绕过继承转发注入（与运行时
    base_state_processor.py:357 的 `state.router = RouterData.from_router_data(...)` 等价）。
    """
    state = BoardState(_reflex_internal_init=True, init_substates=False)
    if query is not None:
        state.router_data = {"pathname": "/", "query": query}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # RouterData.page 已弃用，0.9.7 仍可用
            object.__setattr__(
                state, "router", RouterData.from_router_data(state.router_data)
            )
    return state


def _redirect_path(spec) -> str:
    """从 rx.redirect 返回的 EventSpec 中提取 path 字面量。"""
    assert spec is not None
    for arg in spec.args:
        var, value = arg
        if var._js_expr == "path":
            return value._var_value
    raise AssertionError(f"no path in EventSpec args: {spec.args}")


def test_on_load_default_without_query(core_store):
    """无参数打开：全部默认值；周期选项来自注入的（空）数据源。"""
    st = _make_board_state()
    st.on_load()
    assert st.mode == "all"
    assert st.period_type == "career"
    assert st.period_id is None
    assert st.search == ""
    assert st.period_options == [{"key": "career", "period_type": "career", "id": None, "label": "生涯"}]


def test_on_load_restores_from_query(core_store):
    """带参打开：筛选状态从 URL query 恢复。"""
    st = _make_board_state(
        {"mode": "formal_only", "period_type": "competition_year", "period_id": "2025", "search": "张"}
    )
    st.on_load()
    assert st.mode == "formal_only"
    assert st.period_type == "competition_year"
    assert st.period_id == "2025"
    assert st.search == "张"


def test_on_load_ignores_invalid_values(core_store):
    """非法 mode/period_type 忽略；空白 period_id 忽略；未知参数不影响。"""
    st = _make_board_state(
        {"mode": "javascript:alert(1)", "period_type": "bogus", "period_id": "   ", "evil": "x"}
    )
    st.on_load()
    assert st.mode == "all"
    assert st.period_type == "career"
    assert st.period_id is None


def test_on_load_ignores_period_id_on_career(core_store):
    """career 下 period_id 无意义，不恢复。"""
    st = _make_board_state({"period_id": "2025"})
    st.on_load()
    assert st.period_type == "career"
    assert st.period_id is None


def test_setters_validate():
    """set_* 对非法值不生效。"""
    st = _make_board_state()
    st.set_mode("bogus")
    st.set_period("bogus")
    st.set_sort("bogus")
    assert st.mode == "all"
    assert st.period_type == "career"
    assert st.sort_by == "rating_desc"


def test_set_mode_sync_url_returns_redirect(core_store):
    """set_mode_sync_url 改状态并返回带参 redirect。"""
    st = _make_board_state()
    with pytest.MonkeyPatch.context() as mp:
        # board_snapshot 走真实 core API；内存库无数据即可，不关心 rows 内容
        spec = st.set_mode_sync_url("formal_only")
    assert st.mode == "formal_only"
    assert _redirect_path(spec) == "/?mode=formal_only"


def test_set_period_sync_url_returns_redirect(core_store):
    st = _make_board_state()
    with pytest.MonkeyPatch.context() as mp:
        spec = st.set_period_sync_url("season", "2026-春学期")
    assert st.period_type == "season"
    assert st.period_id == "2026-春学期"
    assert _redirect_path(spec) == "/?period_type=season&period_id=2026-%E6%98%A5%E5%AD%A6%E6%9C%9F"


def test_set_search_sync_url_encodes_and_trims_default(core_store):
    """搜索词写入 URL 需 URL 编码；恢复默认（career/all）时不带多余参数。"""
    st = _make_board_state()
    with pytest.MonkeyPatch.context() as mp:
        spec = st.set_search_sync_url("Zhang San")
    assert st.search == "Zhang San"
    assert _redirect_path(spec) == "/?search=Zhang%20San"

    # 切回默认组合 → URL 回到 /
    st2 = _make_board_state({"mode": "formal_only"})
    with pytest.MonkeyPatch.context() as mp:
        spec2 = st2.set_mode_sync_url("all")
    assert _redirect_path(spec2) == "/"


def test_set_period_non_sync_keeps_url_free(core_store):
    """直接调 set_period（无 _sync_url 后缀）不产生 redirect，供非 UI 调用。"""
    st = _make_board_state()
    st.set_period("competition_year", "2025")
    assert st.period_type == "competition_year"
    assert st.period_id == "2025"


def test_period_option_handler(core_store):
    """具体周期下拉：按 label 设置周期；career 选项复位 period_id；URL 同步。"""
    st = _make_board_state()
    st.on_load()
    st.period_options = [
        {"key": "career", "period_type": "career", "id": None, "label": "生涯"},
        {"key": "competition_year:2025", "period_type": "competition_year", "id": "2025", "label": "2025赛年"},
        {"key": "season:2025-秋学期", "period_type": "season", "id": "2025-秋学期", "label": "2025-秋学期"},
    ]

    spec = st.set_period_option_sync_url("2025赛年")
    assert st.period_type == "competition_year"
    assert st.period_id == "2025"
    assert _redirect_path(spec) == "/?period_type=competition_year&period_id=2025"
    assert st.period_value_label == "2025赛年"

    spec2 = st.set_period_option_sync_url("2025-秋学期")
    assert st.period_type == "season" and st.period_id == "2025-秋学期"
    assert _redirect_path(spec2) == "/?period_type=season&period_id=2025-%E7%A7%8B%E5%AD%A6%E6%9C%9F"

    spec3 = st.set_period_option_sync_url("生涯")
    assert st.period_type == "career" and st.period_id is None
    assert _redirect_path(spec3) == "/"
    assert st.period_value_label == "生涯"


def test_set_period_option_unknown_label_ignored(core_store):
    st = _make_board_state()
    st.on_load()
    st.set_period_option_sync_url("不存在的选项")
    assert st.period_type == "career"
    assert st.period_id is None


def test_board_url_roundtrip(core_store):
    """_board_url 产出 → on_load 恢复 → 再产出，URL 幂等。"""
    st = _make_board_state()
    with pytest.MonkeyPatch.context() as mp:
        spec = st.set_mode_sync_url("formal_only")
    url = _redirect_path(spec)

    st2 = _make_board_state(
        dict(p.split("=", 1) for p in url[2:].split("&"))
    )
    st2.on_load()
    assert st2.mode == "formal_only"
    with pytest.MonkeyPatch.context() as mp:
        spec2 = st2._sync_url()
    assert _redirect_path(spec2) == url
