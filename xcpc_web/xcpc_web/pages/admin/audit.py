"""Admin 审计页：审计日志筛选与只读展示。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.admin.audit import AdminAuditState


def _feedback() -> rx.Component:
    return rx.cond(
        AdminAuditState.admin_error != "",
        rx.callout(
            AdminAuditState.admin_error,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
        rx.fragment(),
    )


def _audit_table() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.cond(
                AdminAuditState.logs.length() > 0,
                rx.scroll_area(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("时间"),
                                rx.table.column_header_cell("用户"),
                                rx.table.column_header_cell("动作"),
                                rx.table.column_header_cell("目标"),
                                rx.table.column_header_cell("变更摘要"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(
                                AdminAuditState.logs,
                                lambda log: rx.table.row(
                                    rx.table.cell(log["at_label"]),
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.text(log["user_label"]),
                                            rx.text(f'#{log["user_id"]}', size="1", color_scheme="gray"),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(rx.badge(log["action"], color_scheme="blue")),
                                    rx.table.cell(log["target"]),
                                    rx.table.cell(rx.code(log["diff_json"])),
                                ),
                            ),
                        ),
                        width="100%",
                    ),
                    type="auto",
                    scrollbars="horizontal",
                    width="100%",
                ),
                rx.text("没有符合条件的审计记录", color_scheme="gray", size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def admin_audit() -> rx.Component:
    """``/admin/audit`` 审计日志页面。"""
    return page_shell(
        rx.cond(
            AdminAuditState.is_admin,
            rx.vstack(
                rx.vstack(
                    rx.heading("审计日志", size="7"),
                    rx.text(
                        "只读查看后台写操作，支持按用户、动作和日期筛选。",
                        size="2",
                        color_scheme="gray",
                    ),
                    align="start",
                    spacing="1",
                    width="100%",
                ),
                _feedback(),
                rx.hstack(
                    rx.input(
                        value=AdminAuditState.user_filter,
                        on_change=AdminAuditState.set_user_filter,
                        placeholder="用户名或用户 ID",
                        width="100%",
                    ),
                    rx.select(
                        [
                            "all",
                            "binding.approve",
                            "binding.reject",
                            "player.create",
                            "player.update",
                            "player.delete",
                            "team.create",
                            "team.update",
                            "team.delete",
                            "contest.delete",
                        ],
                        value=AdminAuditState.action_filter,
                        on_change=AdminAuditState.set_action_filter,
                        width="12em",
                    ),
                    rx.input(
                        value=AdminAuditState.date_from,
                        on_change=AdminAuditState.set_date_from,
                        placeholder="开始日期",
                        type="date",
                        width="10em",
                    ),
                    rx.input(
                        value=AdminAuditState.date_to,
                        on_change=AdminAuditState.set_date_to,
                        placeholder="结束日期",
                        type="date",
                        width="10em",
                    ),
                    width="100%",
                    spacing="3",
                    align="center",
                ),
                rx.badge(rx.text("记录数 "), AdminAuditState.log_count, color_scheme="gray"),
                _audit_table(),
                spacing="5",
                width="100%",
                max_width="100em",
            ),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ),
    )
