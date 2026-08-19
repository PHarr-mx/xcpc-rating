"""个人资料页：绑定申请 + 自助字段编辑。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.profile import OJ_PLATFORMS, ProfileState


def _binding_feedback() -> rx.Component:
    """绑定申请的提示条（成功 / 失败）。"""
    return rx.cond(
        ProfileState.binding_error != "",
        rx.callout(
            ProfileState.binding_error,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
        rx.cond(
            ProfileState.binding_feedback != "",
            rx.callout(
                ProfileState.binding_feedback,
                icon="check",
                color_scheme="green",
                role="status",
                width="100%",
            ),
        ),
    )


def _binding_form() -> rx.Component:
    """未绑定时：提交绑定申请。"""
    return rx.card(
        rx.vstack(
            rx.heading("绑定选手", size="5"),
            rx.text(
                "绑定后你可以在名册中认领自己的选手资料，并自助维护 handle、别名与 OJ 账号。",
                size="2",
                color_scheme="gray",
            ),
            rx.text("选择选手", size="2"),
            rx.select.root(
                rx.select.trigger(placeholder="选择要绑定的选手", width="100%"),
                rx.select.content(
                    rx.select.group(
                        rx.foreach(
                            ProfileState.bindable_players,
                            lambda p: rx.select.item(
                                f"{p['name']}（{p['player_id']}）",
                                value=p["player_id"],
                            ),
                        ),
                    ),
                ),
                value=ProfileState.binding_player_id,
                on_change=ProfileState.set_binding_player_id,
                width="100%",
            ),
            rx.text("申请理由（可选）", size="2"),
            rx.text_area(
                value=ProfileState.binding_reason,
                on_change=ProfileState.set_binding_reason,
                placeholder="例如：我是该选手本人，学号 xxx",
                rows="2",
                width="100%",
            ),
            _binding_feedback(),
            rx.button("提交绑定申请", on_click=ProfileState.submit_binding, width="100%"),
            align="start",
            width="100%",
        ),
        width="100%",
    )


def _bound_info() -> rx.Component:
    """已绑定时：展示绑定信息（admin-only 字段只读）。"""
    return rx.cond(
        ProfileState.player,
        rx.card(
            rx.vstack(
                rx.heading("绑定信息", size="5"),
                rx.hstack(
                    rx.text("校内 ID", width="8em", color_scheme="gray"),
                    rx.text(ProfileState.player.player_id),
                ),
                rx.hstack(
                    rx.text("姓名", width="8em", color_scheme="gray"),
                    rx.hstack(
                        rx.text(ProfileState.player.name),
                        rx.badge("admin 维护", color_scheme="gray", size="1"),
                    ),
                ),
                rx.hstack(
                    rx.text("年级", width="8em", color_scheme="gray"),
                    rx.hstack(
                        rx.text(ProfileState.player.grade_label),
                        rx.badge("admin 维护", color_scheme="gray", size="1"),
                    ),
                ),
                rx.hstack(
                    rx.text("状态", width="8em", color_scheme="gray"),
                    rx.hstack(
                        rx.text(ProfileState.player.status_label),
                        rx.badge("admin 维护", color_scheme="gray", size="1"),
                    ),
                ),
                align="start",
                width="100%",
            ),
            width="100%",
        ),
    )


def _edit_feedback() -> rx.Component:
    """自助编辑的提示条（成功 / 失败）。"""
    return rx.cond(
        ProfileState.edit_error != "",
        rx.callout(
            ProfileState.edit_error,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
        rx.cond(
            ProfileState.edit_feedback != "",
            rx.callout(
                ProfileState.edit_feedback,
                icon="check",
                color_scheme="green",
                role="status",
                width="100%",
            ),
        ),
    )


def _oj_accounts() -> rx.Component:
    """已绑定的 OJ 账号列表 + 新增表单。"""
    return rx.vstack(
        rx.text("OJ 账号", size="2"),
        rx.foreach(
            ProfileState.oj_accounts,
            lambda acc: rx.hstack(
                rx.badge(
                    rx.match(
                        acc["platform"],
                        ("codeforces", "Codeforces"),
                        ("atcoder", "AtCoder"),
                        ("luogu", "洛谷"),
                        ("nowcoder", "牛客"),
                        "",
                    ),
                    size="1",
                ),
                rx.text(acc["handle"]),
                rx.spacer(),
                rx.button(
                    "删除",
                    size="1",
                    variant="ghost",
                    color_scheme="red",
                    on_click=ProfileState.remove_oj_account(
                        acc["platform"], acc["handle"]
                    ),
                ),
                width="100%",
            ),
        ),
        rx.hstack(
            rx.select(
                OJ_PLATFORMS,
                value=ProfileState.oj_platform,
                on_change=ProfileState.set_oj_platform,
                width="10em",
            ),
            rx.input(
                value=ProfileState.oj_handle,
                on_change=ProfileState.set_oj_handle,
                placeholder="OJ 用户名",
                width="100%",
            ),
            rx.button("添加", on_click=ProfileState.add_oj_account),
            width="100%",
        ),
        align="start",
        width="100%",
    )


def _self_edit() -> rx.Component:
    """已绑定时：自助字段编辑（handle / aliases / OJ 账号）。"""
    return rx.card(
        rx.vstack(
            rx.heading("自助资料", size="5"),
            rx.text("以下字段由本人维护，改动即时生效。", size="2", color_scheme="gray"),
            rx.text("Handle", size="2"),
            rx.input(
                value=ProfileState.handle,
                on_change=ProfileState.set_handle,
                placeholder="（留空表示未设置）",
                width="100%",
            ),
            rx.text("别名（逗号分隔，如：Acid, 神神）", size="2"),
            rx.text_area(
                value=ProfileState.aliases_text,
                on_change=ProfileState.set_aliases_text,
                rows="2",
                width="100%",
            ),
            _oj_accounts(),
            _edit_feedback(),
            rx.button("保存资料", on_click=ProfileState.save_profile, width="100%"),
            align="start",
            width="100%",
        ),
        width="100%",
    )


def profile() -> rx.Component:
    """个人资料页。"""
    return page_shell(
        rx.cond(
            ProfileState.is_authenticated,
            rx.vstack(
                rx.heading("个人资料", size="7"),
                rx.cond(ProfileState.is_bound, _bound_info(), _binding_form()),
                rx.cond(ProfileState.is_bound, _self_edit()),
                spacing="6",
                width="100%",
                max_width="40em",
            ),
            rx.text("请先登录…", size="3"),
        ),
    )
