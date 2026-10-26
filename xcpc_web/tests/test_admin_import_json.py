"""通用比赛 JSON 的 Web 上传通道（/admin/import 第二条通道）。"""

from __future__ import annotations

import json
from datetime import date

import asyncio

import pytest
from sqlalchemy import select

from xcpc_core.contest.api import list_contests
from xcpc_core.db.tables import AuditLog, Contest, Player

from xcpc_web.states.admin.imports import AdminImportState


def _doc(**overrides) -> dict:
    base = {
        "contest_id": "web_json_1",
        "title": "Web 上传训练赛",
        "date": "2026-10-05",
        "format": "icpc",
        "entity": "team",
        "tier": "新队员组",
        "counts_for_points": False,
        "counts_for_ranking": True,
        "standings": [
            {"team_name": "甲队", "members": ["张三", "李四"], "rank": 1, "solved": 5, "penalty": 300},
            {"team_name": "乙队", "members": ["王五"], "rank": 2, "solved": 3, "penalty": 400},
        ],
    }
    base.update(overrides)
    return base


class _FakeUpload:
    """模拟 rx.UploadFile：只需要 filename 与同步 read。"""

    def __init__(self, filename: str, payload: dict | str):
        self.filename = filename
        self._payload = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload

    async def read(self) -> bytes:
        return self._payload.encode("utf-8")


def _upload(state, payload: dict, filename: str = "c.json") -> None:
    """同步驱动异步事件处理器（Reflex 事件在测试里直接 await）。"""
    asyncio.run(state.handle_json_upload([_FakeUpload(filename, payload)]))


def _seed_players(session) -> None:
    session.add_all([Player(id="p001", name="张三"), Player(id="p002", name="李四")])
    session.commit()


# ---- 守卫 ----


def test_non_admin_cannot_upload_json(build_state, make_user, core_store):
    st = build_state(AdminImportState, make_user("member"))
    assert st.json_rows == []
    assert st.json_has_preview is False


def test_json_header_empty_without_preview(build_state, make_user, core_store):
    st = build_state(AdminImportState, make_user("root", role="admin"))
    assert st.json_header == {}


# ---- 上传预览（只读） ----


def test_json_upload_produces_preview_without_writing(build_state, make_user, core_store):
    _seed_players(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(), "c.json")

    assert st.admin_error == ""
    assert st.json_has_preview is True
    header = st.json_header
    assert header["format_entity"] == "icpc × team"
    assert header["rows_label"] == "2 条成绩"
    assert header["to_create_label"] == "将新建选手 1 名"  # 只有王五需要新建
    assert header["existing"] is False

    # 关键：预览阶段不写库
    assert len(core_store.scalars(select(Contest)).all()) == 0
    assert len(core_store.scalars(select(Player)).all()) == 2


def test_json_rows_view_distinguishes_cases(build_state, make_user, core_store):
    _seed_players(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(), "c.json")
    rows = st.json_rows

    assert len(rows) == 2
    # 甲队：张三、李四都已在册 → 全部已存在
    assert rows[0]["status"] == "全部已存在"
    assert rows[0]["blocked"] is False
    assert rows[0]["matched"] == 2
    assert rows[0]["to_create"] == 0
    # 乙队：王五未建档 → 将新建
    assert rows[1]["status"] == "将新建选手"
    assert rows[1]["matched"] == 0
    assert rows[1]["to_create"] == 1


def test_json_upload_rejects_non_json(build_state, make_user, core_store):
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(), "bad.xlsx")
    assert "只接受 .json" in st.admin_error
    assert st.json_has_preview is False


def test_json_upload_surfaces_validation_error(build_state, make_user, core_store):
    st = build_state(AdminImportState, make_user("root", role="admin"))
    bad = _doc()
    bad["standings"][0]["members"] = []  # 触发 DTO 校验
    _upload(st, bad)
    assert "解析失败" in st.admin_error
    assert st.json_has_preview is False


# ---- 确认写入 ----


