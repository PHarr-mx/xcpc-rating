"""P4d admin 在线导入页。"""

import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.states.admin.imports import AdminImportState


def _feedback() -> rx.Component:
    return rx.cond(
        AdminImportState.admin_error != "",
        rx.callout(AdminImportState.admin_error, icon="triangle_alert", color_scheme="red", role="alert", width="100%"),
        rx.cond(
            AdminImportState.admin_feedback != "",
            rx.callout(AdminImportState.admin_feedback, icon="check", color_scheme="green", role="status", width="100%"),
        ),
    )


def _steps() -> rx.Component:
    return rx.hstack(
        rx.badge("1 上传", color_scheme="blue"),
        rx.badge("2 元信息", color_scheme="blue"),
        rx.badge("3 预览", color_scheme="blue"),
        rx.badge("4 匹配", color_scheme="blue"),
        rx.badge("5 确认", color_scheme="green"),
        wrap="wrap",
        spacing="2",
    )


def _upload() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("步骤 1–2：上传与元信息", size="4"),
            rx.upload(
                rx.button("选择 xlsx 文件", variant="soft"),
                id="formal-import-upload",
                accept={".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"], ".xlsm": ["application/vnd.ms-excel.sheet.macroEnabled.12"]},
                max_files=1,
                on_drop=AdminImportState.handle_upload,
            ),
            rx.cond(AdminImportState.has_upload, rx.text(AdminImportState.upload_filename, color_scheme="gray")),
            rx.hstack(
                rx.input(value=AdminImportState.form_contest_id, on_change=AdminImportState.set_form_contest_id, placeholder="contest_id"),
                rx.input(value=AdminImportState.form_date, on_change=AdminImportState.set_form_date, placeholder="比赛日期 YYYY-MM-DD", type="date"),
                rx.input(value=AdminImportState.form_contest_type, on_change=AdminImportState.set_form_contest_type, placeholder="contest_type"),
                rx.input(value=AdminImportState.form_default_grade, on_change=AdminImportState.set_form_default_grade, placeholder="默认入学年（可选）", type="number"),
                width="100%", wrap="wrap",
            ),
            rx.button("解析并生成预览", on_click=AdminImportState.stage_parse, color_scheme="blue"),
            spacing="3", width="100%",
        ), width="100%",
    )


def _preview() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("步骤 3：解析预览", size="4"),
            rx.hstack(
                rx.badge(rx.text("总队数 "), AdminImportState.batch["total_teams"]),
                rx.badge(rx.text("本校队数 "), AdminImportState.batch["school_teams_count"]),
                rx.badge(rx.text("奖牌队数 "), AdminImportState.batch["standings_count"]),
                rx.badge(rx.text("未匹配选手 "), AdminImportState.batch["unmatched_count"], color_scheme="orange"),
                wrap="wrap", spacing="2",
            ),
            rx.text("奖牌线：gold / silver / bronze 将按 xlsx 正式组奖牌或百分位自动推算。", color_scheme="gray"),
            spacing="3", width="100%",
        ), width="100%",
    )


def _matching() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("步骤 4：处理未匹配选手", size="4"),
            rx.text("每个姓名选择已有 player，或选择“新建”。所有决议提交前只保存在 staged payload 中。", color_scheme="gray"),
            rx.foreach(
                AdminImportState.unmatched_players,
                lambda item: rx.hstack(
                    rx.text(item["name"], weight="medium", width="8em"),
                    rx.text(item["team_name"], size="2", color_scheme="gray", width="18em"),
                    rx.select(
                        AdminImportState.player_option_ids,
                        value=item["decision"],
                        on_change=lambda value: AdminImportState.set_decision(item["name"], value),
                        placeholder="选择已有选手或新建",
                    ),
                    width="100%", wrap="wrap",
                ),
            ),
            spacing="3", width="100%",
        ), width="100%",
    )


def _actions() -> rx.Component:
    return rx.hstack(
        rx.button("取消导入", on_click=AdminImportState.discard_import, variant="soft", color_scheme="gray"),
        rx.button("确认导入", on_click=AdminImportState.confirm_import, color_scheme="green"),
        spacing="3",
    )


def _content() -> rx.Component:
    return rx.vstack(
        rx.heading("在线正式赛导入", size="7"),
        rx.text("上传与解析阶段只写 ImportBatch(staged)；确认成功后才写选手、队伍、比赛和 raw 归档。", color_scheme="gray"),
        _steps(), _feedback(), _upload(),
        rx.cond(AdminImportState.batch_id > 0, _preview()),
        rx.cond(AdminImportState.unmatched_players.length() > 0, _matching()),
        rx.cond(AdminImportState.batch_id > 0, _actions()),
        spacing="5", width="100%", max_width="90em",
    )


def admin_import() -> rx.Component:
    return page_shell(rx.cond(AdminImportState.is_admin, _content(), rx.text("无权访问，请以管理员身份登录。", size="3", color_scheme="gray")))
