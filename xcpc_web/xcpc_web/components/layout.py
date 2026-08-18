"""布局组件。"""

import reflex as rx


def page_shell(*children) -> rx.Component:
    """页面外壳：导航 + 内容 + 页脚。"""
    return rx.box(
        # 导航栏
        rx.hstack(
            rx.heading("XCPC Rating", size="6"),
            rx.spacer(),
            rx.text("校内编程竞赛评级系统", size="2"),
            padding="1rem 2rem",
            border_bottom="1px solid #e2e8f0",
            background="white",
        ),
        # 内容
        rx.container(*children, padding="2rem 0"),
        # 页脚
        rx.box(
            rx.center(
                rx.text("© 2026 XCPC Rating System", size="1"),
                padding="1rem",
            ),
            border_top="1px solid #e2e8f0",
            margin_top="2rem",
        ),
        min_height="100vh",
    )