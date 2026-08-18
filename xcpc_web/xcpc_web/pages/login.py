"""登录页。"""

import reflex as rx
import reflex_local_auth
from reflex_local_auth import LoginState

from xcpc_web.components.layout import page_shell


def _login_error() -> rx.Component:
    """渲染登录错误提示。"""
    return rx.cond(
        LoginState.error_message != "",
        rx.callout(
            LoginState.error_message,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
    )


def login() -> rx.Component:
    """登录页组件。"""
    return page_shell(
        rx.center(
            rx.cond(
                LoginState.is_hydrated,
                rx.card(
                    rx.form(
                        rx.vstack(
                            rx.heading("登录", size="7"),
                            _login_error(),
                            rx.text("用户名"),
                            rx.input(
                                name="username",
                                placeholder="用户名",
                                width="100%",
                            ),
                            rx.text("密码"),
                            rx.input(
                                name="password",
                                type="password",
                                placeholder="密码",
                                width="100%",
                            ),
                            rx.button("登录", width="100%"),
                            rx.center(
                                rx.link(
                                    "还没有账号？去注册",
                                    on_click=rx.redirect(
                                        reflex_local_auth.routes.REGISTER_ROUTE
                                    ),
                                ),
                                width="100%",
                            ),
                            min_width="50vw",
                        ),
                        on_submit=LoginState.on_submit,
                    ),
                ),
            ),
            padding_top="5vh",
            width="100%",
        ),
    )
