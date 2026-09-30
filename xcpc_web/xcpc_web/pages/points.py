"""积分页（/points）：提交认证 + 我的认证 + 个人/队伍积分榜。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.points import PointsState


def _feedback() -> rx.Component:
    return rx.vstack(
        rx.cond(
            PointsState.claim_error != "",
            rx.callout(
                PointsState.claim_error,
                icon="triangle_alert",
                color_scheme="red",
                role="alert",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            PointsState.claim_feedback != "",
            rx.callout(
                PointsState.claim_feedback,
                icon="circle_check",
                color_scheme="green",
                width="100%",
            ),
            rx.fragment(),
        ),
        spacing="2",
        width="100%",
    )


def _submit_form() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("提交认证", size="5"),
            rx.text(
                "选择积分场次，填写解题数/得分与名次；队伍赛需先选择所属队伍（本人须为现役成员）。",
                size="2",
                color_scheme="gray",
            ),
            rx.select(
                PointsState.event_options,
                value=PointsState.claim_event_id,
                on_change=PointsState.set_claim_event_id,
                placeholder="选择积分场次",
                width="100%",
            ),
            rx.cond(
                PointsState.selected_is_team,
                rx.select(
                    PointsState.my_team_options,
                    value=PointsState.claim_team_id,
                    on_change=PointsState.set_claim_team_id,
                    placeholder="选择队伍",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.hstack(
                rx.input(
                    value=PointsState.claim_value,
                    on_change=PointsState.set_claim_value,
                    placeholder="解题数/得分（≥1）",
                    width="50%",
                ),
                rx.input(
                    value=PointsState.claim_rank,
                    on_change=PointsState.set_claim_rank,
                    placeholder="名次",
                    width="50%",
                ),
                width="100%",
                spacing="3",
            ),
            rx.input(
                value=PointsState.claim_note,
                on_change=PointsState.set_claim_note,
                placeholder="备注（可选，如成绩链接）",
                width="100%",
            ),
            rx.button("提交认证", on_click=PointsState.submit_claim, size="3"),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def _individual_board() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("个人积分榜", size="5"),
            rx.cond(
                PointsState.individual_board.length() > 0,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("#"),
                            rx.table.column_header_cell("选手"),
                            rx.table.column_header_cell("积分"),
                            rx.table.column_header_cell("认证场次"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            PointsState.individual_board,
                            lambda row: rx.table.row(
                                rx.table.cell(row["rank"]),
                                rx.table.cell(row["name"]),
                                rx.table.cell(row["points"]),
                                rx.table.cell(row["entry_count"]),
                            ),
                        ),
                    ),
                    width="100%",
                ),
                rx.text("暂无积分记录", color_scheme="gray", size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def _team_board() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("队伍积分榜", size="5"),
            rx.text(
                "复合分 = 0.6 × 团队积分 + 0.4 × 成员队外个人积分之和",
                size="2",
                color_scheme="gray",
            ),
            rx.cond(
                PointsState.team_board.length() > 0,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("#"),
                            rx.table.column_header_cell("队伍"),
                            rx.table.column_header_cell("成员"),
                            rx.table.column_header_cell("团队积分"),
                            rx.table.column_header_cell("成员履历"),
                            rx.table.column_header_cell("复合分"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            PointsState.team_board,
                            lambda row: rx.table.row(
                                rx.table.cell(row["rank"]),
                                rx.table.cell(row["name"]),
                                rx.table.cell(row["members"]),
                                rx.table.cell(row["team_points"]),
                                rx.table.cell(row["member_points"]),
                                rx.table.cell(rx.text(row["composite"], weight="bold")),
                            ),
                        ),
                    ),
                    width="100%",
                ),
                rx.text("暂无队伍积分记录", color_scheme="gray", size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def points_page() -> rx.Component:
    """``/points`` 积分页。"""
    return page_shell(
        rx.cond(
            PointsState.is_authenticated,
            rx.vstack(
                rx.vstack(
                    rx.heading("生涯积分", size="7"),
                    rx.text(
                        "积分 = 100 × (解题数/得分 ÷ 全场最高) × 名次百分位，只累加不衰减；"
                        "提交认证后由 admin 审核记分。",
                        size="2",
                        color_scheme="gray",
                    ),
                    align="start",
                    spacing="1",
                    width="100%",
                ),
                _feedback(),
                rx.cond(
                    PointsState.is_bound,
                    _submit_form(),
                    rx.callout(
                        "尚未绑定选手：绑定后才能提交认证（前往个人资料页绑定）。",
                        icon="info",
                        width="100%",
                    ),
                ),
                _individual_board(),
                _team_board(),
                spacing="5",
                width="100%",
                max_width="100em",
            ),
            rx.text("请先登录。", size="3", color_scheme="gray"),
        ), section="points", subsection="individual")
