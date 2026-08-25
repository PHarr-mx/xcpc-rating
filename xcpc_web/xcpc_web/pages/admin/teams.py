"""Admin 队伍管理页：列表、搜索与弹窗表单。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.admin.teams import AdminTeamsState


def _error(message) -> rx.Component:
    return rx.cond(
        message != "",
        rx.text(message, color_scheme="red", size="1"),
        rx.fragment(),
    )


def _feedback() -> rx.Component:
    return rx.cond(
        AdminTeamsState.admin_error != "",
        rx.callout(
            AdminTeamsState.admin_error,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
        rx.cond(
            AdminTeamsState.admin_feedback != "",
            rx.callout(
                AdminTeamsState.admin_feedback,
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
        _error(error),
        align="stretch",
        spacing="1",
        width="100%",
    )


def _team_form() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(AdminTeamsState.form_title),
            rx.dialog.description(AdminTeamsState.form_description, size="2"),
            rx.vstack(
                _field(
                    "ID",
                    rx.input(
                        value=AdminTeamsState.form_id,
                        on_change=AdminTeamsState.set_form_id,
                        placeholder="留空自动生成（如 t009）",
                        disabled=AdminTeamsState.editing_team_id != "",
                        width="100%",
                    ),
                    AdminTeamsState.id_error,
                ),
                _field(
                    "成员 player_id",
                    rx.text_area(
                        value=AdminTeamsState.form_members_text,
                        on_change=AdminTeamsState.set_form_members_text,
                        placeholder="例如：p001,p002,p003（每行一个也可以）",
                        rows="3",
                        disabled=AdminTeamsState.editing_team_id != "",
                        width="100%",
                    ),
                    AdminTeamsState.members_error,
                ),
                _field(
                    "队名 / 别名",
                    rx.text_area(
                        value=AdminTeamsState.form_aliases_text,
                        on_change=AdminTeamsState.set_form_aliases_text,
                        placeholder="每行一个，也可用逗号分隔",
                        rows="3",
                        width="100%",
                    ),
                    AdminTeamsState.aliases_error,
                ),
                _error(AdminTeamsState.general_error),
                rx.hstack(
                    rx.spacer(),
                    rx.button("取消", variant="soft", on_click=AdminTeamsState.close_form),
                    rx.button("保存", color_scheme="green", on_click=AdminTeamsState.save_team),
                    spacing="2",
                    width="100%",
                ),
                align="stretch",
                spacing="3",
                width="100%",
            ),
            max_width="36em",
            width="100%",
        ),
        open=AdminTeamsState.form_open,
    )


def _teams_table() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.cond(
                AdminTeamsState.teams.length() > 0,
                rx.scroll_area(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("ID"),
                                rx.table.column_header_cell("成员"),
                                rx.table.column_header_cell("member_key"),
                                rx.table.column_header_cell("别名"),
                                rx.table.column_header_cell("操作"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(
                                AdminTeamsState.teams,
                                lambda team: rx.table.row(
                                    rx.table.cell(team["id"]),
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.text(team["member_names"], size="2"),
                                            rx.text(f'{team["size"]} 人', size="1", color_scheme="gray"),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(rx.code(team["member_key"])),
                                    rx.table.cell(team["aliases"]),
                                    rx.table.cell(
                                        rx.hstack(
                                            rx.button(
                                                "编辑别名",
                                                size="1",
                                                variant="soft",
                                                on_click=AdminTeamsState.open_edit(team["id"]),
                                            ),
                                            rx.button(
                                                "删除",
                                                size="1",
                                                variant="ghost",
                                                color_scheme="red",
                                                on_click=AdminTeamsState.delete_team(team["id"]),
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
                rx.text("没有符合条件的队伍", color_scheme="gray", size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def admin_teams() -> rx.Component:
    """``/admin/teams`` 队伍 CRUD 页面。"""
    return page_shell(
        rx.cond(
            AdminTeamsState.is_admin,
            rx.vstack(
                rx.hstack(
                    rx.vstack(
                        rx.heading("队伍管理", size="7"),
                        rx.text(
                            "按成员集合管理队伍；换员请新建队伍，已有队伍可追加别名。",
                            size="2",
                            color_scheme="gray",
                        ),
                        align="start",
                        spacing="1",
                    ),
                    rx.spacer(),
                    rx.button("新建队伍", color_scheme="green", on_click=AdminTeamsState.open_create),
                    width="100%",
                    align="center",
                ),
                _feedback(),
                rx.hstack(
                    rx.input(
                        value=AdminTeamsState.search,
                        on_change=AdminTeamsState.set_search,
                        placeholder="搜索队伍 ID、成员 ID、姓名、member_key 或别名",
                        width="100%",
                    ),
                    rx.badge(rx.text("共 "), AdminTeamsState.team_count, rx.text(" 支"), color_scheme="gray"),
                    width="100%",
                    spacing="3",
                    align="center",
                ),
                _teams_table(),
                _team_form(),
                spacing="5",
                width="100%",
                max_width="90em",
            ),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ),
    )
