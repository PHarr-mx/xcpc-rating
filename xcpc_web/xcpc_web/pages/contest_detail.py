"""比赛详情页 /contests/[contest_id]（P5）：formal/training 同页，按 format 切列。"""

import reflex as rx

from ..components.layout import page_shell
from ..components.standings_table import standings_table
from ..states.contest_detail import ContestDetailState


def contest_detail() -> rx.Component:
    return page_shell(
        rx.cond(
            ContestDetailState.not_found,
            rx.vstack(
                rx.heading("比赛不存在", size="7"),
                rx.text("该比赛 ID 没有对应的记录。", size="3", color=rx.color("gray", 10)),
                rx.link("返回榜单", href="/", size="2"),
                spacing="4",
                align_items="start",
            ),
            rx.cond(
                ContestDetailState.contest,
                rx.vstack(
                    rx.heading(ContestDetailState.contest["title"], size="7"),
                    rx.text(ContestDetailState.meta_line, size="3", color=rx.color("gray", 10)),
                    rx.heading("成绩", size="5"),
                    standings_table(ContestDetailState.standings, ContestDetailState.is_oi),
                    spacing="5",
                    width="100%",
                    align_items="start",
                ),
                rx.spacer(),
            ),
        )
    )
