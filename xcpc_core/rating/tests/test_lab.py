"""P6 权重试算：参数注入、试算不落库不进缓存、应用写 YAML + bump + 审计。"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml

from xcpc_core.board.api import board
from xcpc_core.contest.api import save_contest
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.tables import AuditLog, Contest, Team
from xcpc_core.db.tables import Meta as MetaRow
from xcpc_core.player.store import find_repo_root
from xcpc_core.rating import lab
from xcpc_core.rating.formula_params import DEFAULT, TUNABLE_FIELDS, FormulaParams


@pytest.fixture
def repo(tmp_path):
    real_root = find_repo_root()
    (tmp_path / "data/config").mkdir(parents=True)
    for name in ("contest_weights.yaml", "school.yaml"):
        shutil.copy(real_root / f"data/config/{name}", tmp_path / f"data/config/{name}")
    return tmp_path


@pytest.fixture(autouse=True)
def _wire_audit(db_session):
    """audit 走独立 configure_session 注入（与 web 层 convention 一致）。"""
    from xcpc_core.audit.api import configure_session as audit_configure

    audit_configure(db_session)
    yield
    audit_configure(None)


def _seed_two_contests(db_session) -> None:
    """两场比赛、两支队伍，确保重放链路有跨场历史（改衰减才可见差异）。"""
    from xcpc_core.db.tables import Player as PlayerRow

    for pid, name in [("p001", "甲"), ("p002", "乙"), ("p003", "丙"), ("p004", "丁")]:
        db_session.add(PlayerRow(id=pid, name=name, grade=2025, status="active"))
    for tid, key in [("t001", "p001|p002"), ("t002", "p003|p004")]:
        db_session.add(Team(id=tid, member_key=key, size=2))
    db_session.flush()

    store = ContestStore(db_session)
    for index, (cid, cdate) in enumerate(
        [("c1", date(2026, 3, 1)), ("c2", date(2026, 4, 1))], start=1
    ):
        save_contest(
            ContestCreate(
                id=cid,
                title=f"训练 {index}",
                date=cdate,
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
            ),
            store=store,
        )


# ---- 参数模型 ----


def test_params_validation():
    with pytest.raises(ValueError, match="time_decay"):
        FormulaParams(time_decay=1.0)
    with pytest.raises(ValueError, match="center"):
        FormulaParams(center=0)
    with pytest.raises(ValueError, match="logistic_odds"):
        FormulaParams(logistic_odds=1.0)


def test_with_overrides_immutable():
    changed = DEFAULT.with_overrides(center=1200.0)
    assert changed.center == 1200.0
    assert DEFAULT.center == 800.0, "默认值不可被修改"
    assert changed is not DEFAULT


def test_with_overrides_rejects_unknown_key():
    with pytest.raises(ValueError, match="未知公式参数"):
        DEFAULT.with_overrides(foo=1.0)


# ---- 试算：不落库、不进缓存 ----


def test_preview_does_not_persist_or_audit(repo, db_session):
    _seed_two_contests(db_session)
    before_meta = db_session.get(MetaRow, 1)
    before_version = before_meta.data_version if before_meta else 0
    before_audit = len(db_session.query(AuditLog).all())
    before_contests = len(db_session.query(Contest).all())

    result = lab.preview(DEFAULT.with_overrides(center=1200.0), repo_root=repo, session=db_session)

    assert result["summary"]["params_changed"] is True
    assert len(result["rows"]) == 4
    # 数据版本、审计、比赛表都没变
    meta = db_session.get(MetaRow, 1)
    assert (meta.data_version if meta else 0) == before_version
    assert len(db_session.query(AuditLog).all()) == before_audit
    assert len(db_session.query(Contest).all()) == before_contests


def test_preview_does_not_write_yaml(repo, db_session):
    _seed_two_contests(db_session)
    lab.preview(DEFAULT.with_overrides(center=1200.0), repo_root=repo, session=db_session)
    assert not (repo / lab.PARAMS_FILE).exists(), "试算不得落盘"


def test_preview_skips_board_cache(repo, db_session):
    """试算走 BoardService 直构，不读也不污染 board.api 的进程内缓存。"""
    _seed_two_contests(db_session)
    import xcpc_core.board.api as board_api

    baseline = board_api.board(session=db_session)  # 注入 session 本就不缓存
    lab.preview(DEFAULT.with_overrides(center=1200.0), repo_root=repo, session=db_session)
    again = board_api.board(session=db_session)
    assert [r.rating for r in again.rows] == [r.rating for r in baseline.rows]


def test_preview_diff_shape(repo, db_session):
    _seed_two_contests(db_session)
    result = lab.preview(DEFAULT.with_overrides(f_full=0.0), repo_root=repo, session=db_session)

    assert set(result) >= {"algorithm", "params", "baseline_params", "rows", "summary"}
    row = result["rows"][0]
    assert {"player_id", "name", "rank_base", "rank_draft", "rating_base", "rating_draft", "delta"} <= set(row)
    # f_full=0 → f(n) 归零：本组每人 2 场，原扣 f(2)≈745.41，故统一 +745.41
    from xcpc_core.rating.formula import f_correction

    expected = round(f_correction(2), 2)
    assert all(abs(item["delta"] - expected) < 0.02 for item in result["rows"]), result["rows"]


def test_preview_identity_params_zero_delta(repo, db_session):
    _seed_two_contests(db_session)
    result = lab.preview(DEFAULT, repo_root=repo, session=db_session)
    assert result["summary"]["params_changed"] is False
    assert all(item["delta"] == 0.0 for item in result["rows"])


# ---- 应用 ----


def test_apply_writes_yaml_bumps_and_audits(repo, db_session):
    _seed_two_contests(db_session)
    before = db_session.get(MetaRow, 1)
    before_version = before.data_version if before else 0

    applied = lab.apply_params(
        DEFAULT.with_overrides(center=1200.0, time_decay=0.85),
        repo_root=repo,
        session=db_session,
        user_id=7,
    )

    assert set(applied["changed"]) == {"center", "time_decay"}

    path = repo / lab.PARAMS_FILE
    assert path.is_file()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["formula"]["center"] == 1200.0
    assert data["formula"]["time_decay"] == 0.85

    meta = db_session.get(MetaRow, 1)
    assert meta.data_version == before_version + 1, "应用必须 bump data_version 使榜单缓存失效"

    actions = [row.action for row in db_session.query(AuditLog).all()]
    assert "weights.apply" in actions


def test_apply_then_load_roundtrip(repo, db_session):
    _seed_two_contests(db_session)
    target = DEFAULT.with_overrides(center=950.0, g_scale=700.0)
    lab.apply_params(target, repo_root=repo, session=db_session, user_id=1)

    loaded = lab.load_applied_params(repo_root=repo)
    assert loaded == target


def test_apply_makes_preview_baseline_track_it(repo, db_session):
    _seed_two_contests(db_session)
    lab.apply_params(DEFAULT.with_overrides(center=1200.0), repo_root=repo, session=db_session, user_id=1)

    # 应用后再用同一参数试算 → 与基线一致，delta 全 0
    result = lab.preview(DEFAULT.with_overrides(center=1200.0), repo_root=repo, session=db_session)
    assert result["summary"]["params_changed"] is False
    assert all(item["delta"] == 0.0 for item in result["rows"])


def test_load_applied_params_defaults_when_missing(repo):
    assert lab.load_applied_params(repo_root=repo) == DEFAULT


def test_load_applied_params_ignores_unknown_keys(repo):
    path = repo / lab.PARAMS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"version": 1, "formula": {"center": 900.0, "bogus": 1.0}}),
        encoding="utf-8",
    )
    loaded = lab.load_applied_params(repo_root=repo)
    assert loaded.center == 900.0
    assert loaded.logistic_scale == DEFAULT.logistic_scale


def test_tunable_fields_cover_all_params():
    assert set(TUNABLE_FIELDS) == set(FormulaParams.__dataclass_fields__)