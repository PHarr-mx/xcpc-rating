"""P4c admin 赛事等级页（/admin/tiers）：CRUD + 审计。

之前本页没有任何测试，且写操作未接审计（2026-10-26 补齐）。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from xcpc_core.db.tables import AuditLog
from xcpc_core.tier import api as tier_api

from xcpc_web.states.admin.tiers import AdminTiersState


def _actions(session) -> list[str]:
    return [row.action for row in session.scalars(select(AuditLog)).all()]


# ---- 权限守卫 ----


def test_non_admin_guarded(build_state, make_user, core_store):
    st = build_state(AdminTiersState, make_user("member"))
    assert st.on_load() is not None
    assert st.tiers == []


# ---- 等级 CRUD ----


def test_create_tier_writes_audit(build_state, make_user, core_store):
    st = build_state(AdminTiersState, make_user("root", role="admin"))
    st.set_form_tier_name("测试等级")
    st.set_form_tier_coefficient("1.2")
    st.set_form_tier_sort("5")
    assert st.save_tier() is None

    assert "已创建" in st.admin_feedback
    assert "tier.create" in _actions(core_store)

    tiers = tier_api.list_tiers()
    created = [t for t in tiers if t.name == "测试等级"]
    assert len(created) == 1
    assert created[0].coefficient == pytest.approx(1.2)


def test_update_tier_records_before_after(build_state, make_user, core_store):
    tier = tier_api.create_tier(tier_api.TierCreate(name="旧名", coefficient=0.5))
    st = build_state(AdminTiersState, make_user("root", role="admin"))
    st.edit_tier(tier.id)
    st.set_form_tier_coefficient("0.75")
    assert st.save_tier() is None

    assert "已更新" in st.admin_feedback
    logs = [r for r in core_store.scalars(select(AuditLog)).all() if r.action == "tier.update"]
    assert len(logs) == 1
    import json

    diff = json.loads(logs[0].diff_json)
    assert diff["coefficient"] == {"from": 0.5, "to": 0.75}, "更新审计必须留前后值"


def test_delete_tier_writes_audit(build_state, make_user, core_store):
    tier = tier_api.create_tier(tier_api.TierCreate(name="待删", coefficient=1.0))
    st = build_state(AdminTiersState, make_user("root", role="admin"))
    st.delete_tier(tier.id)

    assert "已删除" in st.admin_feedback
    assert "tier.delete" in _actions(core_store)


def test_create_tier_rejects_blank_name(build_state, make_user, core_store):
    st = build_state(AdminTiersState, make_user("root", role="admin"))
    st.set_form_tier_name("   ")
    st.save_tier()
    assert "请填写等级名称" in st.admin_error
    assert _actions(core_store) == [], "校验失败不应留审计"


# ---- 奖项 CRUD ----


def test_create_award_writes_audit(build_state, make_user, core_store):
    st = build_state(AdminTiersState, make_user("root", role="admin"))
    st.set_form_award_name("platinum")
    st.set_form_award_points("200")
    st.set_form_award_sort("0")
    assert st.save_award() is None

    assert "已创建" in st.admin_feedback
    assert "award.create" in _actions(core_store)


def test_update_award_writes_audit(build_state, make_user, core_store):
    level = tier_api.create_award_level(
        tier_api.AwardLevelCreate(name="gold", base_points=100)
    )
    st = build_state(AdminTiersState, make_user("root", role="admin"))
    st.edit_award(level.id)
    st.set_form_award_points("150")
    st.save_award()

    assert "已更新" in st.admin_feedback
    assert "award.update" in _actions(core_store)


def test_delete_award_writes_audit(build_state, make_user, core_store):
    level = tier_api.create_award_level(
        tier_api.AwardLevelCreate(name="temp", base_points=10)
    )
    st = build_state(AdminTiersState, make_user("root", role="admin"))
    st.delete_award(level.id)

    assert "已删除" in st.admin_feedback
    assert "award.delete" in _actions(core_store)


def test_audit_failure_does_not_block_write(build_state, make_user, core_store, monkeypatch):
    """审计是 best-effort：写操作已成功时，审计异常不应回滚或报错。"""
    import xcpc_web.states.admin.tiers as tiers_module

    def boom(**kwargs):
        raise RuntimeError("audit down")

    monkeypatch.setattr(tiers_module, "audit_record", boom)

    st = build_state(AdminTiersState, make_user("root", role="admin"))
    st.set_form_tier_name("审计挂了也要建")
    st.set_form_tier_coefficient("1.0")
    assert st.save_tier() is None
    assert "已创建" in st.admin_feedback, "写入应成功"
    names = [t.name for t in tier_api.list_tiers()]
    assert "审计挂了也要建" in names