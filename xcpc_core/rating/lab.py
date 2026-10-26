"""权重试算（P6）：在草稿参数下重算榜单，与当前榜单 diff。

三条硬约束（docs/04 §4）：
1. **不落库** —— 试算只读事件流，不改任何表；
2. **不进缓存** —— 直接调 ``BoardService``，绕开 ``board.board()`` 的进程内缓存；
3. **应用才生效** —— :func:`apply_params` 写 YAML + bump ``data_version`` + 审计。

当前覆盖 **Rating 轨**（AtCoder 式公式参数）。积分轨的调参对象是逐场数据与
tier 系数而非全局常量，其系数调整走 ``/admin/tiers`` 既有 CRUD，不在本模块。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from xcpc_core.board.models import DEFAULT_ALGORITHM, BoardSnapshot
from xcpc_core.board.service import BoardService
from xcpc_core.db.meta import bump_data_version
from xcpc_core.db.session import make_session_factory
from xcpc_core.db.tables import Meta as MetaRow
from xcpc_core.player.store import find_repo_root
from xcpc_core.rating.api import configure_session as _configure_rating_session
from xcpc_core.rating.events import build_events_from_contests
from xcpc_core.rating.formula_params import DEFAULT, TUNABLE_FIELDS, FormulaParams
from xcpc_core.rating.models import PeriodFilter
from xcpc_core.rating.replay import AtcoderReplayEngine

PARAMS_FILE = Path("data/config/rating_params.yaml")

_default_session: Session | None = None


def configure_session(session: Session | None) -> None:
    global _default_session
    _default_session = session


def _resolve_session(session: Session | None) -> tuple[Session, bool]:
    resolved = session or _default_session
    if resolved is not None:
        return resolved, False
    return make_session_factory()[1](), True


# ---- 参数读写 ----


def load_applied_params(*, repo_root: Path | None = None) -> FormulaParams:
    """读 ``data/config/rating_params.yaml`` 的已应用参数；缺文件时用内置默认值。"""
    root = repo_root or find_repo_root()
    path = root / PARAMS_FILE
    if not path.is_file():
        return DEFAULT
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    stored = {key: float(value) for key, value in (data.get("formula") or {}).items()
              if key in TUNABLE_FIELDS and value is not None}
    return DEFAULT.with_overrides(**stored)


def apply_params(
    params: FormulaParams,
    *,
    session: Session | None = None,
    repo_root: Path | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """把试算参数落为**生产参数**：写 YAML + bump data_version + 审计。

    审计走 ``audit.record``（best-effort，失败不回滚业务），动作名 ``weights.apply``。
    """
    root = repo_root or find_repo_root()
    path = root / PARAMS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    previous = load_applied_params(repo_root=root)
    payload = {
        "version": 1,
        "formula": asdict(params),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(
        "# Rating 公式参数（由 /admin/rating 试算页「应用」写入）\n"
        + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    session, close = _resolve_session(session)
    try:
        diff = {
            key: {"from": getattr(previous, key), "to": getattr(params, key)}
            for key in TUNABLE_FIELDS
            if getattr(previous, key) != getattr(params, key)
        }
        bump_data_version(session)
        session.commit()
    finally:
        if close:
            session.close()

    _audit(params, diff, user_id=user_id, path=path)
    return {"path": str(path), "changed": diff}


def _audit(
    params: FormulaParams,
    diff: dict[str, Any],
    *,
    user_id: int | None,
    path: Path,
) -> None:
    """写 ``weights.apply`` 审计（best-effort：审计失败不影响参数已应用的事实）。"""
    if user_id is None:
        return
    try:
        from xcpc_core.audit.api import record as audit_record

        audit_record(
            action="weights.apply",
            target=str(path),
            user_id=user_id,
            diff_json={"params": asdict(params), "changed": diff},
        )
    except Exception:  # pragma: no cover - 审计不可用不应阻塞应用
        pass


# ---- 试算 ----


def _snapshot(
    session: Session,
    *,
    params: FormulaParams,
    period: PeriodFilter,
) -> BoardSnapshot:
    """用给定参数直接构榜（**不经过缓存**）。"""
    row = session.get(MetaRow, 1)
    data_version = row.data_version if row is not None else 0
    algorithm = row.rating_algorithm if row is not None else DEFAULT_ALGORITHM
    service = BoardService(session)
    # BoardService 内部自建引擎；此处临时覆盖其参数入口
    return service.build(
        mode="all",
        period=period,
        data_version=data_version,
        algorithm=algorithm,
        generated_at=datetime.now(timezone.utc),
        params=params,
    )


def preview(
    params: FormulaParams | None = None,
    *,
    period: PeriodFilter | None = None,
    session: Session | None = None,
    repo_root: Path | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """草稿参数下的榜单 + 与当前（已应用参数）逐人 diff。

    返回 ``{"algorithm", "params", "baseline_params", "rows": [...], "summary": {...}}``；
    ``rows`` 每项含 ``player_id/name/rating_base/rating_draft/delta/rank_base/rank_draft``。
    """
    draft = params or DEFAULT
    baseline = load_applied_params(repo_root=repo_root)
    period = period or PeriodFilter()
    session, close = _resolve_session(session)
    try:
        base_snapshot = _snapshot(session, params=baseline, period=period)
        draft_snapshot = _snapshot(session, params=draft, period=period)
    finally:
        if close:
            session.close()

    base_by_id = {row.player_id: row for row in base_snapshot.rows}
    draft_by_id = {row.player_id: row for row in draft_snapshot.rows}
    player_ids = list(dict.fromkeys([*base_by_id, *draft_by_id]))

    rows: list[dict[str, Any]] = []
    for player_id in player_ids:
        base = base_by_id.get(player_id)
        candidate = draft_by_id.get(player_id)
        if base is None or candidate is None:
            continue
        rows.append({
            "player_id": player_id,
            "name": candidate.name,
            "rank_base": base.rank,
            "rank_draft": candidate.rank,
            "rating_base": base.rating,
            "rating_draft": candidate.rating,
            "delta": round(candidate.rating - base.rating, 2),
            "events": candidate.event_count,
        })

    rows.sort(key=lambda item: item["rank_draft"])
    moved = sum(1 for item in rows if item["rank_base"] != item["rank_draft"])
    deltas = [abs(item["delta"]) for item in rows]
    summary = {
        "players": len(rows),
        "rank_changed": moved,
        "max_abs_delta": round(max(deltas), 2) if deltas else 0.0,
        "mean_abs_delta": round(sum(deltas) / len(deltas), 2) if deltas else 0.0,
        "params_changed": asdict(draft) != asdict(baseline),
    }
    return {
        "algorithm": base_snapshot.meta.algorithm,
        "params": asdict(draft),
        "baseline_params": asdict(baseline),
        "rows": rows[:limit],
        "summary": summary,
    }