"""P-U3 通用比赛 JSON 导入（CONTEST_UNIFICATION_PLAN §7）。

与正式赛 xlsx 导入的关系：
- **复用**：姓名解析（``resolve_member_names``，含同名歧义与自动建档）、
  建队（``resolve_team``，member_key 身份 + 别名合并）、raw 归档读写、
  ``_contest_create_from_document`` 的统一比赛映射、tier 解析。
- **不复用**：xlsx 解析与奖项阈值推算（通用 JSON 由填写方直接给 award），
  以及 staged 五步流程（首版只做 API/CLI 入口，见模块尾部说明）。

设计要点：
- ``entity=team`` → 每行解析队员 → 建队/查队 → standing.team_id；
- ``entity=player`` → 每行恰好 1 人 → 不建队，standing.team_id 留空
  （``rating/events.py`` 按 ``player_ids`` 生成事件，个人场次本就无队伍实体）；
- 打星（``unofficial``）与正式赛同义：参与方程、先验记 Center、不入历史。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from xcpc_core.contest.api import save_contest
from xcpc_core.contest.models import ContestCreate, Standing
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.session import make_session_factory
from xcpc_core.importer.config import competition_year, load_default_player_grade, season_label
from xcpc_core.importer.formal import resolve_team
from xcpc_core.importer.formal_store import (
    CONTESTS_KIND,
    raw_contest_path,
    raw_contest_rel_path,
    save_raw_contest,
)
from xcpc_core.importer.models import (
    ContestJsonDocument,
    ContestJsonImportResult,
    CreatedPlayer,
    UnmatchedPlayer,
    UnmatchedTeam,
)
from xcpc_core.importer.players import resolve_default_grade, resolve_member_names
from xcpc_core.player.store import PlayerStore, find_repo_root
from xcpc_core.tier.api import ensure_fallback_tier, ensure_tier_for_contest_type, find_tier_by_name
from xcpc_core.team.service import TeamService
from xcpc_core.team.store import TeamStore, make_member_key
from xcpc_core.utils.plog import Plog


class ContestJsonNotFoundError(FileNotFoundError):
    """归档文件不存在。"""


def _resolve_session(session: Session | None) -> tuple[Session, bool]:
    if session is not None:
        return session, False
    return make_session_factory()[1](), True


def _resolve_tier(document: ContestJsonDocument, *, session: Session, repo_root: Path):
    """tier 名 / contest_type / 兜底，三档依次尝试。

    ``tier`` 写中文标签（如「新队员组」）时，若等级表里没有，会按 config 的 label
    反查类型 key 并自动补建——与正式赛走 ``ensure_tier_for_contest_type`` 的口径一致，
    避免「config 有、等级表被清空」时导入失败。
    """
    if document.tier:
        tier = find_tier_by_name(document.tier, session=session)
        if tier is not None:
            return tier
        from xcpc_core.tier.service import builtin_config_entries, load_config_weights

        config = load_config_weights(repo_root) or builtin_config_entries()
        for key, (label, _coefficient) in config.items():
            if label == document.tier:
                return ensure_tier_for_contest_type(key, repo_root=repo_root, session=session)
        raise ValueError(
            f"赛事等级不存在: {document.tier}"
            "（请在 /admin/tiers 先建，或改用 contest_type / config 中已有的等级标签）"
        )
    if document.contest_type:
        return ensure_tier_for_contest_type(document.contest_type, repo_root=repo_root, session=session)
    return ensure_fallback_tier(session=session)


def _build_standing_entry(
    row,
    *,
    player_ids: list[str],
    team_id: str | None,
) -> dict[str, Any]:
    """raw 归档中的一行成绩（与正式赛归档字段对齐，便于同一套 map 逻辑消费）。"""
    return {
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
        "score": row.score,
        "unofficial": row.unofficial,
    }


def _build_raw_document(
    document: ContestJsonDocument,
    *,
    tier_name: str,
    standings_entries: list[dict[str, Any]],
    unmatched_players: list[UnmatchedPlayer],
    unmatched_teams: list[UnmatchedTeam],
) -> dict[str, Any]:
    return {
        "contest_id": document.contest_id,
        "source_format": "contest_json",
        "title": document.title,
        "date": document.date.isoformat(),
        # format 保持 icpc|ioi 合法值，形式另存 entity —— 归档可被本模块原样再导入
        "format": document.format,
        "entity": document.entity,
        "tier": tier_name,
        "n_teams": document.n_teams or len(standings_entries),
        "school_teams_count": len(standings_entries),
        "max_value": document.max_value,
        "scoring": document.scoring,
        "counts_for_points": document.counts_for_points,
        "counts_for_ranking": document.counts_for_ranking,
        "allow_claims": document.allow_claims,
        "competition_year": competition_year(document.date),
        "season": season_label(document.date),
        "standings": standings_entries,
        "unmatched_players": [item.model_dump(mode="json") for item in unmatched_players],
        "unmatched_teams": [item.model_dump(mode="json") for item in unmatched_teams],
    }


def _contest_create_from_document(
    raw: dict[str, Any], *, source_file: str, tier_id: int, session: Session
) -> ContestCreate:
    """通用 JSON raw 文档 → 统一比赛 DTO。

    与正式赛版本的区别：``entity`` 与 ``format`` 来自文档而非硬编码 team/icpc，
    开关（counts_for_points/ranking、allow_claims、scoring）也由文档承载。
    """
    standings = [
        Standing(
            team_id=row.get("team_id"),
            team_name=row.get("team_name"),
            rank=row.get("rank"),
            school_rank=row.get("school_rank"),
            award=row.get("award"),
            solved=row.get("solved"),
            penalty=row.get("penalty"),
            score=row.get("score"),
            manually_added=row.get("manually_added", False),
            player_ids=row.get("player_ids") or [],
        )
        for row in raw.get("standings") or []
    ]
    max_value = raw.get("max_value")
    if max_value is None:
        max_value = max(
            (value for row in standings for value in (row.solved, row.score) if value is not None),
            default=None,
        )
    return ContestCreate(
        id=raw["contest_id"],
        title=raw["title"],
        date=date.fromisoformat(raw["date"]),
        format=raw.get("format", "icpc"),
        entity=raw.get("entity", "team"),
        tier_id=tier_id,
        n_teams=raw.get("n_teams"),
        school_teams_count=raw.get("school_teams_count"),
        max_value=max_value,
        scoring=raw.get("scoring", "formula"),
        counts_for_points=bool(raw.get("counts_for_points", False)),
        counts_for_ranking=bool(raw.get("counts_for_ranking", True)),
        allow_claims=bool(raw.get("allow_claims", True)),
        source_file=source_file,
        standings=standings,
    )


def import_contest_json(
    document: ContestJsonDocument | dict[str, Any] | Path | str,
    *,
    auto_create_players: bool = True,
    default_grade: int | None = None,
    plog: Plog | None = None,
    repo_root: Path | None = None,
    session: Session | None = None,
    write_raw: bool = True,
) -> ContestJsonImportResult:
    """导入一场通用比赛（任意赛制 × 无形式限制）。

    ``document`` 可以是已解析的 DTO、原始 dict，或指向模板 JSON 文件的路径。
    raw 归档写到 ``data/raw/contests/{contest_id}.json``（P-U3 统一目录）。
    """
    root = repo_root or find_repo_root()

    if isinstance(document, (str, Path)):
        from xcpc_core.importer.formal_store import load_raw_contest

        doc_path = Path(document)
        raw_input = load_raw_contest(doc_path)
        parsed = ContestJsonDocument.model_validate(raw_input)
    elif isinstance(document, ContestJsonDocument):
        parsed = document
    else:
        parsed = ContestJsonDocument.model_validate(document)

    session, close_session = _resolve_session(session)
    try:
        player_store = PlayerStore(session)
        team_store = TeamStore(session)
        team_service = TeamService(team_store)
        default_grade = load_default_player_grade(repo_root=root, override=default_grade)
        tier = _resolve_tier(parsed, session=session, repo_root=root)
        today = parsed.date

        standings_entries: list[dict[str, Any]] = []
        unmatched_players: list[UnmatchedPlayer] = []
        unmatched_teams: list[UnmatchedTeam] = []
        players_created: list[CreatedPlayer] = []
        teams_created: list[str] = []

        for row in parsed.standings:
            label = row.team_name or "、".join(row.members)
            player_ids, row_unmatched, row_created = resolve_member_names(
                contest_id=parsed.contest_id,
                team_name=label,
                rank=row.rank or 0,
                member_names=row.members,
                store=player_store,
                auto_create=auto_create_players,
                default_grade=default_grade,
                today=today,
                plog=plog,
            )
            unmatched_players.extend(row_unmatched)
            players_created.extend(row_created)

            if player_ids is None:
                reason = "姓名存在歧义，无法唯一匹配" if row_unmatched else "队员无法解析"
                unmatched_teams.append(
                    UnmatchedTeam(
                        contest_id=parsed.contest_id,
                        team_name=label,
                        members=row.members,
                        rank=row.rank or 0,
                        reason=reason,
                    )
                )
                if plog:
                    plog.warning("行未导入", name=label, members=row.members, reason=reason)
                continue

            if parsed.entity == "team":
                # 建队/查队与「是否新建」判断共用同一个 service，避免重复查询口径不一致
                is_new_team = team_service.find_by_member_key(make_member_key(player_ids)) is None
                team_id = resolve_team(player_ids, row.team_name or "", team_store)
                if is_new_team:
                    teams_created.append(team_id)
            else:
                team_id = None

            standings_entries.append(
                _build_standing_entry(row, player_ids=player_ids, team_id=team_id)
            )

        if not standings_entries:
            raise ValueError(
                f"没有任何成绩行可导入（{len(unmatched_teams)} 行未匹配，请检查姓名或开启自动建档）"
            )

        raw = _build_raw_document(
            parsed,
            tier_name=tier.name,
            standings_entries=standings_entries,
            unmatched_players=unmatched_players,
            unmatched_teams=unmatched_teams,
        )
        raw_rel = raw_contest_rel_path(parsed.contest_id, kind=CONTESTS_KIND)
        raw_path = raw_contest_path(root, parsed.contest_id, kind=CONTESTS_KIND)
        if write_raw:
            save_raw_contest(raw_path, raw)

        save_contest(
            _contest_create_from_document(raw, source_file=raw_rel, tier_id=tier.id, session=session),
            store=ContestStore(session),
        )

        result = ContestJsonImportResult(
            contest_id=parsed.contest_id,
            title=parsed.title,
            format=parsed.format,
            entity=parsed.entity,
            tier_name=tier.name,
            n_teams=raw["n_teams"],
            standings_imported=len(standings_entries),
            players_created=players_created,
            teams_created=sorted(set(teams_created)),
            unmatched_players=unmatched_players,
            unmatched_teams=unmatched_teams,
            raw_path=str(raw_path),
            source_file=raw_rel,
        )
        if plog:
            plog.info(
                "通用比赛导入完成",
                contest_id=parsed.contest_id,
                format=parsed.format,
                entity=parsed.entity,
                tier=tier.name,
                standings_imported=result.standings_imported,
                players_created=len(players_created),
                unmatched=len(unmatched_players) + len(unmatched_teams),
            )
        return result
    finally:
        if close_session:
            session.close()
