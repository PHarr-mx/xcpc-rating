"""Rating 累计曲线组件。

用 Reflex 内置的 recharts（零新增依赖）替代原计划的
``reflex-components-plotly``——对单条折线足够，且避免额外产物体积
（原 plotly 方案即因体积原因限定仅详情页引入）。
"""

import reflex as rx


def rating_chart(points: list[dict]) -> rx.Component:
    """累计 Rating 折线。``points`` 按日期升序：``{"date": "2026-03-15", "rating_after": 1250.0}``。"""
    return rx.box(
        rx.recharts.line_chart(
            rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
            rx.recharts.line(
                data_key="rating_after",
                stroke="#3182ce",
                stroke_width=2,
                dot=False,
            ),
            rx.recharts.x_axis(data_key="date", tick_font_size=11),
            rx.recharts.y_axis(tick_font_size=11),
            rx.recharts.tooltip(),
            data=points,
            height=280,
            margin={"top": 8, "right": 16, "bottom": 8, "left": 8},
        ),
        width="100%",
    )
