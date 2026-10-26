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

    # ---- 直录（P4）表单 ----

    auto_contest_id: str = ""
    auto_replace: bool = True

    def set_auto_contest_id(self, value: str) -> None:
        self.auto_contest_id = value

    def set_auto_replace(self, value: bool) -> None:
        self.auto_replace = value

    @rx.var(cache=False)
    def points_contests(self) -> list[dict]:
        """可直录的比赛：counts_for_points=True 且有成绩行。"""
        if not self.is_admin:
            return []
        import xcpc_core.contest.api as contest_api

        return [
            {"id": c.id, "title": c.title, "date": c.date.isoformat()}
            for c in contest_api.list_contests()
            if getattr(c, "counts_for_points", False)
        ]

    def auto_record(self):
        """P4：从 standings 批量生成 approved 认证与流水（选手免提交）。"""
        if ret := self._require_admin():
            return ret
        self.admin_error = ""
        self.admin_feedback = ""
        if not self.auto_contest_id:
            self.admin_error = "请先选择要直录的比赛"
            return None
        try:
            created = points_api.auto_record_contest_points(
                contest_id=self.auto_contest_id,
                created_by=self.authenticated_user.id,
                replace=self.auto_replace,
            )
        except Exception as exc:
            self.admin_error = str(exc)
            return None
        self.admin_feedback = f"已直录 {len(created)} 条认证记录（比赛 {self.auto_contest_id}）"
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
