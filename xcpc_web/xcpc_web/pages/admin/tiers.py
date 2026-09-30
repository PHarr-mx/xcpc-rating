"""Admin 赛事等级管理页（/admin/tiers）：等级（系数）+ 奖项基线分，同页管理。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.admin.tiers import AdminTiersState


def _feedback() -> rx.Component:
    return rx.vstack(
        rx.cond(
            AdminTiersState.admin_error != "",
            rx.callout(
                AdminTiersState.admin_error,
                icon="triangle_alert",
                color_scheme="red",
                role="alert",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            AdminTiersState.admin_feedback != "",
            rx.callout(
                AdminTiersState.admin_feedback,
                icon="circle_check",
                color_scheme="green",
                width="100%",
            ),
            rx.fragment(),
        ),
        spacing="2",
        width="100%",
    )


def _tier_form() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("赛事等级", size="5"),
            rx.text(
                "等级决定该档比赛的积分系数与排名权重（系数 1.0 = 基准）；"
                "被比赛引用的等级不可删除。",
                size="2",
                color_scheme="gray",
            ),
            rx.hstack(
                rx.input(
                    value=AdminTiersState.form_tier_name,
                    on_change=AdminTiersState.set_form_tier_name,
                    placeholder="等级名称（如 ICPC 省赛）",
                    width="40%",
                ),
                rx.input(
                    value=AdminTiersState.form_tier_coefficient,
                    on_change=AdminTiersState.set_form_tier_coefficient,
                    placeholder="系数（如 0.7）",
                    width="30%",
                ),
                rx.input(
                    value=AdminTiersState.form_tier_sort,
                    on_change=AdminTiersState.set_form_tier_sort,
                    placeholder="排序",
                    width="30%",
                ),
                width="100%",
                spacing="3",
            ),
            rx.hstack(
                rx.button(
                    rx.cond(AdminTiersState.editing_tier_id != "", "保存修改", "添加等级"),
                    on_click=AdminTiersState.save_tier,
                    size="2",
                ),
                rx.cond(
                    AdminTiersState.editing_tier_id != "",
                    rx.button("取消编辑", on_click=AdminTiersState.cancel_edit_tier,
                              variant="soft", size="2"),
                    rx.fragment(),
                ),
                spacing="3",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def _tiers_table() -> rx.Component:
    return rx.card(
        rx.cond(
            AdminTiersState.tiers.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("名称"),
                        rx.table.column_header_cell("系数"),
                        rx.table.column_header_cell("排序"),
                        rx.table.column_header_cell("操作"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        AdminTiersState.tiers,
                        lambda tier: rx.table.row(
                            rx.table.cell(tier["name"]),
                            rx.table.cell(tier["coefficient"]),
                            rx.table.cell(tier["sort_order"]),
                            rx.table.cell(
                                rx.hstack(
                                    rx.button(
                                        "编辑",
                                        size="1",
                                        variant="ghost",
                                        on_click=AdminTiersState.edit_tier(tier["id"]),
                                    ),
                                    rx.button(
                                        "删除",
                                        size="1",
                                        variant="ghost",
                                        color_scheme="red",
                                        on_click=AdminTiersState.delete_tier(tier["id"]),
                                    ),
                                    spacing="2",
                                )
                            ),
                        ),
                    ),
                ),
                width="100%",
            ),
            rx.text("还没有赛事等级", color_scheme="gray", size="2"),
        ),
        width="100%",
    )


def _award_form() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("奖项基线分", size="5"),
            rx.text(
                "「积分只由奖项决定」的比赛按 基线分 × 赛事等级系数 计分；"
                "名称使用 gold / silver / bronze / honorable 等英文键。",
                size="2",
                color_scheme="gray",
            ),
            rx.hstack(
                rx.input(
                    value=AdminTiersState.form_award_name,
                    on_change=AdminTiersState.set_form_award_name,
                    placeholder="奖项名称（如 gold）",
                    width="40%",
                ),
                rx.input(
                    value=AdminTiersState.form_award_points,
                    on_change=AdminTiersState.set_form_award_points,
                    placeholder="基线分（如 100）",
                    width="30%",
                ),
                rx.input(
                    value=AdminTiersState.form_award_sort,
                    on_change=AdminTiersState.set_form_award_sort,
                    placeholder="排序",
                    width="30%",
                ),
                width="100%",
                spacing="3",
            ),
            rx.hstack(
                rx.button(
                    rx.cond(AdminTiersState.editing_award_id != "", "保存修改", "添加奖项"),
                    on_click=AdminTiersState.save_award,
                    size="2",
                ),
                rx.cond(
                    AdminTiersState.editing_award_id != "",
                    rx.button("取消编辑", on_click=AdminTiersState.cancel_edit_award,
                              variant="soft", size="2"),
                    rx.fragment(),
                ),
                spacing="3",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def _awards_table() -> rx.Component:
    return rx.card(
        rx.cond(
            AdminTiersState.award_levels.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("名称"),
                        rx.table.column_header_cell("基线分"),
                        rx.table.column_header_cell("排序"),
                        rx.table.column_header_cell("操作"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        AdminTiersState.award_levels,
                        lambda award: rx.table.row(
                            rx.table.cell(
                                rx.hstack(
                                    rx.text(award["name"], weight="medium"),
                                    rx.text(award["label"], size="1", color_scheme="gray"),
                                    spacing="2",
                                )
                            ),
                            rx.table.cell(award["base_points"]),
                            rx.table.cell(award["sort_order"]),
                            rx.table.cell(
                                rx.hstack(
                                    rx.button(
                                        "编辑",
                                        size="1",
                                        variant="ghost",
                                        on_click=AdminTiersState.edit_award(award["id"]),
                                    ),
                                    rx.button(
                                        "删除",
                                        size="1",
                                        variant="ghost",
                                        color_scheme="red",
                                        on_click=AdminTiersState.delete_award(award["id"]),
                                    ),
                                    spacing="2",
                                )
                            ),
                        ),
                    ),
                ),
                width="100%",
            ),
            rx.text("还没有奖项基线", color_scheme="gray", size="2"),
        ),
        width="100%",
    )


def admin_tiers() -> rx.Component:
    """``/admin/tiers`` 赛事等级管理页面。"""
    return page_shell(
        rx.cond(
            AdminTiersState.is_admin,
            rx.vstack(
                rx.vstack(
                    rx.heading("赛事等级", size="7"),
                    rx.text(
                        "管理赛事等级（系数）与奖项基线分；统一比赛创建表单的等级选项来自这里。",
                        size="2",
                        color_scheme="gray",
                    ),
                    align="start",
                    spacing="1",
                    width="100%",
                ),
                _feedback(),
                _tier_form(),
                _tiers_table(),
                _award_form(),
                _awards_table(),
                spacing="5",
                width="100%",
                max_width="100em",
            ),
            rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray"),
        ), section="admin", subsection="tiers")
