"""Admin 比赛管理页：统一创建表单 + 列表与删除。"""

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


def _create_form() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("创建比赛", size="5"),
            rx.text(
                "统一入口：所有比赛（正式赛 / 训练赛 / 积分场）都从这里创建；"
                "成绩数据随后由管理员导入或选手申报进入。"
                "「仅按奖项」适用于未公开完整排名的比赛，强制不进排名。",
                size="2",
                color_scheme="gray",
            ),
            rx.hstack(
                rx.input(
                    value=AdminContestsState.form_contest_id,
                    on_change=AdminContestsState.set_form_contest_id,
                    placeholder="比赛 ID（如 2026_school）",
                    width="40%",
                ),
                rx.input(
                    value=AdminContestsState.form_title,
                    on_change=AdminContestsState.set_form_title,
                    placeholder="比赛名称",
                    width="60%",
                ),
                width="100%",
                spacing="3",
            ),
            rx.hstack(
                rx.input(
                    value=AdminContestsState.form_date,
                    on_change=AdminContestsState.set_form_date,
                    placeholder="比赛日期",
                    type="date",
                    width="34%",
                ),
                rx.select(
                    ["icpc", "ioi"],
                    value=AdminContestsState.form_format,
                    on_change=AdminContestsState.set_form_format,
                    width="22%",
                ),
                rx.select(
                    ["team", "player"],
                    value=AdminContestsState.form_entity,
                    on_change=AdminContestsState.set_form_entity,
                    width="22%",
                ),
                rx.select(
                    AdminContestsState.tier_options,
                    value=AdminContestsState.form_tier,
                    on_change=AdminContestsState.set_form_tier,
                    placeholder="赛事等级",
                    width="22%",
                ),
                width="100%",
                spacing="3",
            ),
            rx.hstack(
                rx.input(
                    value=AdminContestsState.form_n_teams,
                    on_change=AdminContestsState.set_form_n_teams,
                    placeholder="参赛实体数（队数/人数）",
                    width="34%",
                ),
                rx.input(
                    value=AdminContestsState.form_max_value,
                    on_change=AdminContestsState.set_form_max_value,
                    placeholder="全场最高解题数/得分",
                    width="33%",
                ),
                rx.select(
                    ["formula", "award_only"],
                    value=AdminContestsState.form_scoring,
                    on_change=AdminContestsState.set_form_scoring,
                    width="33%",
                ),
                width="100%",
                spacing="3",
            ),
            rx.hstack(
                rx.tooltip(
                    rx.checkbox(
                        "计入积分",
                        checked=AdminContestsState.form_counts_for_points,
                        on_change=AdminContestsState.set_form_counts_for_points,
                    ),
                    content="认证/导入的积分流水是否记入积分榜",
                ),
                rx.tooltip(
                    rx.checkbox(
                        "计入排名",
                        checked=AdminContestsState.form_counts_for_ranking,
                        on_change=AdminContestsState.set_form_counts_for_ranking,
                    ),
                    content="成绩是否进入 Rating 重放（需完整名次数据）",
                ),
                rx.tooltip(
                    rx.checkbox(
                        "允许选手申报",
                        checked=AdminContestsState.form_allow_claims,
                        on_change=AdminContestsState.set_form_allow_claims,
                    ),
                    content="关闭后仅管理员导入数据",
                ),
                rx.spacer(),
                rx.button("创建比赛", on_click=AdminContestsState.create_contest, size="3"),
                width="100%",
                spacing="5",
                align="center",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
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
                                rx.table.column_header_cell("赛制 / 形式"),
                                rx.table.column_header_cell("计分"),
                                rx.table.column_header_cell("规模"),
                                rx.table.column_header_cell("积分 / 排名"),
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
                                                f'{contest["date"]} · {contest["season"]}',
                                                size="1",
                                                color_scheme="gray",
                                            ),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.text(contest["format_label"]),
                                            rx.badge(contest["entity_label"], color_scheme="blue"),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.badge(
                                                contest["scoring_label"],
                                                color_scheme=rx.cond(
                                                    contest["scoring_label"] == "仅按奖项", "orange", "gray"
                                                ),
                                            ),
                                            rx.text(f'申报：{contest["allow_claims"]}', size="1",
                                                    color_scheme="gray"),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(
                                        rx.vstack(
                                            rx.text(f'实体数：{contest["n_teams"]}'),
                                            rx.text(f'最高值：{contest["max_value"]}', size="1",
                                                    color_scheme="gray"),
                                            align="start",
                                            spacing="1",
                                        )
                                    ),
                                    rx.table.cell(
                                        rx.hstack(
                                            rx.badge(
                                                contest["counts_for_points"],
                                                color_scheme=rx.cond(
                                                    contest["counts_for_points"] == "计入", "green", "gray"
                                                ),
                                            ),
                                            rx.badge(
                                                contest["counts_for_ranking"],
                                                color_scheme=rx.cond(
                                                    contest["counts_for_ranking"] == "计入", "violet", "gray"
                                                ),
                                            ),
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
                            "统一创建与管理所有比赛；删除会经 core contest API 清理成绩数据。",
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
                _create_form(),
                rx.hstack(
                    rx.input(
                        value=AdminContestsState.search,
                        on_change=AdminContestsState.set_search,
                        placeholder="搜索比赛 ID、标题、赛制或赛季",
                        width="100%",
                    ),
                    rx.badge(rx.text("全部 "), AdminContestsState.contest_count, color_scheme="gray"),
                    rx.badge(rx.text("计积分 "), AdminContestsState.points_count, color_scheme="green"),
                    rx.badge(rx.text("计排名 "), AdminContestsState.ranking_count, color_scheme="violet"),
                    width="100%",
                    spacing="3",
                    align="center",
                ),
                _contests_table(),
                spacing="5",
                width="100%",
                max_width="100em",
            ),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ), section="admin", subsection="contests")
