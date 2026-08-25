"""Admin 比赛管理页：按来源筛选、搜索与删除。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.admin.contests import AdminContestsState


def _feedback() -> rx.Component:
    return rx.cond(
        AdminContestsState.admin_error != "",
        rx.callout(
            AdminContestsState.admin_error,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
        rx.cond(
            AdminContestsState.admin_feedback != "",
            rx.callout(
                AdminContestsState.admin_feedback,
                icon="check",
                color_scheme="green",
                role="status",
                width="100%",
            ),
        ),
    )


def _contests_table() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.cond(
                AdminContestsState.contests.length() > 0,
                rx.scroll_area(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("比赛"),
                                rx.table.column_header_cell("日期 / 来源"),
                                rx.table.column_header_cell("赛制"),
                                rx.table.column_header_cell("规模"),
                                rx.table.column_header_cell("Rating"),
                                rx.table.column_header_cell("操作"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(
                                AdminContestsState.contests,
                                lambda contest: rx.table.row(
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.text(contest["title"], weight="medium"),
                                            rx.text(contest["id"], size="1", color_scheme="gray"),
                                            rx.text(
                                                f'{contest["season"]} · {contest["contest_type"]}',
                                                size="1",
                                                color_scheme="gray",
                                            ),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.text(contest["date"]),
                                            rx.badge(contest["source_label"], color_scheme="blue"),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(contest["format"]),
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.text(f'总计：{contest["total_teams"]}'),
                                            rx.text(f'本校：{contest["school_teams_count"]}', size="1", color_scheme="gray"),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.text(contest["rated"]),
                                            rx.text(f'权重 {contest["weight"]}', size="1", color_scheme="gray"),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(
                                        rx.button(
                                            "删除",
                                            size="1",
                                            variant="ghost",
                                            color_scheme="red",
                                            on_click=AdminContestsState.delete_contest(contest["id"]),
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
                rx.text("没有符合条件的比赛", color_scheme="gray", size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def admin_contests() -> rx.Component:
    """``/admin/contests`` 比赛管理页面。"""
    return page_shell(
        rx.cond(
            AdminContestsState.is_admin,
            rx.vstack(
                rx.hstack(
                    rx.vstack(
                        rx.heading("比赛管理", size="7"),
                        rx.text(
                            "查看正式赛与训练赛记录；删除比赛会经 core contest API 清理成绩数据。",
                            size="2",
                            color_scheme="gray",
                        ),
                        align="start",
                        spacing="1",
                    ),
                    width="100%",
                    align="center",
                ),
                _feedback(),
                rx.hstack(
                    rx.input(
                        value=AdminContestsState.search,
                        on_change=AdminContestsState.set_search,
                        placeholder="搜索比赛 ID、标题、类型、赛季或来源文件",
                        width="100%",
                    ),
                    rx.select(
                        ["all", "formal", "training"],
                        value=AdminContestsState.source_filter,
                        on_change=AdminContestsState.set_source_filter,
                        width="9em",
                    ),
                    width="100%",
                    spacing="3",
                ),
                rx.hstack(
                    rx.badge(rx.text("全部 "), AdminContestsState.contest_count, color_scheme="gray"),
                    rx.badge(rx.text("正式赛 "), AdminContestsState.formal_count, color_scheme="blue"),
                    rx.badge(rx.text("训练赛 "), AdminContestsState.training_count, color_scheme="green"),
                    spacing="2",
                ),
                _contests_table(),
                spacing="5",
                width="100%",
                max_width="100em",
            ),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ),
    )
