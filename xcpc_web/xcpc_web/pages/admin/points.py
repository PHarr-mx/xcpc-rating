"""Admin 积分认证页（/admin/points）：选手/队伍申报的审批。

场次创建已并入 /admin/contests 统一比赛表单；本页只负责审批，
通过即按比赛计分方式（formula / award_only）× 等级系数记入积分。
"""

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
                            rx.table.column_header_cell("比赛"),
                            rx.table.column_header_cell("类型"),
                            rx.table.column_header_cell("队伍/选手"),
                            rx.table.column_header_cell("申报内容"),
                            rx.table.column_header_cell("备注"),
                            rx.table.column_header_cell("操作"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            AdminPointsState.staged_claims,
                            lambda claim: rx.table.row(
                                rx.table.cell(claim["id"]),
                                rx.table.cell(claim["contest_title"]),
                                rx.table.cell(claim["entity_label"]),
                                rx.table.cell(claim["owner_label"]),
                                rx.table.cell(
                                    rx.badge(
                                        claim["result_label"],
                                        color_scheme=rx.cond(
                                            claim["scoring"] == "award_only", "orange", "blue"
                                        ),
                                    )
                                ),
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
    """``/admin/points`` 积分认证管理页面。"""
    return page_shell(
        rx.cond(
            AdminPointsState.is_admin,
            rx.vstack(
                rx.vstack(
                    rx.heading("积分认证", size="7"),
                    rx.text(
                        "审批选手/队伍提交的认证；通过即按比赛的计分方式与赛事等级系数记入积分。"
                        "比赛（场次）的创建与配置在「比赛管理」页。",
                        size="2",
                        color_scheme="gray",
                    ),
                    align="start",
                    spacing="1",
                    width="100%",
                ),
                _feedback(),
                _claims_table(),
                spacing="5",
                width="100%",
                max_width="100em",
            ),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ), section="admin", subsection="points")
