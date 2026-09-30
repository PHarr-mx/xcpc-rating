"""布局组件：顶栏（大类导航）+ 侧边栏（类内小项）+ 内容区。

信息架构（2026-09-30 与用户定案）：
- 顶栏四大类：榜单（公开）/ 积分（登录）/ 个人资料（登录）/ 系统管理（仅 admin）
- 侧边栏恒显示，承载类内小项；「我的认证」归属个人资料类（个人中心一站式）
- 高亮由各页显式传入 section/subsection 字面量，构建期决定——避开 Reflex
  运行时读路由的 Var 时敏坑
"""

import reflex as rx
import reflex_local_auth

from ..states.auth import AuthState

_SECTIONS: dict[str, dict] = {
    "rank": {
        "label": "榜单",
        "href": "/",
        "items": [
            {"key": "board", "label": "总榜", "href": "/"},
            {"key": "about", "label": "关于", "href": "/about"},
            # 两轨制定案后的扩展位：训练赛 Rating 榜 / 正式赛榜
        ],
    },
    "points": {
        "label": "积分",
        "href": "/points",
        "requires_login": True,
        "items": [
            {"key": "individual", "label": "个人积分榜", "href": "/points"},
            {"key": "team", "label": "队伍积分榜", "href": "/points"},
            {"key": "submit", "label": "提交认证", "href": "/points"},
        ],
    },
    "profile": {
        "label": "个人资料",
        "href": "/profile",
        "requires_login": True,
        "items": [
            {"key": "profile", "label": "我的资料", "href": "/profile"},
            {"key": "claims", "label": "我的认证", "href": "/profile"},
        ],
    },
    "admin": {
        "label": "系统管理",
        "href": "/admin",
        "requires_admin": True,
        "items": [
            {"key": "overview", "label": "概览", "href": "/admin"},
            {"key": "users", "label": "用户审批", "href": "/admin/users"},
            {"key": "players", "label": "选手管理", "href": "/admin/players"},
            {"key": "teams", "label": "队伍管理", "href": "/admin/teams"},
            {"key": "contests", "label": "比赛管理", "href": "/admin/contests"},
            {"key": "points", "label": "积分管理", "href": "/admin/points"},
            {"key": "audit", "label": "审计日志", "href": "/admin/audit"},
            {"key": "import", "label": "在线导入", "href": "/admin/import"},
        ],
    },
}


def _nav_link(label: str, href: str, *, size: str = "3", active: bool = False) -> rx.Component:
    """导航链接：激活项加粗用主色，未激活灰色。"""
    if active:
        return rx.link(label, href=href, size=size, weight="bold")
    return rx.link(label, href=href, size=size, color_scheme="gray")


def _top_nav(active_section: str) -> rx.Component:
    def _category(key: str) -> rx.Component:
        meta = _SECTIONS[key]
        link = _nav_link(meta["label"], meta["href"], active=key == active_section)
        if meta.get("requires_admin"):
            return rx.cond(AuthState.is_admin, link, rx.fragment())
        if meta.get("requires_login"):
            return rx.cond(AuthState.is_authenticated, link, rx.fragment())
        return link

    return rx.box(
        rx.hstack(
            rx.link(rx.heading("XCPC Rating", size="6"), href="/"),
            rx.hstack(*[_category(key) for key in _SECTIONS], spacing="4", align="center"),
            rx.spacer(),
            rx.cond(
                AuthState.is_authenticated,
                rx.hstack(
                    rx.text(AuthState.authenticated_user.username, size="2"),
                    rx.button("登出", on_click=AuthState.do_logout, variant="soft", size="2"),
                    spacing="3",
                    align="center",
                ),
                rx.hstack(
                    rx.button(
                        "登录",
                        on_click=rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE),
                        variant="soft",
                        size="2",
                    ),
                    rx.button(
                        "注册",
                        on_click=rx.redirect(reflex_local_auth.routes.REGISTER_ROUTE),
                        variant="solid",
                        size="2",
                    ),
                    spacing="2",
                ),
            ),
            align="center",
            width="100%",
        ),
        padding="1rem 2rem",
        border_bottom="1px solid",
        border_color=rx.color("gray", 6),
        background=rx.color("gray", 1),
        width="100%",
    )


def _sidebar(section: str, subsection: str | None) -> rx.Component:
    meta = _SECTIONS[section]
    return rx.card(
        rx.vstack(
            rx.heading(meta["label"], size="4"),
            rx.separator(size="4"),
            rx.vstack(
                *[
                    _nav_link(
                        item["label"],
                        item["href"],
                        size="2",
                        active=item["key"] == subsection,
                    )
                    for item in meta["items"]
                ],
                spacing="2",
                align="start",
                width="100%",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        width="13em",
        flex_shrink="0",
        height="fit-content",
        position="sticky",
        top="5rem",
    )


def page_shell(*children, section: str = "rank", subsection: str | None = None) -> rx.Component:
    """页面外壳：顶栏大类 + 侧边栏小项 + 内容区。

    各页面传入 section（四大类 key）与 subsection（侧边栏高亮项 key）；
    默认落在榜单类。
    """
    return rx.box(
        _top_nav(section),
        rx.container(
            rx.hstack(
                _sidebar(section, subsection),
                rx.box(*children, flex="1", min_width="0"),
                align="start",
                spacing="6",
                width="100%",
                padding="2rem 0",
            ),
        ),
        rx.box(
            rx.center(
                rx.text("© 2026 XCPC Rating System", size="1"),
                padding="1rem",
            ),
            border_top="1px solid",
            border_color=rx.color("gray", 6),
            margin_top="2rem",
        ),
        min_height="100vh",
    )
