"""Admin 积分管理页（/admin/points）：场次配置 + 认证审批。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.admin.points import AdminPointsState


def _feedback() -> rx.Component:
    return rx.vstack(
        rx.cond(
            AdminPointsState.admin_error != "",
            rx.callout(
                AdminPointsState.admin_error,
                icon="triangle_alert",
                color_scheme="red",
                role="alert",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            AdminPointsState.admin_feedback != "",
            rx.callout(
                AdminPointsState.admin_feedback,
                icon="circle_check",
                color_scheme="green",
                width="100%",
            ),
            rx.fragment(),
        ),
        spacing="2",
        width="100%",
    )


def _create_form() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("创建积分场次", size="5"),
            rx.text(
                "max_value = 全场最高解题数/得分，n_teams = 参赛实体数；"
                "两者与认证内容一起决定积分：100 × (value/max_value) × 名次百分位。",
                size="2",
                color_scheme="gray",
            ),
            rx.input(
                value=AdminPointsState.form_title,
                on_change=AdminPointsState.set_form_title,
                placeholder="场次名称",
                width="100%",
            ),
            rx.hstack(
                rx.input(
                    value=AdminPointsState.form_date,
                    on_change=AdminPointsState.set_form_date,
                    placeholder="比赛日期",
                    type="date",
                    width="50%",
                ),
                rx.select(
                    ["player", "team"],
                    value=AdminPointsState.form_entity,
                    on_change=AdminPointsState.set_form_entity,
                    width="25%",
                ),
                rx.select(
                    ["solved", "score"],
                    value=AdminPointsState.form_kind,
                    on_change=AdminPointsState.set_form_kind,
                    width="25%",
                ),
                width="100%",
                spacing="3",
            ),
            rx.hstack(
                rx.input(
                    value=AdminPointsState.form_max_value,
                    on_change=AdminPointsState.set_form_max_value,
                    placeholder="全场最高值",
                    width="50%",
                ),
                rx.input(
                    value=AdminPointsState.form_n_teams,
                    on_change=AdminPointsState.set_form_n_teams,
                    placeholder="参赛实体数",
                    width="50%",
                ),
                width="100%",
                spacing="3",
            ),
            rx.button("创建场次", on_click=AdminPointsState.create_event, size="3"),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def _events_table() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("场次列表", size="5"),
            rx.cond(
                AdminPointsState.events.length() > 0,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("#"),
                            rx.table.column_header_cell("名称"),
                            rx.table.column_header_cell("日期"),
                            rx.table.column_header_cell("类型"),
                            rx.table.column_header_cell("计分"),
                            rx.table.column_header_cell("最高值"),
                            rx.table.column_header_cell("实体数"),
                            rx.table.column_header_cell("待审/总数"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            AdminPointsState.events,
                            lambda event: rx.table.row(
                                rx.table.cell(event["id"]),
                                rx.table.cell(event["title"]),
                                rx.table.cell(event["date_label"]),
                                rx.table.cell(event["entity_label"]),
                                rx.table.cell(event["kind_label"]),
                                rx.table.cell(event["max_value"]),
                                rx.table.cell(event["n_teams"]),
                                rx.table.cell(
                                    rx.hstack(
                                        rx.text(event["claims_staged"], weight="bold"),
                                        rx.text(f' / {event["claims_total"]}'),
                                        spacing="1",
                                    )
                                ),
                            ),
                        ),
                    ),
                    width="100%",
                ),
                rx.text("还没有积分场次", color_scheme="gray", size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def _claims_table() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("待审认证", size="5"),
                rx.badge(AdminPointsState.pending_count, color_scheme="orange"),
                spacing="3",
            ),
            rx.cond(
                AdminPointsState.staged_claims.length() > 0,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("#"),
                            rx.table.column_header_cell("场次"),
                            rx.table.column_header_cell("类型"),
                            rx.table.column_header_cell("队伍/选手"),
                            rx.table.column_header_cell("解题/得分"),
                            rx.table.column_header_cell("名次"),
                            rx.table.column_header_cell("备注"),
                            rx.table.column_header_cell("操作"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            AdminPointsState.staged_claims,
                            lambda claim: rx.table.row(
                                rx.table.cell(claim["id"]),
                                rx.table.cell(claim["event_title"]),
                                rx.table.cell(claim["entity_label"]),
                                rx.table.cell(claim["owner_label"]),
                                rx.table.cell(claim["value"]),
                                rx.table.cell(claim["rank"]),
                                rx.table.cell(claim["note"]),
                                rx.table.cell(
                                    rx.hstack(
                                        rx.button(
                                            "通过",
                                            size="1",
                                            color_scheme="green",
                                            on_click=lambda: AdminPointsState.approve(
                                                claim["id"]
                                            ),
                                        ),
                                        rx.button(
                                            "驳回",
                                            size="1",
                                            color_scheme="red",
                                            on_click=lambda: AdminPointsState.reject(
                                                claim["id"]
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
                rx.text("没有待审认证", color_scheme="gray", size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def admin_points() -> rx.Component:
    """``/admin/points`` 积分管理页面。"""
    return page_shell(
        rx.cond(
            AdminPointsState.is_admin,
            rx.vstack(
                rx.vstack(
                    rx.heading("积分管理", size="7"),
                    rx.text(
                        "配置积分场次并审批选手/队伍提交的认证；通过即按公式记入积分。",
                        size="2",
                        color_scheme="gray",
                    ),
                    align="start",
                    spacing="1",
                    width="100%",
                ),
                _feedback(),
                _create_form(),
                _events_table(),
                _claims_table(),
                spacing="5",
                width="100%",
                max_width="100em",
            ),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ),
    )
