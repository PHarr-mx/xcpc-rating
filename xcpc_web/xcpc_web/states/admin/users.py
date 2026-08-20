"""Admin 用户与绑定审批状态。

三层守卫（docs/09 §4）：
1. on_load —— 非 admin 重定向
2. approve/reject 事件首行 ``_require_admin()`` —— 真正的写保护
3. pending_requests / users computed var —— 非 admin 返回空列表

跨库：绑定事实写 web DB（rx.session()）先 commit，AuditLog 到 core DB
（xcpc_core.audit）best-effort，失败不回滚绑定。
"""

from __future__ import annotations

from datetime import datetime, timezone

import reflex as rx
import reflex_local_auth
from sqlmodel import select

from xcpc_core.audit import record as audit_record
from xcpc_core.player import api as player_api

from xcpc_web.states.admin.base import AdminState
from xcpc_web.states.auth_models import BindingRequest, UserProfile


class AdminUsersState(AdminState):
    """/admin/users：绑定审批 + 用户列表。"""

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

    # ---- computed var（第 3 层守卫：非 admin 返回空）----

    @rx.var(cache=False)
    def pending_requests(self) -> list[dict]:
        """待审批绑定申请（含申请人/目标选手名称）。"""
        if not self.is_admin:
            return []
        with rx.session() as session:
            rows = session.exec(
                select(BindingRequest)
                .where(BindingRequest.status == "pending")
                .order_by(BindingRequest.created_at)
            ).all()
        if not rows:
            return []
        username_map = self._username_map({r.user_id for r in rows})
        name_map = self._player_name_map()
        return [
            {
                "request_id": r.id,
                "user_id": r.user_id,
                "username": username_map.get(r.user_id, f"#{r.user_id}"),
                "player_id": r.player_id,
                "player_name": name_map.get(r.player_id, r.player_id),
                "reason": r.reason or "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]

    @rx.var(cache=False)
    def users(self) -> list[dict]:
        """全部用户（角色 / 绑定状态），只读展示。"""
        if not self.is_admin:
            return []
        with rx.session() as session:
            from reflex_local_auth import LocalUser

            rows = session.exec(
                select(UserProfile, LocalUser)
                .join(LocalUser, LocalUser.id == UserProfile.user_id)
                .order_by(UserProfile.user_id)
            ).all()
        if not rows:
            return []
        name_map = self._player_name_map()
        return [
            {
                "user_id": up.user_id,
                "username": lu.username,
                "role": up.role,
                "bound_player_id": up.bound_player_id,
                "bound_player_name": (
                    name_map.get(up.bound_player_id, up.bound_player_id)
                    if up.bound_player_id
                    else ""
                ),
                "created_at": up.created_at.isoformat() if up.created_at else "",
            }
            for up, lu in rows
        ]

    # ---- 辅助查询（非事件/非 var）----

    def _username_map(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        with rx.session() as session:
            from reflex_local_auth import LocalUser

            us = session.exec(
                select(LocalUser).where(LocalUser.id.in_(user_ids))
            ).all()
        return {u.id: u.username for u in us}

    def _player_name_map(self) -> dict[str, str]:
        try:
            players = player_api.list_players(include_left=True)
        except Exception:
            return {}
        return {p.id: p.name for p in players}

    # ---- 事件（第 2 层守卫：写操作前真校验）----

    @rx.event
    def approve(self, request_id: int):
        """批准绑定申请：申请者获得该选手，其余 pending 申请被驳回。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_feedback = ""
        self.admin_error = ""

        with rx.session() as session:
            req = session.exec(
                select(BindingRequest).where(BindingRequest.id == request_id)
            ).one_or_none()
            if req is None:
                self.admin_error = "申请不存在"
                return
            if req.status != "pending":
                self.admin_error = "该申请已被处理，请刷新页面"
                return
            # 唯一性预检：选手已被别人绑定 / 用户已绑别人
            holder = session.exec(
                select(UserProfile).where(UserProfile.bound_player_id == req.player_id)
            ).one_or_none()
            if holder is not None and holder.user_id != req.user_id:
                self.admin_error = "该选手已绑定其他用户"
                return
            applicant = session.exec(
                select(UserProfile).where(UserProfile.user_id == req.user_id)
            ).one_or_none()
            if applicant is not None and applicant.bound_player_id is not None:
                self.admin_error = "该用户已绑定其他选手"
                return
            # 快照标量（session 关闭后 expire）
            player_id = req.player_id
            applicant_user_id = req.user_id
            # 写绑定事实
            if applicant is not None:
                applicant.bound_player_id = player_id
            req.status = "approved"
            req.reviewed_by = self.authenticated_user.id
            req.reviewed_at = datetime.now(timezone.utc)
            # 自动驳回该用户其余 pending 申请
            for other in session.exec(
                select(BindingRequest).where(
                    BindingRequest.user_id == applicant_user_id,
                    BindingRequest.status == "pending",
                    BindingRequest.id != req.id,
                )
            ).all():
                other.status = "rejected"
                other.reviewed_by = self.authenticated_user.id
                other.reviewed_at = req.reviewed_at
            session.commit()

        # 审计 best-effort（core DB，失败不回滚绑定）
        try:
            audit_record(
                action="binding.approve",
                target=player_id,
                user_id=self.authenticated_user.id,
                diff_json={
                    "request_id": request_id,
                    "applicant_user_id": applicant_user_id,
                },
            )
        except Exception:
            # audit 失败不回滚，仅少一条日志
            pass
        self.admin_feedback = f"已批准绑定：{player_id}"

    @rx.event
    def reject(self, request_id: int):
        """驳回绑定申请：仅改状态，不改绑定。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_feedback = ""
        self.admin_error = ""

        with rx.session() as session:
            req = session.exec(
                select(BindingRequest).where(BindingRequest.id == request_id)
            ).one_or_none()
            if req is None:
                self.admin_error = "申请不存在"
                return
            if req.status != "pending":
                self.admin_error = "该申请已被处理，请刷新页面"
                return
            player_id = req.player_id
            req.status = "rejected"
            req.reviewed_by = self.authenticated_user.id
            req.reviewed_at = datetime.now(timezone.utc)
            session.commit()

        try:
            audit_record(
                action="binding.reject",
                target=player_id,
                user_id=self.authenticated_user.id,
                diff_json={"request_id": request_id},
            )
        except Exception:
            pass
        self.admin_feedback = f"已驳回申请：{player_id}"
