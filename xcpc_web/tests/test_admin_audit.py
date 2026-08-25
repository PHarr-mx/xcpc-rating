"""P4c admin 审计日志页回归。"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from xcpc_core.audit import api as audit_api
from xcpc_core.db.tables import AuditLog

from xcpc_web.states.admin.audit import AdminAuditState


def test_non_admin_is_guarded_and_sees_no_logs(build_state, make_user, core_store):
    audit_api.record(action="player.create", target="p001", user_id=99, diff_json={})
    state = build_state(AdminAuditState, make_user("member"))

    assert state.logs == []
    assert state.on_load() is not None


def test_admin_can_filter_logs_by_user_action_and_date(
    build_state, make_user, core_store
):
    admin = make_user("root", role="admin")
    other = make_user("operator", role="admin")
    audit_api.record(action="player.create", target="p001", user_id=admin[0], diff_json={"x": 1})
    audit_api.record(action="team.delete", target="t001", user_id=other[0], diff_json={"x": 2})
    state = build_state(AdminAuditState, admin)

    assert [item["action"] for item in state.logs] == ["team.delete", "player.create"]
    state.set_user_filter("root")
    assert [item["target"] for item in state.logs] == ["p001"]
    state.set_user_filter("")
    state.set_action_filter("team.delete")
    assert [item["target"] for item in state.logs] == ["t001"]
    state.set_action_filter("all")
    audit_day = datetime.now(timezone.utc).date().isoformat()
    state.set_date_from(audit_day)
    state.set_date_to(audit_day)
    assert len(state.logs) == 2


def test_audit_invalid_date_is_reported(build_state, make_user, core_store):
    state = build_state(AdminAuditState, make_user("root", role="admin"))
    state.set_date_from("not-a-date")

    assert state.logs == []
    assert state.admin_error == "开始日期格式应为 YYYY-MM-DD"
