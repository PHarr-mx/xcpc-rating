"""P6 权重试算页 State（/admin/rating）回归。"""

from __future__ import annotations

from datetime import date

import pytest

from xcpc_core.board import api as board_api
from xcpc_core.contest import api as contest_api
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.db.tables import AuditLog, Meta, Player, Team
from xcpc_core.rating import lab
from xcpc_core.rating.formula_params import DEFAULT

from xcpc_web.states.admin.rating import RatingLabState


def _seed(session) -> None:
    for pid, name in [("p001", "甲"), ("p002", "乙"), ("p003", "丙"), ("p004", "丁")]:
        session.add(Player(id=pid, name=name, grade=2025, status="active"))
    for tid, key in [("t001", "p001|p002"), ("t002", "p003|p004")]:
        session.add(Team(id=tid, member_key=key, size=2))
    session.flush()

    for index, cid in enumerate(["c1", "c2"], start=1):
        contest_api.save_contest(
            ContestCreate(
                id=cid,
                title=f"训练 {index}",
                date=date(2026, 3, index),
                format="icpc",
                entity="team",
                n_teams=2,
                max_value=5,
                counts_for_ranking=True,
                standings=[
                    Standing(team_id="t001", team_name="甲队", rank=1, solved=5, penalty=100,
                             player_ids=["p001", "p002"]),
                    Standing(team_id="t002", team_name="乙队", rank=2, solved=3, penalty=200,
                             player_ids=["p003", "p004"]),
                ],
            )
        )


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    """把 lab.PARAMS_FILE 重定向到临时目录，避免写真实 data/config。"""
    import xcpc_core.rating.lab as lab_module

    monkeypatch.setattr(lab_module, "PARAMS_FILE", tmp_path / "rating_params.yaml")
    return tmp_path


# ---- 权限守卫 ----


def test_non_admin_guarded(build_state, make_user, core_store):
    state = build_state(RatingLabState, make_user("member"))
    assert state.on_load() is not None
    assert state.run_preview() is not None


def test_anonymous_guarded(build_state, core_store):
    state = build_state(RatingLabState)
    assert state.on_load() is not None


# ---- on_load 载入已应用参数 ----


def test_on_load_fills_draft_from_baseline(build_state, make_user, core_store, repo_root):
    lab.apply_params(DEFAULT.with_overrides(center=999.0), user_id=1)
    state = build_state(RatingLabState, make_user("root", role="admin"))
    state.on_load()
    assert state.draft_center == "999.0"
    assert state.baseline_params["center"] == 999.0


# ---- 试算 ----


def test_run_preview_produces_rows_with_display_fields(
    build_state, make_user, core_store, repo_root
):
    _seed(core_store)
    state = build_state(RatingLabState, make_user("root", role="admin"))
    state.on_load()
    state.set_draft_f_full("0")
    assert state.run_preview() is None

    assert state.has_preview is True
    assert state.summary["players"] == 4
    row = state.preview_rows[0]
    # State 预算的展示字段（Var 里不能做数值比较）
    assert row["delta_text"].startswith("+")
    assert row["delta_tone"] == "green"
    assert row["rank_moved"] in (True, False)


def test_preview_rejects_invalid_number_without_raising(
    build_state, make_user, core_store, repo_root
):
    state = build_state(RatingLabState, make_user("root", role="admin"))
    state.on_load()
    state.set_draft_center("abc")
    assert state.run_preview() is None  # 返回 None 而非抛异常
    assert "不是合法数字" in state.admin_error
    assert state.preview_rows == []


def test_preview_rejects_out_of_range_param(build_state, make_user, core_store, repo_root):
    state = build_state(RatingLabState, make_user("root", role="admin"))
    state.on_load()
    state.set_draft_time_decay("1.5")
    state.run_preview()
    assert "time_decay" in state.admin_error


def test_preview_does_not_touch_db(build_state, make_user, core_store, repo_root):
    _seed(core_store)
    state = build_state(RatingLabState, make_user("root", role="admin"))
    state.on_load()
    before_audit = len(core_store.query(AuditLog).all())
    before_meta = core_store.get(Meta, 1)
    before_version = before_meta.data_version if before_meta else 0

    state.set_draft_center("1200")
    state.run_preview()

    assert len(core_store.query(AuditLog).all()) == before_audit
    meta = core_store.get(Meta, 1)
    assert (meta.data_version if meta else 0) == before_version


# ---- 应用 ----


def test_apply_writes_file_and_audits(build_state, make_user, core_store, repo_root):
    _seed(core_store)
    user = make_user("root", role="admin")
    state = build_state(RatingLabState, user)
    state.on_load()
    state.set_draft_center("1200")
    assert state.apply_draft() is None

    assert (repo_root / "rating_params.yaml").is_file()
    assert "已应用" in state.admin_feedback
    assert state.baseline_params["center"] == 1200.0

    actions = [row.action for row in core_store.query(AuditLog).all()]
    assert "weights.apply" in actions

    meta = core_store.get(Meta, 1)
    assert meta.data_version >= 1


def test_apply_without_change_reports_no_diff(build_state, make_user, core_store, repo_root):
    state = build_state(RatingLabState, make_user("root", role="admin"))
    state.on_load()
    state.apply_draft()
    assert "无变化" in state.admin_feedback


# ---- 重置 ----


def test_reset_to_baseline_restores_applied(build_state, make_user, core_store, repo_root):
    lab.apply_params(DEFAULT.with_overrides(center=950.0), user_id=1)
    state = build_state(RatingLabState, make_user("root", role="admin"))
    state.on_load()

    state.set_draft_center("1234")
    state.run_preview()
    assert state.previewed is True

    state.reset_to_baseline()
    assert state.draft_center == "950.0"
    assert state.previewed is False
    assert state.preview_rows == []


def test_reset_to_default_does_not_apply(build_state, make_user, core_store, repo_root):
    lab.apply_params(DEFAULT.with_overrides(center=950.0), user_id=1)
    state = build_state(RatingLabState, make_user("root", role="admin"))
    state.on_load()

    state.set_draft_center("1234")
    state.reset_to_default()
    assert state.draft_center == str(DEFAULT.center)
    # 已应用参数不变
    assert lab.load_applied_params().center == 950.0