"""Admin 审计日志状态：按用户、动作和日期筛选只读日志。"""

from __future__ import annotations

from datetime import date

import reflex as rx
import reflex_local_auth
from sqlmodel import select

from xcpc_core.audit import api as audit_api

from xcpc_web.states.admin.base import AdminState


class AdminAuditState(AdminState):
    """``/admin/audit`` 状态。"""

    user_filter: str = ""
    action_filter: str = "all"
    date_from: str = ""
    date_to: str = ""

    admin_error: str = ""

    def on_load(self):
        """第 1 层守卫：非 admin 重定向。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        self.admin_error = ""
        return None

    def set_user_filter(self, value: str) -> None:
        self.user_filter = value

    def set_action_filter(self, value: str) -> None:
        self.action_filter = value

    def set_date_from(self, value: str) -> None:
        self.date_from = value

    def set_date_to(self, value: str) -> None:
        self.date_to = value

    @rx.var(cache=False)
    def logs(self) -> list[dict]:
        """返回审计日志，并补充 web 用户名。"""
        if not self.is_admin:
            return []
        self.admin_error = ""

        user_id = self._resolve_user_id(self.user_filter)
        if self.user_filter.strip() and user_id is None:
            return []
        date_from = self._parse_date(self.date_from)
        date_to = self._parse_date(self.date_to)
        if self.date_from.strip() and date_from is None:
            self.admin_error = "开始日期格式应为 YYYY-MM-DD"
            return []
        if self.date_to.strip() and date_to is None:
            self.admin_error = "结束日期格式应为 YYYY-MM-DD"
            return []
        if date_from and date_to and date_from > date_to:
            self.admin_error = "开始日期不能晚于结束日期"
            return []

        try:
            rows = audit_api.list_logs(
                user_id=user_id,
                action=None if self.action_filter == "all" else self.action_filter,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception:
            return []

        username_map = self._username_map({int(row["user_id"]) for row in rows})
        return [
            {
                **row,
                "user_label": username_map.get(row["user_id"], f'#{row["user_id"]}'),
                "at_label": self._format_datetime(row["at"]),
            }
            for row in rows
        ]

    @rx.var(cache=False)
    def log_count(self) -> int:
        if not self.is_admin:
            return 0
        return len(self.logs)

    @staticmethod
    def _parse_date(value: str) -> date | None:
        value = value.strip()
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def _resolve_user_id(self, value: str) -> int | None:
        value = value.strip()
        if not value:
            return None
        from reflex_local_auth import LocalUser

        with rx.session() as session:
            users = session.exec(select(LocalUser).order_by(LocalUser.id)).all()
        lowered = value.casefold()
        matched = [
            user
            for user in users
            if str(user.id) == value or user.username.casefold() == lowered
        ]
        return matched[0].id if matched else -1

    @staticmethod
    def _username_map(user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        from reflex_local_auth import LocalUser

        with rx.session() as session:
            users = session.exec(select(LocalUser).where(LocalUser.id.in_(user_ids))).all()
        return {user.id: user.username for user in users}

    @staticmethod
    def _format_datetime(value: str) -> str:
        return value.replace("T", " ").split("+", 1)[0]
