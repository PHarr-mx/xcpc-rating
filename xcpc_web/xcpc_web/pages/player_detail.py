"""选手详情页 /players/[player_id]（P5）。"""

import reflex as rx

from ..components.layout import page_shell
from ..components.oj_link import oj_links
from ..components.rating_chart import rating_chart
from ..states.player_detail import PlayerDetailState


def _profile_header() -> rx.Component:
    return rx.hstack(
        rx.heading(PlayerDetailState.player["name"], size="7"),
        rx.text(PlayerDetailState.player["grade_label"], size="3", color=rx.color("gray", 10)),
        rx.text(PlayerDetailState.player["status_label"], size="3", color=rx.color("gray", 10)),
        rx.cond(
            PlayerDetailState.is_self,
            rx.link("编辑我的资料", href="/profile", size="2"),
        ),
        spacing="4",
        align_items="baseline",
        width="100%",
    )


def _records_table() -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("日期"),
                rx.table.column_header_cell("比赛"),
                rx.table.column_header_cell("名次"),
                rx.table.column_header_cell("解题/得分"),
                rx.table.column_header_cell("贡献"),
                rx.table.column_header_cell("累计 Rating"),
            ),
        ),
        rx.table.body(
            rx.foreach(
                PlayerDetailState.history,
                lambda r: rx.table.row(
                    rx.table.cell(r["date"]),
                    rx.table.cell(rx.cond(r["contest_title"], r["contest_title"], r["contest_id"])),
                    rx.table.cell(rx.cond(r["rank"], r["rank"], "—")),
                    rx.table.cell(
                        rx.cond(
                            r["solved"],
                            f'{r["solved"]} 题',
                            rx.cond(r["score"], f'{r["score"]} 分', "—"),
                        )
                    ),
                    rx.table.cell(f'{r["contribution"]:.1f}'),
                    rx.table.cell(f'{r["rating_after"]:.1f}'),
                ),
            )
        ),
        width="100%",
    )


def _detail_body() -> rx.Component:
    return rx.vstack(
        _profile_header(),
        oj_links(PlayerDetailState.oj_accounts),
        rx.cond(
            PlayerDetailState.history.length() > 0,
            rx.vstack(
                rx.heading("Rating 曲线", size="5"),
                rating_chart(PlayerDetailState.chart_points),
                rx.heading("参赛记录", size="5"),
                _records_table(),
                spacing="4",
                width="100%",
            ),
            rx.text("暂无参赛记录。", size="3", color=rx.color("gray", 10)),
        ),
        spacing="5",
        width="100%",
        align_items="start",
    )


def player_detail() -> rx.Component:
    return page_shell(
        rx.cond(
            PlayerDetailState.not_found,
            rx.vstack(
                rx.heading("选手不存在", size="7"),
                rx.text("该选手 ID 没有对应的档案。", size="3", color=rx.color("gray", 10)),
                rx.link("返回榜单", href="/", size="2"),
                spacing="4",
                align_items="start",
            ),
            rx.cond(
                PlayerDetailState.player,
                _detail_body(),
                rx.spacer(),
            ),
        )
    )
