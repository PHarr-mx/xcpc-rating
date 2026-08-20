"""Admin 权限守卫的共享基类。

三层守卫（docs/09 §4）：
1. on_load 重定向 —— 各 admin State 的 on_load 首行拒绝非 admin
2. 事件处理器内校验 —— ``_require_admin()``
3. computed var 内校验 —— 各列表/计数 var 对非 admin 返回空

``_require_admin`` 判定依赖 ``AuthState.is_admin``（从会话派生），
不是可被客户端覆盖的可写 var。
"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth

from xcpc_web.states.auth import AuthState


class AdminState(AuthState):
    """admin 页面的共享基类。"""

    def _require_admin(self) -> rx.event.EventSpec | None:
        """第 2 层守卫：未登录→/login，非 admin→/。返回 None 表示通过。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        return None
