"""Admin 积分管理状态：场次配置 + 认证审批（/admin/points）。"""

from __future__ import annotations

from datetime import date

import reflex as rx
import reflex_local_auth

import xcpc_core.points.api as points_api
from xcpc_core.points.models import PointsEventCreate

from xcpc_web.states.admin.base import AdminState

ENTITY_LABELS = {"player": "个人赛", "team": "队伍赛"}
KIND_LABELS = {"solved": "解题数", "score": "得分"}


class AdminPointsState(AdminState):
    """``/admin/points`` 状态。"""

    # 场次创建表单
    form_title: str = ""
    form_date: str = ""
    form_entity: str = "player"
    form_kind: str = "solved"
    form_max_value: str = ""
    form_n_teams: str = ""
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

    # ---- 表单 setter ----

    def set_form_title(self, value: str) -> None:
        self.form_title = value

    def set_form_date(self, value: str) -> None:
        self.form_date = value

    def set_form_entity(self, value: str) -> None:
        self.form_entity = value

    def set_form_kind(self, value: str) -> None:
        self.form_kind = value

    def set_form_max_value(self, value: str) -> None:
        self.form_max_value = value

    def set_form_n_teams(self, value: str) -> None:
        self.form_n_teams = value

    # ---- 展示 var ----

    @rx.var(cache=False)
    def events(self) -> list[dict]:
        if not self.is_admin:
            return []
        return [
            {
                "id": e.id,
                "title": e.title,
                "date_label": e.date.isoformat(),
                "entity_label": ENTITY_LABELS.get(e.entity, e.entity),
                "kind_label": KIND_LABELS.get(e.kind, e.kind),
                "max_value": e.max_value,
                "n_teams": e.n_teams,
                "claims_staged": e.claims_staged,
                "claims_total": e.claims_total,
            }
            for e in points_api.list_events()
        ]

    @rx.var(cache=False)
    def staged_claims(self) -> list[dict]:
        if not self.is_admin:
            return []
        return [
            {
                "id": c.id,
                "event_title": c.event_title or f"#{c.event_id}",
                "entity_label": ENTITY_LABELS.get(c.entity, c.entity),
                "owner_label": c.team_name or c.player_name or "-",
                "value": c.value,
                "rank": c.rank,
                "note": c.note or "",
            }
            for c in points_api.list_claims(status="staged")
        ]

    @rx.var(cache=False)
    def pending_count(self) -> int:
        return len(self.staged_claims)

    # ---- 事件 ----

    def create_event(self):
        """创建积分场次（参数即 UCup 式公式的 max_value / n_teams）。"""
        if ret := self._require_admin():
            return ret
        self.admin_error = ""
        self.admin_feedback = ""
        title = self.form_title.strip()
        if not title:
            self.admin_error = "请填写场次名称"
            return
        try:
            event_date = date.fromisoformat(self.form_date.strip())
        except ValueError:
            self.admin_error = "日期格式应为 YYYY-MM-DD"
            return
        try:
            max_value = int(self.form_max_value.strip())
            n_teams = int(self.form_n_teams.strip())
        except ValueError:
            self.admin_error = "全场最高值与参赛实体数必须为正整数"
            return
        try:
            view = points_api.create_event(
                params=PointsEventCreate(
                    title=title,
                    date=event_date,
                    entity=self.form_entity,  # type: ignore[arg-type]
                    kind=self.form_kind,  # type: ignore[arg-type]
                    max_value=max_value,
                    n_teams=n_teams,
                ),
                created_by=self.authenticated_user.id,
            )
        except Exception as exc:
            self.admin_error = str(exc)
            return
        self.form_title = ""
        self.form_date = ""
        self.form_max_value = ""
        self.form_n_teams = ""
        self.admin_feedback = f"场次「{view.title}」已创建"

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
