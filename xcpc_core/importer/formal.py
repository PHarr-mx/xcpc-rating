from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from xcpc_core.importer.awards import assign_award
from xcpc_core.importer.config import competition_year, load_default_player_grade, season_label
from xcpc_core.importer.formal_store import (
    load_raw_contest,
    raw_contest_path,
    raw_contest_rel_path,
    save_raw_contest,
    update_standings_counts,
)
from xcpc_core.importer.models import (
    AddFormalTeamParams,
    AddFormalTeamResult,
    AwardThresholds,
    CreatedPlayer,
    FormalImportParams,
    FormalImportResult,
    UnmatchedPlayer,
    UnmatchedTeam,
    XcpcioParsedContest,
)
from xcpc_core.importer.players import resolve_default_grade, resolve_member_names
from xcpc_core.contest.api import save_contest
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore
from xcpc_core.importer.weights import load_formal_weight
from xcpc_core.importer.xcpcio_xlsx import parse_xcpcio_xlsx
from xcpc_core.player.store import PlayerStore, find_repo_root
from xcpc_core.team.models import TeamCreate
from xcpc_core.team.service import TeamService
from xcpc_core.team.store import TeamStore, make_member_key
from xcpc_core.utils.plog import Plog

from sqlalchemy.orm import Session

from xcpc_core.db.session import make_session_factory


def _resolve_session(session: Session | None) -> tuple[Session, bool]:
    """返回 (session, 是否需要关闭)。未提供时用默认工厂新建一个。"""
    if session is not None:
        return session, False
    return make_session_factory()[1](), True


def _player_store(session: Session) -> PlayerStore:
    return PlayerStore(session)


def _team_store(session: Session) -> TeamStore:
    return TeamStore(session)


def _contest_create_from_document(document: dict[str, Any], *, source_file: str) -> ContestCreate:
    """把 raw 正式赛文档映射为 ContestCreate，用于写入 SQLite。"""
    standings = [
        Standing(
            team_id=row.get("team_id"),
            team_name=row.get("team_name"),
            rank=row["rank"],
            school_rank=row.get("school_rank"),
            award=row.get("award"),
            solved=row.get("solved"),
            penalty=row.get("penalty"),
            score=row.get("score"),
            manually_added=row.get("manually_added", False),
            player_ids=row.get("player_ids") or [],
        )
        for row in document.get("standings") or []
    ]
    return ContestCreate(
        id=document["contest_id"],
        source_type="formal",
        title=document["title"],
        date=date.fromisoformat(document["date"]),
        contest_type=document.get("contest_type"),
        format=document.get("format", "team_xcpc"),
        total_teams=document.get("total_teams"),
        school_teams_count=document.get("school_teams_count"),
        rated=document.get("rated", True),
        weight=document.get("weight", 100),
        weight_source=document.get("weight_source", "config"),
        source_file=source_file,
        standings=standings,
    )


def resolve_team(
    player_ids: list[str],
    team_name: str,
    store: TeamStore,
) -> str:
    """查找或创建队伍，返回 team_id。

    队员相同但队名不同时，视为同一队伍，将新队名追加到 aliases。
    """
    member_key = make_member_key(player_ids)
    service = TeamService(store)
    team = service.find_by_member_key(member_key)
    if team:
        if team_name and team_name.strip() not in team.aliases:
            service.add_alias(team.id, team_name.strip())
        return team.id
    created = service.create_team(TeamCreate(
        members=player_ids,
        aliases=[team_name.strip()] if team_name and team_name.strip() else [],
    ))
    return created.id


