"""Admin 概览状态：待审批 / 用户 / 已绑定计数。"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth
from sqlmodel import func, select

from xcpc_web.states.admin.base import AdminState
from xcpc_web.states.auth_models import BindingRequest, UserProfile


class AdminOverviewState(AdminState):
    """/admin 概览页。"""

    admin_feedback: str = ""
    admin_error: str = ""

    @rx.event
    def on_load(self):
        """第 1 层守卫：非 admin 重定向。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        self.admin_feedback = ""
        self.admin_error = ""
        return None

    @rx.var(cache=False)
    def pending_count(self) -> int:
        """待审批绑定申请数。"""
        if not self.is_admin:
            return 0
        with rx.session() as session:
            return session.exec(
                select(func.count()).select_from(BindingRequest).where(
                    BindingRequest.status == "pending"
                )
            ).one()

    @rx.var(cache=False)
    def member_count(self) -> int:
        """member 角色用户数。"""
        if not self.is_admin:
            return 0
        with rx.session() as session:
            return session.exec(
                select(func.count()).select_from(UserProfile).where(
                    UserProfile.role == "member"
                )
            ).one()

    @rx.var(cache=False)
    def bound_count(self) -> int:
        """已绑定选手的用户数。"""
        if not self.is_admin:
            return 0
        with rx.session() as session:
            return session.exec(
                select(func.count()).select_from(UserProfile).where(
                    UserProfile.bound_player_id.isnot(None),
                )
            ).one()
