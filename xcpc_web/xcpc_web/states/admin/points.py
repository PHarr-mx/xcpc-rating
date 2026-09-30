"""Admin 积分认证管理状态（/admin/points）：认证审批（场次创建已并入比赛管理）。"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth

import xcpc_core.points.api as points_api

from xcpc_web.states.admin.base import AdminState

ENTITY_LABELS = {"player": "个人赛", "team": "队伍赛"}


class AdminPointsState(AdminState):
    """``/admin/points`` 状态。"""

    admin_error: str = ""
    admin_feedback: str = ""

    def on_load(self):
        """第 1 层守卫：非 admin 重定向。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        self.admin_error = ""
        self.admin_feedback = ""
        return None

    # ---- 展示 var ----

    @rx.var(cache=False)
    def staged_claims(self) -> list[dict]:
        if not self.is_admin:
            return []
        return [
            {
                "id": c.id,
                "contest_title": c.contest_title or c.contest_id,
                "scoring": c.scoring or "formula",
                "entity_label": ENTITY_LABELS.get(c.entity, c.entity),
                "owner_label": c.team_name or c.player_name or "-",
                "result_label": (
                    f'{c.award}'
                    if c.award
                    else f'解 {c.value} · 第 {c.rank} 名'
                ),
                "note": c.note or "",
            }
            for c in points_api.list_claims(status="staged")
        ]

    @rx.var(cache=False)
    def pending_count(self) -> int:
        return len(self.staged_claims)

    # ---- 事件 ----

    def approve(self, claim_id: int):
        if ret := self._require_admin():
            return ret
        self.admin_error = ""
        try:
            points_api.review_claim(
                claim_id=claim_id, decision="approved", decided_by=self.authenticated_user.id
            )
        except Exception as exc:
            self.admin_error = str(exc)

    def reject(self, claim_id: int):
        if ret := self._require_admin():
            return ret
        self.admin_error = ""
        try:
            points_api.review_claim(
                claim_id=claim_id, decision="rejected", decided_by=self.authenticated_user.id
            )
        except Exception as exc:
            self.admin_error = str(exc)
