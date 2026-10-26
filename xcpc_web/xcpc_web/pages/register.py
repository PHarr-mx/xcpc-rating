"""建号页（管理员专用，替代原公开注册页）。

五期定案（2026-10-26）：**不允许自助注册**，账号一律由管理员创建。
原 ``/register`` 路由保留但改为 admin-only：普通访客访问会被重定向，
管理员可在本页为单个成员建号。批量建号见 ``/admin/users`` 的批量表单。
"""

import reflex as rx
import reflex_local_auth

from xcpc_web.components.layout import page_shell
from xcpc_web.states.registration import ExtendedRegistrationState


def _guard_notice() -> rx.Component:
    """非管理员看到的中性说明（不暴露建号入口）。"""
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading("此页面仅限管理员", size="6"),
                rx.text(
                    "系统不开放自助注册。账号由赛事管理员统一创建，如需开通请联系负责人。",
                    size="2",
                    color_scheme="gray",
                ),
                rx.button(
                    "去登录",
                    on_click=rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE),
                    width="100%",
                ),
                spacing="4",
                width="100%",
                align="center",
            ),
            min_width="24em",
        ),
        padding_top="10vh",
        width="100%",
    )


def _register_error() -> rx.Component:
    """渲染建号错误提示。"""
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


def _register_form() -> rx.Component:
    return rx.center(
        rx.cond(
            ExtendedRegistrationState.success,
            rx.card(
                rx.vstack(
                    rx.heading("账号已创建", size="6"),
                    rx.text(
                        "请把用户名与初始密码告知该成员，并提醒其首次登录后自行修改。",
                        size="2",
                        color_scheme="gray",
                    ),
                    rx.hstack(
                        rx.button(
                            "再建一个",
                            on_click=ExtendedRegistrationState.reset_form,
                            variant="soft",
                        ),
                        rx.button(
                            "去用户管理",
                            on_click=rx.redirect("/admin/users"),
                        ),
                        spacing="3",
                    ),
                    spacing="4",
                    align="start",
                ),
                min_width="26em",
            ),
            rx.card(
                rx.form(
                    rx.vstack(
                        rx.heading("创建成员账号", size="7"),
                        rx.text(
                            "仅管理员可用。新账号默认为成员（member）角色，"
                            "登录后可自行申请绑定选手。",
                            size="2",
                            color_scheme="gray",
                        ),
                        _register_error(),
                        rx.text("用户名"),
                        rx.input(name="username", placeholder="用户名", width="100%"),
                        rx.text("初始密码"),
                        rx.input(
                            name="password",
                            type="password",
                            placeholder="至少 6 位",
                            width="100%",
                        ),
                        rx.text("确认密码"),
                        rx.input(
                            name="confirm_password",
                            type="password",
                            placeholder="再次输入",
                            width="100%",
                        ),
                        rx.button("创建账号", width="100%"),
                        min_width="50vw",
                    ),
                    on_submit=ExtendedRegistrationState.handle_registration,
                ),
                min_width="26em",
            ),
        ),
        padding_top="5vh",
        width="100%",
    )


def register() -> rx.Component:
    """建号页（admin-only）。"""
    return page_shell(
        rx.cond(
            ExtendedRegistrationState.is_admin,
            _register_form(),
            _guard_notice(),
        ),
    )