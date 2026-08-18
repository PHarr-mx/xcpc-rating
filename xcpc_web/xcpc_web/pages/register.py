"""注册页。"""

import reflex as rx
from reflex_local_auth import routes

from xcpc_web.components.layout import page_shell
from xcpc_web.states.registration import ExtendedRegistrationState


def _register_error() -> rx.Component:
    """渲染注册错误提示。"""
    return rx.cond(
        ExtendedRegistrationState.error_message != "",
        rx.callout(
            ExtendedRegistrationState.error_message,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
    )


def register() -> rx.Component:
    """注册页组件。"""
    return page_shell(
        rx.center(
            rx.cond(
                ExtendedRegistrationState.success,
                rx.vstack(
                    rx.text("注册成功！即将跳转到登录页…", size="4"),
                    spacing="4",
                ),
                rx.card(
                    rx.form(
                        rx.vstack(
                            rx.heading("注册账号", size="7"),
                            _register_error(),
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
                            rx.text("确认密码"),
                            rx.input(
                                name="confirm_password",
                                type="password",
                                placeholder="确认密码",
                                width="100%",
                            ),
                            rx.button("注册", width="100%"),
                            rx.center(
                                rx.link(
                                    "已有账号？去登录",
                                    on_click=rx.redirect(routes.LOGIN_ROUTE),
                                ),
                                width="100%",
                            ),
                            min_width="50vw",
                        ),
                        on_submit=ExtendedRegistrationState.handle_registration,
                    ),
                ),
            ),
            padding_top="5vh",
            width="100%",
        ),
    )
