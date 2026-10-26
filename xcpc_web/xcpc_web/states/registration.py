"""Extended RegistrationState：建号（管理员专用）。

五期定案（2026-10-26）：**不允许自助注册**。本 State 从「公开注册」改为
「管理员建号」，服务端在事件处理器内做 admin 校验——`rx.cond` 隐藏表单
不是安全边界（docs/05 §7.3）。

reflex 0.9.x 注意：@rx.event 覆盖父类方法并调用 super() 会把父事件异步排队
（self.new_user_id 仍是旧值），且继承的 handler 以基类路径注册、在基类实例上执行。
故这里自己实现 handle_registration 并调用自身的 _register_user，单事务建
LocalUser + UserProfile。
"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth
from reflex_local_auth.user import LocalUser

from sqlmodel import select

from xcpc_core.audit import record as audit_record

from .auth_models import UserProfile


class ExtendedRegistrationState(reflex_local_auth.RegistrationState):
    """管理员建号（原公开注册，已按五期决策收紧）。

    基类是 ``LocalAuthState``（不含项目角色），故本类自己推导 admin 身份。
    """

    @rx.var(cache=True)
    def is_admin(self) -> bool:
        """当前登录用户是否 admin（从 UserProfile 推导，不可由客户端覆盖）。"""
        if not self.is_authenticated:
            return False
        try:
            with rx.session() as session:
                profile = session.exec(
                    select(UserProfile).where(
                        UserProfile.user_id == self.authenticated_user.id
                    )
                ).one_or_none()
        except Exception:
            return False
        return profile is not None and profile.role == "admin"

    def _register_user(self, username, password) -> int | None:
        """建 LocalUser + UserProfile（单事务），返回新用户 id。"""
        with rx.session() as session:
            new_user = LocalUser()
            new_user.username = username
            new_user.password_hash = LocalUser.hash_password(password)
            new_user.enabled = True
            session.add(new_user)
            session.flush()
            session.refresh(new_user)
            new_user_id = new_user.id
            if new_user_id is not None:
                self.new_user_id = new_user_id
                session.add(UserProfile(user_id=new_user_id, role="member"))
            session.commit()
            return new_user_id

    @rx.event
    def handle_registration(self, form_data: dict):
        """校验 → 建号。**仅管理员可调用**。"""
        # 第 2 层守卫：真正的写保护（前端隐藏不是安全边界）
        if not self.is_authenticated or not self.is_admin:
            self.new_user_id = -1
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)

        username = (form_data.get("username") or "").strip()
        password = form_data.get("password") or ""
        confirm = form_data.get("confirm_password") or ""

        validation_errors = self._validate_fields(username, password, confirm)
        if validation_errors:
            self.new_user_id = -1
            return validation_errors

        new_id = self._register_user(username, password)
        self._audit_created(new_id, username)
        return type(self).successful_registration

    def _audit_created(self, new_user_id: int | None, username: str) -> None:
        """记 user.create 审计（best-effort：审计失败不回滚建号）。"""
        try:
            audit_record(
                action="user.create",
                target=str(new_user_id or ""),
                user_id=self.authenticated_user.id,
                diff_json={"username": username, "role": "member", "source": "admin_single"},
            )
        except Exception:
            pass

    @rx.event
    def reset_form(self):
        """建号成功后返回表单，便于连续创建。"""
        self.new_user_id = 0
        self.error_message = ""
        return None