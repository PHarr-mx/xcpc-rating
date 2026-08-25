"""在线正式赛导入的 staged 流程。

这个模块把旧的 ``import_formal_xcpcio_xlsx`` 拆成三步：

1. ``stage_formal_xlsx`` 只解析 xlsx、匹配已有选手并写入 ``ImportBatch``；
2. 管理员提交姓名决议（新建或已有 player id）；
3. ``confirm_import_batch`` 在同一个 core DB 事务中创建选手/队伍、保存 raw 和正式比赛。

解析阶段绝不写 Player、Team、Contest，因而关闭页面不会留下半截正式数据。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.service import ContestService
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.tables import ImportBatch
from xcpc_core.importer.config import (
    competition_year,
    load_default_player_grade,
    season_label,
)
from xcpc_core.importer.formal import _build_raw_document
from xcpc_core.importer.formal_store import (
    raw_contest_path,
    raw_contest_rel_path,
    save_raw_contest,
)
from xcpc_core.importer.models import (
    CreatedPlayer,
    FormalImportParams,
    FormalImportResult,
    ImportBatchDetail,
    ImportBatchSummary,
    StagedImportPayload,
    StagedStanding,
    UnmatchedPlayer,
    UnmatchedTeam,
    XcpcioParsedContest,
)
from xcpc_core.importer.weights import load_formal_weight
from xcpc_core.importer.xcpcio_xlsx import parse_xcpcio_xlsx
from xcpc_core.player.models import PlayerCreate, PlayerStatus
from xcpc_core.player.service import PlayerService
from xcpc_core.player.store import PlayerStore, find_repo_root
from xcpc_core.team.models import TeamCreate
from xcpc_core.team.service import TeamService
from xcpc_core.team.store import TeamStore, make_member_key


def _summary(batch_id: int, payload: StagedImportPayload, *, filename: str, status: str) -> ImportBatchSummary:
    return ImportBatchSummary(
        batch_id=batch_id,
        filename=filename,
        status=status,
        contest_id=payload.params.contest_id,
        title=payload.parsed.title,
        total_teams=payload.parsed.total_teams,
        school_teams_count=payload.parsed.school_teams_total,
        award_thresholds=payload.parsed.award_thresholds,
        standings_count=len(payload.standings),
        unmatched_players=payload.unmatched_players,
        unmatched_teams=payload.unmatched_teams,
    )


def _resolve_session(session: Session | None) -> tuple[Session, bool]:
    if session is not None:
        return session, False
    from xcpc_core.db.session import make_session_factory

    return make_session_factory()[1](), True


def _contest_meta(params: FormalImportParams, parsed: XcpcioParsedContest, *, repo_root: Path) -> dict[str, Any]:
    weight, label = load_formal_weight(params.contest_type, repo_root=repo_root)
    source = "config"
    if params.weight_override is not None:
        weight = params.weight_override
        source = "override"
    meta: dict[str, Any] = {
        "competition_year": competition_year(params.date),
        "season": season_label(params.date),
        "contest_type_label": label,
        "format_label": "组队 XCPC",
        "rated": True,
        "weight": weight,
        "weight_source": source,
    }
    if params.weight_override_reason:
        meta["weight_override_reason"] = params.weight_override_reason
    return meta


def _payload_from_xlsx(
    path: Path,
    params: FormalImportParams,
    *,
    session: Session,
    repo_root: Path,
) -> StagedImportPayload:
    parsed = parse_xcpcio_xlsx(
        path,
        school_organizations=params.school_organizations,
        standings_sheet=params.standings_sheet,
        total_teams_sheet=params.total_teams_sheet,
        include_unofficial=params.include_unofficial,
    )
    player_service = PlayerService(PlayerStore(session))
    staged_rows: list[StagedStanding] = []
    unmatched_players: list[UnmatchedPlayer] = []
    unmatched_teams: list[UnmatchedTeam] = []

    # 同一姓名在一批中只需要一次人工决议；候选列表保留在 payload 中供 UI 展示。
    seen_unmatched: set[str] = set()
    for row in parsed.standings:
        player_ids: list[str] = []
        unresolved: list[str] = []
        for name in row.members:
            matches = player_service.find_by_name(name)
            if len(matches) == 1:
                player_ids.append(matches[0].id)
                continue
            unresolved.append(name)
            if name not in seen_unmatched:
                seen_unmatched.add(name)
                unmatched_players.append(
                    UnmatchedPlayer(
                        contest_id=params.contest_id,
                        name=name,
                        team_name=row.team_name,
                        rank=row.rank,
                        candidates=[{"id": item.id, "name": item.name} for item in matches],
                    )
                )
        if unresolved:
            unmatched_teams.append(
                UnmatchedTeam(
                    contest_id=params.contest_id,
                    team_name=row.team_name,
                    members=row.members,
                    rank=row.rank,
                    reason="存在未匹配或有歧义的队员",
                )
            )
        staged_rows.append(
            StagedStanding(
                row=row,
                player_ids=player_ids,
                unresolved_names=unresolved,
            )
        )

    return StagedImportPayload(
        params=params,
        parsed=parsed,
        contest_meta=_contest_meta(params, parsed, repo_root=repo_root),
        standings=staged_rows,
        unmatched_players=unmatched_players,
        unmatched_teams=unmatched_teams,
    )


def stage_formal_xlsx(
    path: Path | str,
    params: FormalImportParams,
    *,
    uploaded_by: int,
    filename: str | None = None,
    repo_root: Path | None = None,
    session: Session | None = None,
) -> ImportBatchSummary:
    """解析 xlsx 并落一条 ``status=staged`` 的 ImportBatch。

    ``auto_create_players`` 在 staged 流程中被故意忽略：是否新建由确认时的
    ``decisions`` 明确指定，避免在线导入盲目建号。
    """
    root = repo_root or find_repo_root()
    session, close_session = _resolve_session(session)
    try:
        payload = _payload_from_xlsx(Path(path), params, session=session, repo_root=root)
        batch = ImportBatch(
            uploaded_by=uploaded_by,
            filename=filename or Path(path).name,
            status="staged",
            payload_json=json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
            created_at=datetime.now(timezone.utc),
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)
        return _summary(batch.id, payload, filename=batch.filename, status=batch.status)
    except Exception:
        session.rollback()
        raise
    finally:
        if close_session:
            session.close()


def get_import_batch(batch_id: int, *, session: Session | None = None) -> ImportBatchDetail:
    session, close_session = _resolve_session(session)
    try:
        row = session.get(ImportBatch, batch_id)
        if row is None:
            raise ValueError(f"导入批次不存在: {batch_id}")
        payload = StagedImportPayload.model_validate_json(row.payload_json)
        return ImportBatchDetail(
            batch_id=row.id,
            uploaded_by=row.uploaded_by,
            filename=row.filename,
            status=row.status,
            created_at=row.created_at,
            payload=payload,
        )
    finally:
        if close_session:
            session.close()


def list_import_batches(*, status: str | None = None, session: Session | None = None) -> list[ImportBatchDetail]:
    session, close_session = _resolve_session(session)
    try:
        stmt = select(ImportBatch).order_by(ImportBatch.id.desc())
        if status:
            stmt = stmt.where(ImportBatch.status == status)
        return [
            ImportBatchDetail(
                batch_id=row.id,
                uploaded_by=row.uploaded_by,
                filename=row.filename,
                status=row.status,
                created_at=row.created_at,
                payload=StagedImportPayload.model_validate_json(row.payload_json),
            )
            for row in session.scalars(stmt).all()
        ]
    finally:
        if close_session:
            session.close()


def discard_import_batch(batch_id: int, *, session: Session | None = None) -> None:
    session, close_session = _resolve_session(session)
    try:
        row = session.get(ImportBatch, batch_id)
        if row is None:
            raise ValueError(f"导入批次不存在: {batch_id}")
        if row.status != "staged":
            raise ValueError(f"导入批次 {batch_id} 当前状态为 {row.status}，不能取消")
        row.status = "discarded"
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if close_session:
            session.close()


def _decision_value(decisions: dict[str, Any], name: str) -> tuple[str, int | None]:
    value = decisions.get(name)
    if value is None:
        raise ValueError(f"未为选手“{name}”提交匹配决议")
    if isinstance(value, dict):
        action = str(value.get("action") or value.get("decision") or "").strip()
        grade = value.get("grade")
        if action in {"new", "create", "新建", "new_player"}:
            return "new", int(grade) if grade is not None else None
        value = value.get("player_id") or value.get("id")
    text = str(value).strip()
    if text in {"new", "create", "新建", "new_player"}:
        return "new", None
    if not text:
        raise ValueError(f"选手“{name}”的决议不能为空")
    return text, None


def confirm_import_batch(
    batch_id: int,
    decisions: dict[str, Any],
    *,
    repo_root: Path | None = None,
    session: Session | None = None,
) -> FormalImportResult:
    """确认 staged 批次，并在一次 core DB 事务中写入正式数据。"""
    root = repo_root or find_repo_root()
    session, close_session = _resolve_session(session)
    try:
        batch = session.get(ImportBatch, batch_id)
        if batch is None:
            raise ValueError(f"导入批次不存在: {batch_id}")
        if batch.status != "staged":
            raise ValueError(f"导入批次 {batch_id} 当前状态为 {batch.status}，不能确认")
        payload = StagedImportPayload.model_validate_json(batch.payload_json)
        params = payload.params
        default_grade = load_default_player_grade(repo_root=root, override=params.default_grade)

        player_service = PlayerService(PlayerStore(session))
        team_service = TeamService(TeamStore(session))
        resolved_by_name: dict[str, str] = {}
        players_created: list[CreatedPlayer] = []

        # 先完成并校验所有决议；任何不合法决议都会在写事务前失败。
        for item in payload.unmatched_players:
            decision, grade = _decision_value(decisions, item.name)
            if decision == "new":
                existing = player_service.find_by_name(item.name)
                if len(existing) > 1:
                    raise ValueError(f"选手“{item.name}”存在多个同名记录，请指定已有 player_id")
                if len(existing) == 1:
                    raise ValueError(f"选手“{item.name}”已存在，请指定已有 player_id")
                player = player_service.create_player(
                    PlayerCreate(
                        name=item.name,
                        grade=default_grade if grade is None else grade,
                        status=PlayerStatus.active,
                    ),
                    today=params.date,
                    commit=False,
                )
                session.flush()
                resolved_by_name[item.name] = player.id
                players_created.append(
                    CreatedPlayer(
                        player_id=player.id,
                        name=player.name,
                        team_name=item.team_name,
                        contest_id=params.contest_id,
                    )
                )
            else:
                player = player_service.get_player(decision)
                resolved_by_name[item.name] = player.id

        standings: list[Standing] = []
        raw_entries: list[dict[str, Any]] = []
        for staged in payload.standings:
            ids = list(staged.player_ids)
            for name in staged.unresolved_names:
                ids.append(resolved_by_name[name])
            if len(ids) != len(staged.row.members):
                raise ValueError(f"队伍“{staged.row.team_name}”队员决议不完整")
            member_key = make_member_key(ids)
            team = team_service.find_by_member_key(member_key)
            if team is None:
                team = team_service.create_team(
                    TeamCreate(members=ids, aliases=[staged.row.team_name]),
                    today=params.date,
                    commit=False,
                )
                session.flush()
            elif staged.row.team_name and staged.row.team_name not in team.aliases:
                team_service.add_alias(team.id, staged.row.team_name, today=params.date, commit=False)
            standings.append(
                Standing(
                    team_id=team.id,
                    team_name=staged.row.team_name,
                    rank=staged.row.rank,
                    school_rank=staged.row.school_rank,
                    award=staged.row.award,
                    solved=staged.row.solved,
                    penalty=staged.row.penalty,
                    player_ids=ids,
                )
            )
            raw_entries.append({
                "team_id": team.id,
                "team_name": staged.row.team_name,
                "member_names": staged.row.members,
                "player_ids": ids,
                "size": len(ids),
                "rank": staged.row.rank,
                "school_rank": staged.row.school_rank,
                "award": staged.row.award,
                "solved": staged.row.solved,
                "penalty": staged.row.penalty,
                "unofficial": staged.row.unofficial,
            })

        document = _build_raw_document(
            payload.parsed,
            params,
            contest_meta=payload.contest_meta,
            standings_entries=raw_entries,
            unmatched_players=[],
            unmatched_teams=[],
        )
        raw_rel = raw_contest_rel_path(params.contest_id)
        contest_data = ContestCreate(
            id=params.contest_id,
            source_type="formal",
            title=payload.parsed.title,
            date=params.date,
            contest_type=params.contest_type,
            format=params.format,
            total_teams=payload.parsed.total_teams,
            school_teams_count=payload.parsed.school_teams_total,
            rated=True,
            weight=int(payload.contest_meta["weight"]),
            weight_source=str(payload.contest_meta["weight_source"]),
            source_file=raw_rel,
            standings=standings,
        )
        ContestService(ContestStore(session)).save_contest(contest_data, today=params.date, commit=False)
        batch.status = "confirmed"
        batch.payload_json = json.dumps(
            payload.model_copy(update={"unmatched_players": [], "unmatched_teams": []}).model_dump(mode="json"),
            ensure_ascii=False,
        )
        session.commit()

        # raw 是归档文件，不参与 DB 写事务；DB 已成功后才写，避免 staged 失败时产生正式 raw。
        save_raw_contest(raw_contest_path(root, params.contest_id), document)
        return FormalImportResult(
            contest_id=params.contest_id,
            title=payload.parsed.title,
            total_teams=payload.parsed.total_teams,
            school_teams_count=payload.parsed.school_teams_total,
            standings_imported=len(standings),
            players_created=players_created,
            unmatched_players=[],
            unmatched_teams=[],
            raw_path=str(raw_contest_path(root, params.contest_id)),
            source_file=raw_rel,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        if close_session:
            session.close()
