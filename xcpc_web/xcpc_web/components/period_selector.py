"""周期选择器组件。"""

import reflex as rx
from ..states.board import BoardState


def period_selector() -> rx.Component:
    """周期选择器组件。"""
    return rx.hstack(
        # 模式选择
        rx.select.root(
            rx.select.trigger(placeholder="选择模式"),
            rx.select.content(
                rx.select.item("全部比赛", value="all"),
                rx.select.item("仅正式赛", value="formal_only"),
            ),
            value=BoardState.mode,
            on_change=BoardState.set_mode,
            width="150px",
        ),
        # 周期类型选择
        rx.select.root(
            rx.select.trigger(placeholder="选择周期"),
            rx.select.content(
                rx.select.item("生涯", value="career"),
                rx.select.item("赛年", value="competition_year"),
                rx.select.item("赛季", value="season"),
            ),
            value=BoardState.period_type,
            on_change=lambda value: BoardState.set_period(value),
            width="120px",
        ),
        # 搜索框
        rx.input(
            placeholder="搜索选手ID或姓名",
            value=BoardState.search,
            on_change=BoardState.set_search,
            width="200px",
        ),
        spacing="3",
    )