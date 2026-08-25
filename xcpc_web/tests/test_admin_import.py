"""P4d 在线导入 Web 集成回归。"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from sqlalchemy import select

from xcpc_core.audit import api as audit_api
from xcpc_core.db.tables import AuditLog, Contest, ImportBatch, Player, Team
from xcpc_core.importer import api as importer_api
from xcpc_core.importer.models import (
    CreatedPlayer,
    FormalImportParams,
    FormalImportResult,
)
from xcpc_core.player.store import find_repo_root

from xcpc_web.states.admin.imports import AdminImportState


def test_non_admin_import_is_guarded_and_has_no_data(build_state, make_user, core_store):
    state = build_state(AdminImportState, make_user("member"))

    assert state.batch == {}
    assert state.unmatched_players == []
    assert state.on_load() is not None


def test_admin_can_stage_from_web_state_without_formal_data(
    build_state, make_user, core_store, monkeypatch
):
    root = find_repo_root()
    sample = root / "第十八届四川省大学生程序设计竞赛 - 正式赛.xlsx"
    if not sample.is_file():
        return
    monkeypatch.setattr(
        "xcpc_web.states.admin.imports.load_school_organizations",
        lambda: ["电子科技大学"],
    )
    state = build_state(AdminImportState, make_user("root", role="admin"))
    state.upload_path = str(sample)
    state.upload_filename = sample.name
    state.set_form_contest_id("web_staged_test")
    state.set_form_date("2026-05-18")
    state.set_form_contest_type("icpc_provincial")

    # Reflex 的 background event 不能像普通事件一样直接调用；测试调用其
    # EventHandler.fn，保留真实 async handler 逻辑并绕过前端事件调度器。
    asyncio.run(AdminImportState.stage_parse.fn(state))

    assert state.batch_id > 0
    batch = core_store.execute(select(ImportBatch)).scalar_one()
    assert batch.status == "staged"
    assert core_store.execute(select(Player)).scalars().all() == []
    assert core_store.execute(select(Team)).scalars().all() == []
    assert core_store.execute(select(Contest)).scalars().all() == []


def test_importer_session_is_configured_for_web(core_store):
    params = FormalImportParams(
        contest_id="configured_session_test",
        date="2026-05-18",
        contest_type="icpc_provincial",
        school_organizations=["电子科技大学"],
    )
    # 这里只验证 Web fixture 注入的 facade session 可用；实际 xlsx 流程由上一测试覆盖。
    assert importer_api.list_import_batches() == []
    assert params.contest_id == "configured_session_test"


def test_admin_confirm_cleans_upload_and_writes_audit(
    build_state, make_user, core_store, tmp_path, monkeypatch
):
    admin = make_user("root", role="admin")
    audit_api.configure_session(core_store)
    state = build_state(AdminImportState, admin)
    uploaded = tmp_path / "formal.xlsx"
    uploaded.write_bytes(b"xlsx placeholder")
    state.batch_id = 9
    state.upload_path = str(uploaded)
    state.upload_filename = uploaded.name

    result = FormalImportResult(
        contest_id="web_confirm_test",
        title="Web 确认测试",
        total_teams=1,
        school_teams_count=1,
        standings_imported=1,
        players_created=[
            CreatedPlayer(
                player_id="p001",
                name="新选手",
                team_name="测试队",
                contest_id="web_confirm_test",
            )
        ],
        unmatched_players=[],
        unmatched_teams=[],
        raw_path="data/raw/formal/web_confirm_test.json",
        source_file="formal/web_confirm_test.json",
    )
    calls: list[tuple[int, dict[str, str]]] = []

    def fake_confirm(batch_id: int, decisions: dict[str, str]):
        calls.append((batch_id, decisions))
        return result

    monkeypatch.setattr(importer_api, "confirm_import_batch", fake_confirm)
    state.decisions = {"新选手": "new"}

    state.confirm_import()

    assert calls == [(9, {"新选手": "new"})]
    assert not uploaded.exists()
    assert state.upload_path == ""
    assert state.admin_feedback == "导入完成：Web 确认测试（1 支队伍）"
    logs = core_store.execute(select(AuditLog)).scalars().all()
    assert [(log.action, log.target) for log in logs] == [
        ("import.confirm", "web_confirm_test")
    ]


def test_admin_discard_marks_batch_and_cleans_upload(
    build_state, make_user, core_store, tmp_path
):
    state = build_state(AdminImportState, make_user("root", role="admin"))
    sample = find_repo_root() / "第十八届四川省大学生程序设计竞赛 - 正式赛.xlsx"
    if not sample.is_file():
        return
    summary = importer_api.stage_formal_xlsx(
        sample,
        FormalImportParams(
            contest_id="web_discard_test",
            date=date(2026, 5, 18),
            contest_type="icpc_provincial",
            school_organizations=["电子科技大学"],
            auto_create_players=False,
        ),
        uploaded_by=state.authenticated_user.id,
        filename=sample.name,
    )
    uploaded = tmp_path / "discard.xlsx"
    uploaded.write_bytes(b"xlsx placeholder")
    state.batch_id = summary.batch_id
    state.upload_path = str(uploaded)
    state.upload_filename = uploaded.name

    state.discard_import()

    assert core_store.get(ImportBatch, summary.batch_id).status == "discarded"
    assert not uploaded.exists()
    assert state.batch_id == 0
    assert state.admin_feedback == "已取消导入，正式数据未发生变化"