def test_confirm_writes_and_audits(build_state, make_user, core_store):
    _seed_players(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(), "c.json")
    st.confirm_json_import()

    assert st.admin_error == ""
    assert "已导入" in st.admin_feedback
    contests = core_store.scalars(select(Contest)).all()
    assert len(contests) == 1
    assert contests[0].id == "web_json_1"

    actions = [row.action for row in core_store.scalars(select(AuditLog)).all()]
    assert "import.json_confirm" in actions

    # 确认后状态复位
    assert st.json_has_preview is False


def test_confirm_requires_upload_first(build_state, make_user, core_store):
    st = build_state(AdminImportState, make_user("root", role="admin"))
    st.confirm_json_import()
    assert "请先上传" in st.admin_error


def test_discard_clears_without_writing(build_state, make_user, core_store):
    _seed_players(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(), "c.json")
    st.discard_json_import()

    assert "已取消" in st.admin_feedback
    assert st.json_has_preview is False
    assert len(core_store.scalars(select(Contest)).all()) == 0


def test_existing_contest_flagged_in_preview(build_state, make_user, core_store):
    _seed_players(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(), "c.json")
    st.confirm_json_import()

    # 再传一次同 ID → 预览应提示将覆盖
    _upload(st, _doc())
    assert st.json_header["existing"] is True

# ---- 姓名歧义的人工决议（与 xlsx 通道同口径）-------------------------------


def _seed_same_name(session) -> None:
    """造两个同名选手，制造真实的姓名歧义。"""
    session.add_all([Player(id="p001", name="张伟"), Player(id="p002", name="张伟")])
    session.commit()


def test_ambiguous_name_blocks_row_without_decision(build_state, make_user, core_store):
    _seed_same_name(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(
        contest_id="amb1",
        standings=[{"team_name": "甲队", "members": ["张伟"], "rank": 1, "solved": 5}],
    ))

    assert st.json_unresolved_count == 1
    assert st.json_ambiguous[0]["name"] == "张伟"
    assert st.json_ambiguous[0]["current"] == ""

    # 未决议 → 确认后该行被跳过
    st.confirm_json_import()
    assert st.admin_error != "", "全部行被跳过时应报错"


def test_decision_resolves_ambiguity_and_imports(build_state, make_user, core_store):
    _seed_same_name(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(
        contest_id="amb2",
        standings=[{"team_name": "甲队", "members": ["张伟"], "rank": 1, "solved": 5}],
    ))

    st.set_json_decision("张伟", "p002")
    assert st.json_unresolved_count == 0

    st.confirm_json_import()
    assert st.admin_error == ""
    assert "已导入" in st.admin_feedback

    # 决议生效：用的是 p002
    from sqlalchemy import select as sel
    from xcpc_core.db.tables import StandingMember

    member_ids = core_store.scalars(sel(StandingMember.player_id)).all()
    assert list(member_ids) == ["p002"]


def test_decision_new_creates_player(build_state, make_user, core_store):
    _seed_same_name(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(
        contest_id="amb3",
        standings=[{"team_name": "甲队", "members": ["张伟"], "rank": 1, "solved": 5}],
    ))

    st.set_json_decision("张伟", "new")
    assert st.json_unresolved_count == 0
    st.confirm_json_import()

    assert st.admin_error == ""
    assert "新建选手 1 名" in st.admin_feedback or "新建选手" in st.admin_feedback


def test_decision_payload_conversion(build_state, make_user, core_store):
    _seed_same_name(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(contest_id="amb4"))

    st.set_json_decision("甲", "p001")
    st.set_json_decision("乙", "new:2025")
    payload = st._decisions_payload()

    assert payload["甲"] == {"player_id": "p001"}
    assert payload["乙"] == {"action": "new", "grade": 2025}


def test_clear_decision(build_state, make_user, core_store):
    _seed_same_name(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(contest_id="amb5"))

    st.set_json_decision("张伟", "p001")
    st.set_json_decision("张伟", "")
    assert st.json_decisions == {}


def test_upload_resets_previous_decisions(build_state, make_user, core_store):
    _seed_same_name(core_store)
    st = build_state(AdminImportState, make_user("root", role="admin"))
    _upload(st, _doc(contest_id="amb6"))
    st.set_json_decision("张伟", "p001")
    assert st.json_decisions

    _upload(st, _doc(contest_id="amb7"))
    assert st.json_decisions == {}, "重新上传应清空上一次的决议"
