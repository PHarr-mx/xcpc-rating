"""OJ 账号外链组件（docs/05 组件清单）。

URL 与展示文案在 State 侧（服务端）预算成视图 dict（``display``/``url``），
本组件只做渲染——Var 不能在构建期按 Python 逻辑逐项分支。
"""

import reflex as rx


def oj_links(accounts) -> rx.Component:
    """渲染 OJ 账号列表：有 url 渲染外链，否则纯文本；无账号给占位说明。

    ``accounts`` 可为视图 list（测试）或 State list var（运行时）。
    """
    count = len(accounts) if isinstance(accounts, list) else accounts.length()
    return rx.cond(
        count > 0,
        rx.hstack(
            rx.foreach(
                accounts,
                lambda a: rx.cond(
                    a["url"],
                    rx.link(a["display"], href=a["url"], is_external=True, size="2"),
                    rx.text(a["display"], size="2"),
                ),
            ),
            spacing="4",
            wrap="wrap",
            align_items="center",
        ),
        rx.text("未填写 OJ 账号", size="2", color=rx.color("gray", 10)),
    )
