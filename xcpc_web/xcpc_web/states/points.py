"""积分页状态（/points）：我的认证、提交认证、个人/队伍积分榜。

权限纪律与 ProfileState 一致：认证主体一律取 ``bound_player_id``（服务端推导），
不接受客户端传入 player_id；队伍赛从本人现役队伍中选择（service 再校验成员身份）。
"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth

import xcpc_core.points.api as points_api
from xcpc_core.points.models import PointsClaimCreate

from xcpc_web.states.auth import AuthState

STATUS_LABELS = {"staged": "待审核", "approved": "已通过", "rejected": "已驳回"}


class PointsState(AuthState):
    """``/points`` 状态。"""

    # 提交认证表单
    claim_event_id: str = ""  # 下拉选项形如 "3. 场次名"
    claim_team_id: str = ""
    claim_value: str = ""
    claim_rank: str = ""
    claim_note: str = ""
    claim_error: str = ""
    claim_feedback: str = ""

    def on_load(self):
        """页面加载：未登录重定向登录页。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        self.claim_error = ""
        self.claim_feedback = ""
        return None

    # ---- 表单 setter ----

    def set_claim_event_id(self, value: str) -> None:
        self.claim_event_id = value

    def set_claim_team_id(self, value: str) -> None:
        self.claim_team_id = value

    def set_claim_value(self, value: str) -> None:
        self.claim_value = value

    def set_claim_rank(self, value: str) -> None:
        self.claim_rank = value

    def set_claim_note(self, value: str) -> None:
        self.claim_note = value

    # ---- 展示 var ----

    @rx.var(cache=False)
    def events(self) -> list[dict]:
        if not self.is_authenticated:
            return []
        return [
            {
                "id": e.id,
                "title": e.title,
                "date_label": e.date.isoformat(),
                "entity": e.entity,
                "max_value": e.max_value,
                "n_teams": e.n_teams,
            }
            for e in points_api.list_events()
        ]

    @rx.var(cache=False)
    def event_options(self) -> list[str]:
        return [f'{e["id"]}. {e["title"]}' for e in self.events]

    @rx.var(cache=False)
    def selected_event(self) -> dict | None:
        prefix = self.claim_event_id.split(".", 1)[0].strip()
        for event in self.events:
            if str(event["id"]) == prefix:
                return event
        return None

    @rx.var(cache=False)
    def selected_is_team(self) -> bool:
        event = self.selected_event
        return event is not None and event["entity"] == "team"

    @rx.var(cache=False)
    def my_teams(self) -> list[dict]:
        """提交队伍认证时的可选队伍（本人现役成员身份）。"""
        if not self.is_authenticated or not self.is_bound:
            return []
        return points_api.player_teams(player_id=self.bound_player_id)

    @rx.var(cache=False)
    def my_team_options(self) -> list[str]:
        return [f'{t["team_id"]}. {t["name"]}' for t in self.my_teams]

    @rx.var(cache=False)
    def my_claims(self) -> list[dict]:
        if not self.is_authenticated or not self.is_bound:
            return []
        return [
            {
                "id": c.id,
                "event_title": c.event_title or f"#{c.event_id}",
                "entity_label": "队伍" if c.entity == "team" else "个人",
                "owner_label": c.team_name or c.player_name or "-",
                "value": c.value,
                "rank": c.rank,
                "status_label": STATUS_LABELS.get(c.status, c.status),
                "status": c.status,
            }
            for c in points_api.my_claims(player_id=self.bound_player_id)
        ]

    @rx.var(cache=False)
    def individual_board(self) -> list[dict]:
        if not self.is_authenticated:
            return []
        return [
            {
                "rank": row.rank,
                "player_id": row.player_id,
                "name": row.name,
                "points": f"{row.points:.1f}",
                "entry_count": row.entry_count,
            }
            for row in points_api.individual_leaderboard()
        ]

    @rx.var(cache=False)
    def team_board(self) -> list[dict]:
        if not self.is_authenticated:
            return []
        return [
            {
                "rank": row.rank,
                "name": row.name,
                "team_points": f"{row.team_points:.1f}",
                "member_points": f"{row.member_points:.1f}",
                "composite": f"{row.composite:.1f}",
                "members": "、".join(row.members),
            }
            for row in points_api.team_leaderboard()
        ]

    # ---- 事件 ----

    @rx.event
    def submit_claim(self):
        """提交认证：个人赛自动取绑定选手；队伍赛从本人现役队伍中选择。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        self.claim_error = ""
        self.claim_feedback = ""
        if not self.is_bound:
            self.claim_error = "请先在个人资料页完成选手绑定"
            return
        event = self.selected_event
        if event is None:
            self.claim_error = "请选择积分场次"
            return
        try:
            value = int(self.claim_value.strip())
            rank = int(self.claim_rank.strip())
        except ValueError:
            self.claim_error = "解题数/得分与名次必须为正整数"
            return
        if value < 1:
            self.claim_error = "积分资格线：解题数/得分至少为 1"
            return
        team_id = None
        if event["entity"] == "team":
            prefix = self.claim_team_id.split(".", 1)[0].strip()
            team_id = prefix or None
            if not team_id:
                self.claim_error = "请选择所属队伍"
                return
        try:
            points_api.submit_claim(
                params=PointsClaimCreate(
                    event_id=event["id"],
                    value=value,
                    rank=rank,
                    team_id=team_id,
                    note=self.claim_note.strip() or None,
                ),
                submitted_by=self.authenticated_user.id,
                submitter_player_id=self.bound_player_id,  # type: ignore[arg-type]
            )
        except Exception as exc:
            self.claim_error = str(exc)
            return
        self.claim_value = ""
        self.claim_rank = ""
        self.claim_note = ""
        self.claim_feedback = "认证已提交，等待 admin 审核"