def _build_standing_entry(
    *,
    row,
    player_ids: list[str],
    team_id: str,
    manually_added: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    entry = {
        "team_id": team_id,
        "team_name": row.team_name,
        "member_names": row.members,
        "player_ids": player_ids,
        "size": len(player_ids),
        "rank": row.rank,
        "school_rank": row.school_rank,
        "award": row.award,
        "solved": row.solved,
        "penalty": row.penalty,
        "unofficial": row.unofficial,
    }
    if manually_added:
        entry["manually_added"] = True
    if note:
        entry["note"] = note
    return entry


def _build_standing_entry_from_params(
    params: AddFormalTeamParams,
    *,
    player_ids: list[str],
    team_id: str,
    award: str,
) -> dict[str, Any]:
    entry = {
        "team_id": team_id,
        "team_name": params.team_name,
        "member_names": params.member_names,
        "player_ids": player_ids,
        "size": len(player_ids),
        "rank": params.rank,
        "school_rank": params.school_rank,
        "award": award,
        "solved": params.solved,
        "penalty": params.penalty,
        "unofficial": params.unofficial,
        "manually_added": True,
    }
    if params.note:
        entry["note"] = params.note
    return entry


def _resolve_award_for_team(
    *,
    solved: int,
    penalty: int,
    award: str | None,
    thresholds: AwardThresholds | None,
) -> str:
    if award is not None:
        return award
    if thresholds is None:
        raise ValueError("未指定 award 且 raw 文件中缺少 award_thresholds，无法推算获奖等级")
    resolved = assign_award(solved, penalty, thresholds)
    if resolved is None:
        raise ValueError(
            f"成绩 solved={solved} penalty={penalty} 未达到金/银/铜奖线，无法添加"
        )
    return resolved


def _contest_date(document: dict[str, Any]) -> date:
    raw_date = document.get("date")
    if not raw_date:
        raise ValueError("raw 文件缺少 date 字段")
    return date.fromisoformat(str(raw_date))


def _upsert_standing(standings: list[dict[str, Any]], entry: dict[str, Any]) -> bool:
    team_id = entry["team_id"]
    replaced = False
    for index, row in enumerate(standings):
        if row.get("team_id") == team_id:
            standings[index] = entry
            replaced = True
            break
    if not replaced:
        standings.append(entry)
    standings.sort(key=lambda item: item.get("rank", 0))
    return replaced


def _build_raw_document(
    parsed: XcpcioParsedContest,
    params: FormalImportParams,
    *,
    contest_meta: dict[str, Any],
    standings_entries: list[dict[str, Any]],
    unmatched_players: list[UnmatchedPlayer],
    unmatched_teams: list[UnmatchedTeam],
) -> dict[str, Any]:
    return {
        "contest_id": params.contest_id,
        "source_format": parsed.source_format,
        "title": parsed.title,
        "date": params.date.isoformat(),
        "contest_type": params.contest_type,
        "format": params.format,
        "total_teams": parsed.total_teams,
        "total_problems": parsed.total_problems,
        "school_teams_count": parsed.school_teams_total,
        "school_teams_awarded": len(standings_entries),
        "award_thresholds": (
            parsed.award_thresholds.model_dump(mode="json") if parsed.award_thresholds else None
        ),
        **contest_meta,
        "standings": standings_entries,
        "unmatched_players": [item.model_dump(mode="json") for item in unmatched_players],
        "unmatched_teams": [item.model_dump(mode="json") for item in unmatched_teams],
    }


def import_formal_xcpcio_xlsx(
    path: Path | str,
    params: FormalImportParams,
    *,
    plog: Plog | None = None,
    repo_root: Path | None = None,
    session: Session | None = None,
    write_raw: bool = True,
) -> FormalImportResult:
    root = repo_root or find_repo_root()
    path = Path(path)
    session, close_session = _resolve_session(session)
    player_store = _player_store(session)
    team_store = _team_store(session)
    default_grade = resolve_default_grade(params, repo_root=root)
    today = params.date

    parsed = parse_xcpcio_xlsx(
        path,
        school_organizations=params.school_organizations,
        standings_sheet=params.standings_sheet,
        total_teams_sheet=params.total_teams_sheet,
        include_unofficial=params.include_unofficial,
    )

    if plog:
        plog.info(
            "解析 xcpcio_xlsx 完成",
            title=parsed.title,
            total_teams=parsed.total_teams,
            total_problems=parsed.total_problems,
            school_teams_total=parsed.school_teams_total,
            school_teams_awarded=len(parsed.standings),
            award_source=parsed.award_thresholds.source if parsed.award_thresholds else None,
            auto_create_players=params.auto_create_players,
        )

    weight, contest_type_label = load_formal_weight(params.contest_type, repo_root=root)
    weight_source = "config"
    if params.weight_override is not None:
        weight = params.weight_override
        weight_source = "override"

    contest_meta = {
        "competition_year": competition_year(params.date),
        "season": season_label(params.date),
        "contest_type_label": contest_type_label,
        "format_label": "组队 XCPC",
        "rated": True,
        "weight": weight,
        "weight_source": weight_source,
    }
    if params.weight_override_reason:
        contest_meta["weight_override_reason"] = params.weight_override_reason

    standings_entries: list[dict[str, Any]] = []
    unmatched_players: list[UnmatchedPlayer] = []
    unmatched_teams: list[UnmatchedTeam] = []
    players_created: list[CreatedPlayer] = []

    for row in parsed.standings:
        player_ids, row_unmatched, row_created = resolve_member_names(
            contest_id=params.contest_id,
            team_name=row.team_name,
            rank=row.rank,
            member_names=row.members,
            store=player_store,
            auto_create=params.auto_create_players,
            default_grade=default_grade,
            today=today,
            plog=plog,
        )
        unmatched_players.extend(row_unmatched)
        players_created.extend(row_created)
        if player_ids is None:
            reason = "队员姓名存在歧义，无法唯一匹配" if row_unmatched else "队员无法解析"
            unmatched_teams.append(
                UnmatchedTeam(
                    contest_id=params.contest_id,
                    team_name=row.team_name,
                    members=row.members,
                    rank=row.rank,
                    reason=reason,
                )
            )
            if plog:
                plog.warning("队伍未导入", team_name=row.team_name, members=row.members, reason=reason)
            continue

        standings_entries.append(
            _build_standing_entry(
                row=row,
                player_ids=player_ids,
                team_id=resolve_team(player_ids, row.team_name, team_store),
            )
        )

    raw_rel = raw_contest_rel_path(params.contest_id)
    raw_path = raw_contest_path(root, params.contest_id)
    document = _build_raw_document(
        parsed,
        params,
        contest_meta=contest_meta,
        standings_entries=standings_entries,
        unmatched_players=unmatched_players,
        unmatched_teams=unmatched_teams,
    )
    if write_raw:
        save_raw_contest(raw_path, document)
    # 写入 SQLite（raw 归档与 DB 并存，DB 为运行时数据源）
    save_contest(_contest_create_from_document(document, source_file=raw_rel), store=ContestStore(session))

    result = FormalImportResult(
        contest_id=params.contest_id,
        title=parsed.title,
        total_teams=parsed.total_teams,
        school_teams_count=parsed.school_teams_total,
        standings_imported=len(standings_entries),
        players_created=players_created,
        unmatched_players=unmatched_players,
        unmatched_teams=unmatched_teams,
        raw_path=str(raw_path),
        source_file=raw_rel,
    )
    if plog:
        plog.info(
            "正式赛导入完成",
            contest_id=params.contest_id,
            standings_imported=result.standings_imported,
            players_created=len(players_created),
            unmatched_players=len(unmatched_players),
            unmatched_teams=len(unmatched_teams),
        )
    if close_session:
        session.close()
    return result


def add_formal_team(
    params: AddFormalTeamParams,
    *,
    plog: Plog | None = None,
    repo_root: Path | None = None,
    session: Session | None = None,
) -> AddFormalTeamResult:
    """向已有正式赛 raw 文件手动追加一支队伍（如未挂靠本校的打星队）。"""
    root = repo_root or find_repo_root()
    session, close_session = _resolve_session(session)
    raw_path = raw_contest_path(root, params.contest_id)
    document = load_raw_contest(raw_path)

    if document.get("contest_id") and document["contest_id"] != params.contest_id:
        raise ValueError(
            f"raw 文件 contest_id={document['contest_id']} 与参数 {params.contest_id} 不一致"
        )

    thresholds = None
    if document.get("award_thresholds"):
        thresholds = AwardThresholds.model_validate(document["award_thresholds"])
    award = _resolve_award_for_team(
        solved=params.solved,
        penalty=params.penalty,
        award=params.award,
        thresholds=thresholds,
    )

    player_store = _player_store(session)
    team_store = _team_store(session)
    default_grade = load_default_player_grade(repo_root=root, override=params.default_grade)
    today = _contest_date(document)

    player_ids, unmatched_players, players_created = resolve_member_names(
        contest_id=params.contest_id,
        team_name=params.team_name,
        rank=params.rank,
        member_names=params.member_names,
        store=player_store,
        auto_create=params.auto_create_players,
        default_grade=default_grade,
        today=today,
        plog=plog,
    )
    if player_ids is None:
        raise ValueError(
            "队员无法解析，请检查名册或开启 auto_create_players；"
            f"未匹配: {[item.name for item in unmatched_players]}"
        )

    entry = _build_standing_entry_from_params(
        params,
        player_ids=player_ids,
        team_id=resolve_team(player_ids, params.team_name, team_store),
        award=award,
    )
    standings = list(document.get("standings") or [])
    replaced = _upsert_standing(standings, entry)
    document["standings"] = standings
    update_standings_counts(document)
    save_raw_contest(raw_path, document)

    raw_rel = raw_contest_rel_path(params.contest_id)
    # 同步写入 SQLite
    save_contest(_contest_create_from_document(document, source_file=raw_rel), store=ContestStore(session))

    if plog:
        plog.info(
            "手动添加正式赛队伍",
            contest_id=params.contest_id,
            team_name=params.team_name,
            team_id=entry["team_id"],
            award=award,
            replaced=replaced,
            players_created=len(players_created),
        )

    if close_session:
        session.close()

    return AddFormalTeamResult(
        contest_id=params.contest_id,
        team_id=entry["team_id"],
        award=award,
        replaced=replaced,
        players_created=players_created,
        unmatched_players=unmatched_players,
        raw_path=str(raw_path),
        source_file=raw_rel,
    )
