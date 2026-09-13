"""成绩表组件：按 format 切列（docs/05 组件清单）。

行视图由 State 侧预算（姓名解析、打星标记、奖项中文）；xcpc 类
（team_xcpc / solo_xcpc）显示解题+罚时，OI 显示得分。
组件构建期两个分支都会求值，行数据来自同一来源。
"""

import reflex as rx


def _xcpc_table(rows) -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("名次"),
                rx.table.column_header_cell("队伍"),
                rx.table.column_header_cell("队员"),
                rx.table.column_header_cell("解题"),
                rx.table.column_header_cell("罚时"),
                rx.table.column_header_cell("校内名次"),
                rx.table.column_header_cell("奖项"),
            ),
        ),
        rx.table.body(
            rx.foreach(
                rows,
                lambda r: rx.table.row(
                    rx.table.cell(r["rank"]),
                    rx.table.cell(r["team_name"]),
                    rx.table.cell(r["members"]),
                    rx.table.cell(rx.cond(r["solved"], r["solved"], "—")),
                    rx.table.cell(rx.cond(r["penalty"], r["penalty"], "—")),
                    rx.table.cell(rx.cond(r["school_rank"], r["school_rank"], "—")),
                    rx.table.cell(rx.cond(r["award_label"], r["award_label"], "—")),
                ),
            )
        ),
        width="100%",
    )


def _oi_table(rows) -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("名次"),
                rx.table.column_header_cell("队员"),
                rx.table.column_header_cell("得分"),
                rx.table.column_header_cell("校内名次"),
                rx.table.column_header_cell("奖项"),
            ),
        ),
        rx.table.body(
            rx.foreach(
                rows,
                lambda r: rx.table.row(
                    rx.table.cell(r["rank"]),
                    rx.table.cell(r["members"]),
                    rx.table.cell(rx.cond(r["score"], r["score"], "—")),
                    rx.table.cell(rx.cond(r["school_rank"], r["school_rank"], "—")),
                    rx.table.cell(rx.cond(r["award_label"], r["award_label"], "—")),
                ),
            )
        ),
        width="100%",
    )


def standings_table(rows, is_oi) -> rx.Component:
    """按赛制渲染成绩表。``is_oi`` 可为 bool（测试）或 State bool var（运行时）。"""
    return rx.cond(is_oi, _oi_table(rows), _xcpc_table(rows))
