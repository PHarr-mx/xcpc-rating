"""比赛详情页（P5）：加载、404、format 切列、奖项/打星映射、页面构建冒烟。"""

import warnings
from datetime import date

from reflex.istate.data import RouterData

from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.service import ContestService
from xcpc_core.contest.store import ContestStore
from xcpc_core.player.models import PlayerCreate
from xcpc_core.player.service import PlayerService
from xcpc_core.player.store import PlayerStore
from xcpc_web.components.board_table import board_table
from xcpc_web.components.standings_table import standings_table
from xcpc_web.pages.contest_detail import contest_detail
from xcpc_web.pages.player_detail import player_detail
from xcpc_web.states.contest_detail import ContestDetailState


def _make_state(build_state, user=None, contest_id: str | None = None) -> ContestDetailState:
    st = build_state(ContestDetailState, user)
    if contest_id is not None:
        root = st
        while root.parent_state is not None:
            root = root.parent_state
        root.router_data = {
            "pathname": f"/contests/{contest_id}",
            "query": {"contest_id": contest_id},
        }
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # RouterData.page 已弃用，0.9.7 仍可用
            object.__setattr__(root, "router", RouterData.from_router_data(root.router_data))
    return st


def _seed(session) -> None:
    service = PlayerService(PlayerStore(session))
    service.create_player(PlayerCreate(name="张三", handle="zs", grade=2023))
    service.create_player(PlayerCreate(name="李四", handle="ls", grade=2023))
    contest_service = ContestService(ContestStore(session))
    contest_service.save_contest(ContestCreate(
        id="c_team", title="省赛", date=date(2026, 5, 18),
        contest_type="icpc_provincial", total_teams=100, school_teams_count=2, weight=70,
        standings=[Standing(
            team_name="一队", rank=3, solved=7, penalty=500, school_rank=1,
            award="gold", player_ids=["p001", "p002"],
        )],
    ))
    contest_service.save_contest(ContestCreate(
        id="c_oi", title="新生 OI", date=date(2026, 3, 1),
        contest_type="icpc_school", format="oi", total_teams=20, weight=50,
        standings=[Standing(rank=2, score=280, player_ids=["p001"])],
    ))


def test_on_load_loads_team_contest(build_state, core_store):
    _seed(core_store)
    st = _make_state(build_state, contest_id="c_team")
    st.on_load()
    assert st.not_found is False
    assert st.contest["title"] == "省赛"
    assert st.contest["source_label"] == "正式赛"
    assert st.contest["type_label"] == "组队 XCPC"
    assert st.is_oi is False
    assert "总队伍 100" in st.meta_line and "权重 70" in st.meta_line

    (row,) = st.standings
    assert row["members"] == "张三、李四"  # 队员姓名已解析
    assert row["award_label"] == "金奖"
    assert row["solved"] == 7 and row["penalty"] == 500
    assert "打星" not in row["team_name"]


def test_on_load_loads_oi_contest(build_state, core_store):
    _seed(core_store)
    st = _make_state(build_state, contest_id="c_oi")
    st.on_load()
    assert st.is_oi is True
    (row,) = st.standings
    assert row["score"] == 280
    assert row["team_name"] == "—"  # solo 无队名
    assert row["members"] == "张三"


def test_manually_added_star_marker(build_state, core_store):
    _seed(core_store)
    ContestService(ContestStore(core_store)).save_contest(ContestCreate(
        id="c_star", title="补录赛", date=date(2026, 6, 1),
        contest_type="icpc_school", total_teams=10,
        standings=[Standing(
            team_name="打星队", rank=1, solved=9, penalty=100,
            manually_added=True, player_ids=["p001"],
        )],
    ))
    st = _make_state(build_state, contest_id="c_star")
    st.on_load()
    assert st.standings[0]["team_name"] == "打星队（打星）"


def test_on_load_missing_contest(build_state, core_store):
    st = _make_state(build_state, contest_id="nope")
    st.on_load()
    assert st.not_found is True
    assert st.contest is None


def test_on_load_without_param(build_state, core_store):
    st = _make_state(build_state, contest_id=None)
    st.on_load()
    assert st.not_found is True


def test_detail_pages_build(build_state, core_store):
    """三个含 Var 逻辑的页面/组件构建冒烟（链接 f-string、foreach、cond）。"""
    _seed(core_store)
    assert contest_detail() is not None
    assert player_detail() is not None
    assert board_table() is not None
    # 空 plain list 无法推断 foreach 条目类型，给带键位的样例行
    xcpc_row = {"rank": 1, "team_name": "x", "members": "x", "solved": 1, "penalty": 1, "school_rank": None, "award_label": ""}
    oi_row = {"rank": 1, "members": "x", "score": 1, "school_rank": None, "award_label": ""}
    assert standings_table([xcpc_row], False) is not None
    assert standings_table([oi_row], True) is not None
