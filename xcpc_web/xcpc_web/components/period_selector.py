"""周期选择器组件。"""

import reflex as rx
from ..states.board import BoardState


def period_selector() -> rx.Component:
    """周期选择器组件（比赛统一化后榜单只有单一口径，模式选择已移除）。"""
    return rx.hstack(
        # 具体周期下拉：生涯 / 2025赛年 / 2025-秋学期 …（选项来自数据覆盖范围）
        rx.select.root(
            rx.select.trigger(placeholder="选择周期"),
            rx.select.content(
                rx.foreach(
                    BoardState.period_options,
                    lambda opt: rx.select.item(opt["label"], value=opt["label"]),
                ),
            ),
            value=BoardState.period_value_label,
            on_change=BoardState.set_period_option_sync_url,
            width="170px",
        ),
        # 搜索框
        rx.input(
            placeholder="搜索选手ID或姓名",
            value=BoardState.search,
            on_change=BoardState.set_search_sync_url,
            width="200px",
        ),
        spacing="3",
    )