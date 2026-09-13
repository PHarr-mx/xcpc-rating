"""audit API：写入、筛选（user/action/日期区间含当天）——盲区补齐。"""

from datetime import date, datetime, timezone

import pytest

from xcpc_core.audit import api as audit_api
from xcpc_core.db.tables import AuditLog


@pytest.fixture
def audit_session(db_session):
    audit_api.configure_session(db_session)
    yield db_session
    audit_api.configure_session(None)


def test_record_writes_and_lists(audit_session):
    log_id = audit_api.record(
        action="player.create", target="p001", user_id=1, diff_json={"name": "张三"}
    )
    assert log_id > 0
    (entry,) = audit_api.list_logs()
    assert entry["action"] == "player.create"
    assert entry["target"] == "p001"
    assert entry["user_id"] == 1
    assert "张三" in entry["diff_json"]
    assert entry["at"]  # isoformat 时间串


def test_record_without_diff(audit_session):
    audit_api.record(action="contest.delete", target="c1", user_id=2)
    (entry,) = audit_api.list_logs()
    assert entry["diff_json"] == "{}"


def _insert_row(session, *, action: str, user_id: int, at: datetime) -> None:
    session.add(AuditLog(action=action, target="t", user_id=user_id, at=at, diff_json="{}"))
    session.flush()  # autoflush=False，手动刷出保证同会话 SELECT 可见


def test_filter_by_action_and_user(audit_session):
    _insert_row(audit_session, action="player.create", user_id=1, at=datetime(2026, 1, 5, tzinfo=timezone.utc))
    _insert_row(audit_session, action="team.create", user_id=2, at=datetime(2026, 1, 6, tzinfo=timezone.utc))

    assert [e["action"] for e in audit_api.list_logs(action="team.create")] == ["team.create"]
    assert [e["user_id"] for e in audit_api.list_logs(user_id=2)] == [2]
    assert len(audit_api.list_logs()) == 2


def test_filter_by_date_range_inclusive(audit_session):
    _insert_row(audit_session, action="a", user_id=1, at=datetime(2026, 1, 4, 23, 0, tzinfo=timezone.utc))
    _insert_row(audit_session, action="b", user_id=1, at=datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc))
    _insert_row(audit_session, action="c", user_id=1, at=datetime(2026, 1, 5, 23, 59, tzinfo=timezone.utc))
    _insert_row(audit_session, action="d", user_id=1, at=datetime(2026, 1, 6, 0, 0, tzinfo=timezone.utc))

    days = {e["action"] for e in audit_api.list_logs(date_from=date(2026, 1, 5), date_to=date(2026, 1, 5))}
    assert days == {"b", "c"}  # date_to 当天包含

    assert {e["action"] for e in audit_api.list_logs(date_from=date(2026, 1, 6))} == {"d"}
    assert {e["action"] for e in audit_api.list_logs(date_to=date(2026, 1, 4))} == {"a"}
