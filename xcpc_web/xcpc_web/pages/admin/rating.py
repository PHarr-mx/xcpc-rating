"""权重试算页（/admin/rating，P6）：左调参数、右看与当前榜单的 diff。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_core.rating.formula_params import TUNABLE_FIELDS

from xcpc_web.states.admin.rating import FIELD_META, RatingLabState


def _feedback() -> rx.Component:
    return rx.vstack(
        rx.cond(
            RatingLabState.admin_error != "",
            rx.callout(
                RatingLabState.admin_error,
                icon="triangle_alert",
                color_scheme="red",
                role="alert",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            RatingLabState.admin_feedback != "",
            rx.callout(
                RatingLabState.admin_feedback,
                icon="circle_check",
                color_scheme="green",
                width="100%",
            ),
            rx.fragment(),
        ),
        spacing="2",
        width="100%",
    )


def _param_row(field: str) -> rx.Component:
    """一行参数：标签/说明 + 输入框 + 已应用值。

    字段集在构建期已知（``TUNABLE_FIELDS``），故直接按字段名取 State var 与 setter
    ——``rx.foreach`` 循环变量是运行时 Var，不能用于查 Python 字典。
    """
    label, hint = FIELD_META[field]
    return rx.grid(
        rx.vstack(
            rx.text(label, size="2", weight="medium"),
            rx.text(hint, size="1", color_scheme="gray"),
            spacing="1",
            align="start",
            width="100%",
        ),
        rx.input(
            value=getattr(RatingLabState, f"draft_{field}"),
            on_change=getattr(RatingLabState, f"set_draft_{field}"),
            width="100%",
            aria_label=label,
        ),
        rx.text(
            getattr(RatingLabState, "baseline_params").get(field, ""),
            size="2",
            color_scheme="gray",
        ),
        columns="3",
        spacing="3",
        width="100%",
        align="center",
    )


def _params_card() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("公式参数", size="5"),
            rx.text(
                "修改后点「试算」看与当前榜单的差异——试算不落库、不进缓存。"
                "确认无误再点「应用」，才会写入 data/config/rating_params.yaml 并使榜单缓存失效。",
                size="2",
                color_scheme="gray",
            ),
            rx.hstack(
                rx.text("参数", size="1", color_scheme="gray", width="40%"),
                rx.text("草稿值", size="1", color_scheme="gray"),
                rx.text("已应用", size="1", color_scheme="gray"),
                spacing="3",
                width="100%",
            ),
            rx.divider(),
            rx.vstack(
                *[_param_row(field) for field in TUNABLE_FIELDS],
                spacing="3",
                width="100%",
            ),
            rx.divider(),
            rx.hstack(
                rx.button(
                    "试算",
                    on_click=RatingLabState.run_preview,
                    color_scheme="violet",
                ),
                rx.button(
                    "应用",
                    on_click=RatingLabState.apply_draft,
                    color_scheme="green",
                    variant="soft",
                ),
                rx.button(
                    "恢复为已应用",
                    on_click=RatingLabState.reset_to_baseline,
                    variant="ghost",
                ),
                rx.button(
                    "恢复默认值",
                    on_click=RatingLabState.reset_to_default,
                    variant="ghost",
                    color_scheme="gray",
                ),
                spacing="3",
                wrap="wrap",
            ),
            spacing="4",
            width="100%",
        ),
        width="100%",
    )


def _summary_card() -> rx.Component:
    return rx.cond(
        RatingLabState.has_preview,
        rx.card(
            rx.vstack(
                rx.heading("试算结果", size="5"),
                rx.hstack(
                    rx.badge(
                        f"选手 {RatingLabState.summary['players']} 人",
                        color_scheme="gray",
                        size="2",
                    ),
                    rx.badge(
                        f"名次变化 {RatingLabState.summary['rank_changed']} 人",
                        color_scheme="orange",
                        size="2",
                    ),
                    rx.badge(
                        f"最大变动 {RatingLabState.summary['max_abs_delta']}",
                        color_scheme="violet",
                        size="2",
                    ),
                    rx.badge(
                        f"平均变动 {RatingLabState.summary['mean_abs_delta']}",
                        color_scheme="gray",
                        size="2",
                    ),
                    spacing="2",
                    wrap="wrap",
                ),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("名次", width="80px"),
                            rx.table.column_header_cell("原", width="60px"),
                            rx.table.column_header_cell("选手"),
                            rx.table.column_header_cell("原 Rating", justify="end"),
                            rx.table.column_header_cell("试算", justify="end"),
                            rx.table.column_header_cell("变动", justify="end"),
                            rx.table.column_header_cell("场次", justify="end"),
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            RatingLabState.preview_rows,
                            lambda row: rx.table.row(
                                rx.table.cell(row["rank_draft"]),
                                rx.table.cell(
                                    rx.cond(
                                        row["rank_moved"],
                                        rx.badge(
                                            row["rank_base"],
                                            color_scheme="orange",
                                            variant="soft",
                                        ),
                                        row["rank_base"],
                                    )
                                ),
                                rx.table.cell(row["name"]),
                                rx.table.cell(row["rating_base"], justify="end"),
                                rx.table.cell(row["rating_draft"], justify="end"),
                                rx.table.cell(
                                    rx.text(
                                        row["delta_text"],
                                        color_scheme=row["delta_tone"],
                                        weight="medium",
                                    ),
                                    justify="end",
                                ),
                                rx.table.cell(row["events"], justify="end"),
                            ),
                        )
                    ),
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            width="100%",
        ),
        rx.fragment(),
    )


def rating_lab_page() -> rx.Component:
    return page_shell(
        rx.vstack(
            rx.hstack(
                rx.heading("权重试算", size="7"),
                rx.badge("P6", color_scheme="violet", size="2"),
                rx.spacer(),
                rx.text(
                    "只覆盖 Rating 轨；积分系数请到「赛事等级」页调整",
                    size="1",
                    color_scheme="gray",
                ),
                width="100%",
                align="center",
            ),
            _feedback(),
            _params_card(),
            _summary_card(),
            spacing="5",
            width="100%",
            align="start",
        ),
        section="admin",
        subsection="rating",
    )