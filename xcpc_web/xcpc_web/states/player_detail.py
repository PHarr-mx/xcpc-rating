"""选手详情页 State（P5）：路由参数取 player_id，加载档案 + 参赛历史。"""

from __future__ import annotations

import reflex as rx
from xcpc_core.player import api as player_api
from xcpc_core.player.exceptions import PlayerNotFoundError
from xcpc_core.player.models import PlayerStatus
from xcpc_core.rating import api as rating_api

from ..config import oj_profile_url, platform_label
from .auth import AuthState

_STATUS_LABELS = {
    PlayerStatus.probation: "预备队员",
    PlayerStatus.active: "现役",
    PlayerStatus.retired: "退役",
    PlayerStatus.left: "离队",
}


class PlayerDetailState(AuthState):
    """选手详情：player 为视图 dict（含 grade_label/status_label），history 为逐场记录。

    路由参数 player_id 由 Reflex 动态路由自动注入（勿声明同名 var，会触发
    DynamicRouteArgShadowsStateVarError）；统一从 router.page.params 读取。
    """

    player: dict | None = None
    history: list[dict] = []
    not_found: bool = False

    @rx.var(cache=False)
    def is_self(self) -> bool:
        """当前登录用户绑定的就是本选手（决定「编辑我的资料」入口）。

        直接读路由参数，不依赖 on_load 是否已执行；不接受客户端传入之外的来源。
        """
        if not self.bound_player_id:
            return False
        return self.router.page.params.get("player_id", "") == self.bound_player_id

    @rx.var(cache=False)
    def chart_points(self) -> list[dict]:
        """累计曲线数据点（按日期升序）。"""
        return [
            {"date": record["date"], "rating_after": record["rating_after"]}
            for record in self.history
        ]

    @rx.var(cache=False)
    def oj_accounts(self) -> list[dict]:
        """OJ 账号视图（display/url 已预算），供 oj_links 组件渲染。"""
        if not self.player:
            return []
        return self.player["oj_accounts"]

    def on_load(self) -> None:
        params = self.router.page.params
        player_id = params.get("player_id", "")
        self.player = None
        self.history = []
        self.not_found = False
        if not player_id:
            self.not_found = True
            return
        try:
            player = player_api.get_player(player_id)
        except PlayerNotFoundError:
            self.not_found = True
            return

        self.player = {
            "id": player.id,
            "name": player.name,
            "grade_label": "未设置" if player.grade == 0 else f"{player.grade}级",
            "status_label": _STATUS_LABELS.get(player.status, player.status.value),
            "aliases": player.aliases,
            "oj_accounts": [self._oj_view(account) for account in player.oj_accounts],
        }
        self.history = [
            record.model_dump(mode="json")
            for record in rating_api.player_event_history(player_id)
        ]

    @staticmethod
    def _oj_view(account) -> dict:
        """OJ 账号 → 视图 dict：展示文案与外链在服务端预算好。

        url 用空串而非 None 表示无外链——rx.cond 两个分支在构建期都会求值，
        rx.link 的 href 收到 None 会触发 prop 类型检查错误。
        """
        return {
            "display": f"{platform_label(account.platform)}: {account.handle}",
            "url": oj_profile_url(account.platform, account.handle) or "",
        }
