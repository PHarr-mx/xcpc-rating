"""Admin 选手管理页：列表、筛选与弹窗表单。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.admin.players import AdminPlayersState


def _error(field: str, message) -> rx.Component:
    return rx.cond(
        message != "",
        rx.text(message, color_scheme="red", size="1"),
        rx.fragment(),
    )


def _feedback() -> rx.Component:
    return rx.cond(
        AdminPlayersState.admin_error != "",
        rx.callout(
            AdminPlayersState.admin_error,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
        rx.cond(
            AdminPlayersState.admin_feedback != "",
            rx.callout(
                AdminPlayersState.admin_feedback,
                icon="check",
                color_scheme="green",
                role="status",
                width="100%",
            ),
        ),
    )


def _field(label: str, control: rx.Component, error) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium"),
        control,
        _error(label, error),
        align="stretch",
        spacing="1",
        width="100%",
    )


def _player_form() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(AdminPlayersState.form_title),
            rx.dialog.description(
                "创建或编辑选手资料。姓名、年级和状态由管理员维护。",
                size="2",
            ),
            rx.vstack(
                _field(
                    "ID",
                    rx.input(
                        value=AdminPlayersState.form_id,
                        on_change=AdminPlayersState.set_form_id,
                        placeholder="留空自动生成（如 p025）",
                        disabled=AdminPlayersState.editing_player_id != "",
                        width="100%",
                    ),
                    AdminPlayersState.general_error,
                ),
                _field(
                    "姓名",
                    rx.input(
                        value=AdminPlayersState.form_name,
                        on_change=AdminPlayersState.set_form_name,
                        placeholder="真实姓名",
                        width="100%",
                    ),
                    AdminPlayersState.name_error,
                ),
                rx.hstack(
                    _field(
                        "校内简称 / Handle",
                        rx.input(
                            value=AdminPlayersState.form_handle,
                            on_change=AdminPlayersState.set_form_handle,
                            placeholder="可留空",
                            width="100%",
                        ),
                        AdminPlayersState.handle_error,
                    ),
                    _field(
                        "入学年",
                        rx.input(
                            value=AdminPlayersState.form_grade,
                            on_change=AdminPlayersState.set_form_grade,
                            placeholder="留空表示未设置",
                            type="number",
                            width="100%",
                        ),
                        AdminPlayersState.grade_error,
                    ),
                    align="start",
                    width="100%",
                    spacing="3",
                ),
                _field(
                    "状态",
                    rx.select(
                        ["active", "retired", "left"],
                        value=AdminPlayersState.form_status,
                        on_change=AdminPlayersState.set_form_status,
                        width="100%",
                    ),
                    AdminPlayersState.status_error,
                ),
                _field(
                    "别名",
                    rx.text_area(
                        value=AdminPlayersState.form_aliases,
                        on_change=AdminPlayersState.set_form_aliases,
                        placeholder="每行一个，也可用逗号分隔",
                        rows="3",
                        width="100%",
                    ),
                    AdminPlayersState.aliases_error,
                ),
                _field(
                    "OJ 账号",
                    rx.text_area(
                        value=AdminPlayersState.form_oj_accounts,
                        on_change=AdminPlayersState.set_form_oj_accounts,
                        placeholder="每行一个，例如：codeforces:tourist",
                        rows="4",
                        width="100%",
                    ),
                    AdminPlayersState.oj_accounts_error,
                ),
                rx.hstack(
                    rx.spacer(),
                    rx.button("取消", variant="soft", on_click=AdminPlayersState.close_form),
                    rx.button("保存", color_scheme="green", on_click=AdminPlayersState.save_player),
                    width="100%",
                    justify="end",
                    spacing="2",
                ),
                align="stretch",
                spacing="3",
                width="100%",
            ),
            max_width="36em",
        ),
        open=AdminPlayersState.form_open,
    )


def _players_table() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.cond(
                AdminPlayersState.players.length() > 0,
                rx.scroll_area(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("ID"),
                                rx.table.column_header_cell("姓名"),
                                rx.table.column_header_cell("Handle"),
                                rx.table.column_header_cell("年级"),
                                rx.table.column_header_cell("状态"),
                                rx.table.column_header_cell("别名 / OJ 账号"),
                                rx.table.column_header_cell("操作"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(
                                AdminPlayersState.players,
                                lambda p: rx.table.row(
                                    rx.table.cell(p["id"]),
                                    rx.table.cell(p["name"]),
                                    rx.table.cell(p["handle"]),
                                    rx.table.cell(p["grade_label"]),
                                    rx.table.cell(
                                        rx.badge(
                                            p["status_label"],
                                            color_scheme=rx.match(
                                                p["status"],
                                                ("active", "green"),
                                                ("retired", "orange"),
                                                ("left", "gray"),
                                                "gray",
                                            ),
                                        )
                                    ),
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.text(p["aliases"], size="1"),
                                            rx.text(p["oj_accounts"], size="1", color_scheme="gray"),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(
                                        rx.hstack(
                                            rx.button(
                                                "编辑",
                                                size="1",
                                                variant="soft",
                                                on_click=AdminPlayersState.open_edit(p["id"]),
                                            ),
                                            rx.cond(
                                                p["status"] != "left",
                                                rx.button(
                                                    "标记离队",
                                                    size="1",
                                                    variant="ghost",
                                                    color_scheme="red",
                                                    on_click=AdminPlayersState.mark_player_left(p["id"]),
                                                ),
                                                rx.text("已离队", size="1", color_scheme="gray"),
                                            ),
                                            spacing="2",
                                        )
                                    ),
                                ),
                            ),
                        ),
                        width="100%",
                    ),
                    type="auto",
                    scrollbars="horizontal",
                    width="100%",
                ),
                rx.text("没有符合条件的选手", color_scheme="gray", size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def admin_players() -> rx.Component:
    """``/admin/players`` 选手 CRUD 页面。"""
    return page_shell(
        rx.cond(
            AdminPlayersState.is_admin,
            rx.vstack(
                rx.hstack(
                    rx.vstack(
                        rx.heading("选手管理", size="7"),
                        rx.text("通过 Web 管理选手名册；标记离队会保留历史记录。", size="2", color_scheme="gray"),
                        align="start",
                        spacing="1",
                    ),
                    rx.spacer(),
                    rx.button("新建选手", color_scheme="green", on_click=AdminPlayersState.open_create),
                    width="100%",
                    align="center",
                ),
                _feedback(),
                rx.hstack(
                    rx.input(
                        value=AdminPlayersState.search,
                        on_change=AdminPlayersState.set_search,
                        placeholder="搜索 ID、姓名、Handle、别名或 OJ 账号",
                        width="100%",
                    ),
                    rx.select(
                        ["all", "active", "retired", "left"],
                        value=AdminPlayersState.status_filter,
                        on_change=AdminPlayersState.set_status_filter,
                        width="10em",
                    ),
                    rx.input(
                        value=AdminPlayersState.grade_filter,
                        on_change=AdminPlayersState.set_grade_filter,
                        placeholder="年级",
                        type="number",
                        width="8em",
                    ),
                    width="100%",
                    spacing="3",
                ),
                rx.hstack(
                    rx.badge(rx.text("现役 "), AdminPlayersState.active_count, color_scheme="green"),
                    rx.badge(rx.text("退役 "), AdminPlayersState.retired_count, color_scheme="orange"),
                    rx.badge(rx.text("离队 "), AdminPlayersState.left_count, color_scheme="gray"),
                    spacing="2",
                ),
                _players_table(),
                _player_form(),
                spacing="5",
                width="100%",
                max_width="90em",
            ),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ),
    )
