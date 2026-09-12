"""关于页（/about）：数据与赛季说明（docs/08 §3 路由表）。

纯静态页，无 State 依赖；内容随功能演进手工维护。
"""

import reflex as rx

from ..components.layout import page_shell


def _section(title: str, *children) -> rx.Component:
    return rx.vstack(
        rx.heading(title, size="5"),
        *children,
        spacing="2",
        width="100%",
        align_items="start",
    )


def _item(text: str) -> rx.Component:
    return rx.hstack(
        rx.text("·", size="3", color=rx.color("gray", 10), width="1em"),
        rx.text(text, size="3", color=rx.color("gray", 11)),
        spacing="2",
        align_items="start",
        width="100%",
    )


def about() -> rx.Component:
    return page_shell(
        rx.vstack(
            rx.heading("关于 XCPC Rating", size="7"),
            rx.text(
                "西南民族大学校内 XCPC 系列编程竞赛的 Rating 统计与展示系统。"
                "系统汇总正式赛成绩并按统一规则计算选手 Rating，形成可查询、可分享的校内榜单。",
                size="3",
                color=rx.color("gray", 11),
            ),
            rx.divider(),
            _section(
                "数据来源",
                _item("正式赛：ICPC / CCPC / 蓝桥杯 / 天梯赛等各级赛事，由管理员经后台从 XCPC.io 格式成绩表导入。"),
                _item("训练赛：规划中，支持录入后接入 Rating 计算。"),
            ),
            _section(
                "赛年与赛季",
                _item("赛年：每年 9 月 1 日至次年 8 月 31 日。"),
                _item("赛季：秋学期（9–1 月）、寒假（2 月）、春学期（3–6 月）、暑假（7–8 月）。"),
                _item("榜单提供生涯 / 赛年 / 赛季三个时间维度，以及「全部比赛 / 仅正式赛」两种口径；筛选状态可通过地址栏链接分享。"),
            ),
            _section(
                "Rating 算法",
                _item("当前为过渡版本 placeholder_v0：按单场名次百分位与比赛权重累计得分。"),
                _item("比赛权重按级别赋值：区域赛 / 全国赛 100，线上赛 90，邀请赛 80，全国性其他赛事 75–80，省赛 70，校赛 50–60。"),
                _item("正式公式开发中；榜单为运行时全量计算，算法切换后将整体按新公式重算。"),
            ),
            _section(
                "榜单规则",
                _item("按 Rating 降序排名，同分并列（1、2、2、4 式竞赛排名）。"),
                _item("离队选手不再出现在榜单；退役选手保留档案、成绩与 Rating。"),
                _item("页脚「数据版本」随每次数据变更自动递增，可用于确认看到的是最新榜单。"),
            ),
            _section(
                "账号与绑定",
                _item("注册账号后，在「个人资料」页提交绑定申请，管理员审批通过即与选手档案关联。"),
                _item("绑定后可自助维护校内简称、曾用名，以及 Codeforces / AtCoder / 洛谷 / 牛客账号。"),
            ),
            rx.divider(),
            rx.link("返回榜单", href="/", size="2"),
            spacing="5",
            width="100%",
            align_items="start",
        ),
    )
