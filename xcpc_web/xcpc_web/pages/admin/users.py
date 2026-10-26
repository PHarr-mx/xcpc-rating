"""Admin 用户与绑定审批页：待审批列表 + 用户列表。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.admin.users import AdminUsersState


def _feedback() -> rx.Component:
    """操作反馈提示条。"""
    return rx.cond(
        AdminUsersState.admin_error != "",
        rx.callout(
            AdminUsersState.admin_error,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
        rx.cond(
            AdminUsersState.admin_feedback != "",
            rx.callout(
                AdminUsersState.admin_feedback,
                icon="check",
                color_scheme="green",
                role="status",
                width="100%",
            ),
        ),
    )


def _pending_table() -> rx.Component:
    """待审批绑定申请表。"""
    return rx.card(
        rx.vstack(
            rx.heading("待审批绑定", size="5"),
            rx.cond(
                AdminUsersState.pending_requests.length() > 0,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("申请人"),
                            rx.table.column_header_cell("目标选手"),
                            rx.table.column_header_cell("说明"),
                            rx.table.column_header_cell("申请时间"),
                            rx.table.column_header_cell("操作"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            AdminUsersState.pending_requests,
                            lambda r: rx.table.row(
                                rx.table.cell(r["username"]),
                                rx.table.cell(
                                    f'{r["player_name"]}（{r["player_id"]}）'
                                ),
                                rx.table.cell(r["reason"]),
                                rx.table.cell(r["created_at"]),
                                rx.table.cell(
                                    rx.hstack(
                                        rx.button(
                                            "批准",
                                            color_scheme="green",
                                            size="1",
                                            on_click=AdminUsersState.approve(
                                                r["request_id"]
                                            ),
                                        ),
                                        rx.button(
                                            "驳回",
                                            color_scheme="red",
                                            variant="soft",
                                            size="1",
                                            on_click=AdminUsersState.reject(
                                                r["request_id"]
                                            ),
                                        ),
                                        spacing="2",
                                    )
                                ),
                            ),
                        ),
                    ),
                    width="100%",
                ),
                rx.text("暂无待审批的绑定申请", color_scheme="gray", size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def _users_table() -> rx.Component:
    """用户列表（只读）。"""
    return rx.card(
        rx.vstack(
            rx.heading("用户", size="5"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("用户名"),
                        rx.table.column_header_cell("角色"),
                        rx.table.column_header_cell("绑定选手"),
                        rx.table.column_header_cell("注册时间"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        AdminUsersState.users,
                        lambda u: rx.table.row(
                            rx.table.cell(u["username"]),
                            rx.table.cell(u["role"]),
                            rx.table.cell(
                                rx.cond(
                                    u["bound_player_id"] != "",
                                    f'{u["bound_player_name"]}（{u["bound_player_id"]}）',
                                    "—",
                                )
                            ),
                            rx.table.cell(u["created_at"]),
                        ),
                    ),
                ),
                width="100%",
            ),
            width="100%",
        ),
        width="100%",
    )


def _batch_create() -> rx.Component:
    """批量建号（五期：不允许自助注册，账号由管理员统一创建）。"""
    return rx.card(
        rx.vstack(
            rx.heading("批量创建账号", size="5"),
            rx.text(
                "系统不开放自助注册。每行一个账号，格式：用户名[,初始密码][,绑定选手ID]。"
                "密码留空则用下方默认初始密码；绑定选手可选（须未被他人绑定）。"
                "以 # 开头的行会被忽略。逐行独立处理——某行失败不影响其他行。",
                size="2",
                color_scheme="gray",
            ),
            rx.text_area(
                value=AdminUsersState.batch_text,
                on_change=AdminUsersState.set_batch_text,
                placeholder=(
                    "zhangsan,Passw0rd,p001\n"
                    "lisi                    # 用默认密码\n"
                    "wangwu,Passw0rd"
                ),
                rows="7",
                width="100%",
                font_family="monospace",
            ),
            rx.hstack(
                rx.input(
                    value=AdminUsersState.batch_default_password,
                    on_change=AdminUsersState.set_batch_default_password,
                    placeholder="默认初始密码（≥6 位，未逐行指定时使用）",
                    type="password",
                    width="24em",
                ),
                rx.button(
                    "批量创建",
                    on_click=AdminUsersState.submit_batch,
                    color_scheme="green",
                ),
                rx.button(
                    "清空",
                    on_click=AdminUsersState.clear_batch,
                    variant="ghost",
                ),
                spacing="3",
                wrap="wrap",
                align="center",
            ),
            rx.cond(
                AdminUsersState.batch_rows.length() > 0,
                rx.vstack(
                    rx.separator(size="4"),
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("输入行"),
                                rx.table.column_header_cell("用户名"),
                                rx.table.column_header_cell("结果", width="80px"),
                                rx.table.column_header_cell("说明"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                AdminUsersState.batch_rows,
                                lambda row: rx.table.row(
                                    rx.table.cell(
                                        rx.code(row["line"]), size="1"
                                    ),
                                    rx.table.cell(row["username"]),
                                    rx.table.cell(
                                        rx.badge(
                                            row["label"],
                                            color_scheme=row["tone"],
                                            variant="soft",
                                        )
                                    ),
                                    rx.table.cell(row["message"], size="1"),
                                ),
                            )
                        ),
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.fragment(),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def admin_users() -> rx.Component:
    """/admin/users 用户与绑定审批页。"""
    return page_shell(
        rx.cond(
            AdminUsersState.is_admin,
            rx.vstack(
                rx.heading("用户与绑定审批", size="7"),
                _feedback(),
                _pending_table(),
                _batch_create(),
                _users_table(),
                spacing="6",
                width="100%",
                max_width="80em",
            ),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ), section="admin", subsection="users")
