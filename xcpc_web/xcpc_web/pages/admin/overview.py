"""Admin 概览页：待审批 / 用户 / 已绑定计数卡片。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.admin.overview import AdminOverviewState


def _feedback() -> rx.Component:
    """操作反馈提示条。"""
    return rx.cond(
        AdminOverviewState.admin_error != "",
        rx.callout(
            AdminOverviewState.admin_error,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
        rx.cond(
            AdminOverviewState.admin_feedback != "",
            rx.callout(
                AdminOverviewState.admin_feedback,
                icon="check",
                color_scheme="green",
                role="status",
                width="100%",
            ),
        ),
    )


def _stat_card(label: str, value) -> rx.Component:
    """概览统计卡。"""
    return rx.card(
        rx.vstack(
            rx.text(label, size="2", color_scheme="gray"),
            rx.heading(f"{value}", size="7"),
            align="center",
            spacing="1",
        ),
        width="100%",
    )


def _overview() -> rx.Component:
    return rx.vstack(
        rx.heading("后台概览", size="7"),
        rx.hstack(
            rx.link(
                _stat_card("待审批绑定", AdminOverviewState.pending_count),
                href="/admin/users",
                width="100%",
            ),
            _stat_card("用户数", AdminOverviewState.member_count),
            _stat_card("已绑定", AdminOverviewState.bound_count),
            spacing="4",
            width="100%",
            align="stretch",
        ),
        _feedback(),
        rx.link(
            rx.button("前往绑定审批", color_scheme="green"),
            href="/admin/users",
        ),
        spacing="6",
        width="100%",
        max_width="60em",
    )


def admin_overview() -> rx.Component:
    """/admin 概览页。"""
    return page_shell(
        rx.cond(
            AdminOverviewState.is_admin,
            _overview(),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ),
    )
