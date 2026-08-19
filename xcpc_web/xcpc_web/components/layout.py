"""布局组件。"""

import reflex as rx
import reflex_local_auth

from ..states.auth import AuthState


def page_shell(*children) -> rx.Component:
    """页面外壳：导航 + 内容 + 页脚。"""
    return rx.box(
        # 导航栏
        rx.hstack(
            rx.heading("XCPC Rating", size="6"),
            rx.spacer(),
            rx.cond(
                AuthState.is_authenticated,
                rx.hstack(
                    rx.text(AuthState.authenticated_user.username, size="2"),
                    rx.link(
                        "个人资料",
                        href="/profile",
                        size="2",
                    ),
                    rx.button(
                        "登出",
                        on_click=AuthState.do_logout,
                        variant="soft",
                        size="2",
                    ),
                    spacing="3",
                ),
                rx.hstack(
                    rx.button(
                        "登录",
                        on_click=rx.redirect(
                            reflex_local_auth.routes.LOGIN_ROUTE
                        ),
                        variant="soft",
                        size="2",
                    ),
                    rx.button(
                        "注册",
                        on_click=rx.redirect(
                            reflex_local_auth.routes.REGISTER_ROUTE
                        ),
                        variant="solid",
                        size="2",
                    ),
                    spacing="2",
                ),
            ),
            padding="1rem 2rem",
            border_bottom="1px solid",
            border_color=rx.color("gray", 6),
            background=rx.color("gray", 1),
        ),
        # 内容
        rx.container(*children, padding="2rem 0"),
        # 页脚
        rx.box(
            rx.center(
                rx.text("© 2026 XCPC Rating System", size="1"),
                padding="1rem",
            ),
            border_top="1px solid",
            border_color=rx.color("gray", 6),
            margin_top="2rem",
        ),
        min_height="100vh",
    )