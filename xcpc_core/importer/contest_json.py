"""P-U3 通用比赛 JSON 导入（wiki/比赛与导入 §3）。

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
from xcpc_core.db.tables import Contest as ContestRow
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
from xcpc_core.player.api import create_player, find_by_name
from xcpc_core.player.models import PlayerCreate, PlayerStatus
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


def _resolve_row_members(
    member_names: list[str],
    *,
    decisions: dict[str, dict[str, Any]],
    contest_id: str,
    team_name: str,
    rank: int,
    player_store: PlayerStore,
    auto_create: bool,
    default_grade: int,
    today: date,
    plog: Plog | None,
) -> tuple[list[str] | None, list[UnmatchedPlayer], list[CreatedPlayer], bool]:
    """逐名解析一行队员，**人工决议优先**。

    与 ``resolve_member_names`` 的区别：本函数按姓名逐个处理，已决议的姓名直接
    采用（指定 ID 或强制新建），未决议的走常规匹配；因此部分队员有决议时，
    其余队员仍能正常匹配，不会被整行拖累。

    返回 ``(player_ids | None, unmatched, created, blocked_by_ambiguity)``；
    ``player_ids`` 为 None 表示该行不可导入（有歧义未决议 / 有无法解析的姓名）。
    顺序与 ``member_names`` 一致。
    """
    ids: list[str] = []
    unmatched: list[UnmatchedPlayer] = []
    created: list[CreatedPlayer] = []
    blocked = False

    for name in member_names:
        decision = decisions.get(name)
        if decision:
            action = str(decision.get("action") or "").strip().lower()
            if action in {"new", "create", "新建"}:
                raw_grade = decision.get("grade")
                grade = int(raw_grade) if raw_grade is not None else default_grade
                player = create_player(
                    PlayerCreate(name=name, grade=grade, status=PlayerStatus.active),
                    today=today,
                    store=player_store,
                )
                created.append(
                    CreatedPlayer(
                        player_id=player.id, name=player.name,
                        team_name=team_name, contest_id=contest_id,
                    )
                )
                ids.append(player.id)
                if plog:
                    plog.info("按决议新建选手", name=name, player_id=player.id)
                continue
            target = str(decision.get("player_id") or decision.get("id") or "").strip()
            if target:
                ids.append(target)
                continue
            # 决议格式不对 → 视为无效，落到常规匹配
            if plog:
                plog.warning("决议无效，回退常规匹配", name=name, decision=decision)

        matches = find_by_name(name, store=player_store)
        if len(matches) == 1:
            ids.append(matches[0].id)
        elif len(matches) > 1:
            blocked = True
            unmatched.append(
                UnmatchedPlayer(
                    contest_id=contest_id, name=name, team_name=team_name, rank=rank
                )
            )
        elif auto_create:
            player = create_player(
                PlayerCreate(name=name, grade=default_grade, status=PlayerStatus.active),
                today=today,
                store=player_store,
            )
            created.append(
                CreatedPlayer(
                    player_id=player.id, name=player.name,
                    team_name=team_name, contest_id=contest_id,
                )
            )
            ids.append(player.id)
            if plog:
                plog.info("自动建档选手", name=name, player_id=player.id)
        else:
            unmatched.append(
                UnmatchedPlayer(
                    contest_id=contest_id, name=name, team_name=team_name, rank=rank
                )
            )

    if unmatched:
        return None, unmatched, created, blocked
    return ids, [], created, blocked


def preview_contest_json(
    document: ContestJsonDocument | dict[str, Any] | Path | str,
    *,
    repo_root: Path | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """**只读**预览：校验模板 + 尝试姓名匹配，不写库、不归档、不建档。

    Web 上传要在「确认写入」之前看到「谁会匹配、谁会新建、谁有歧义」，
    与正式赛 staged 的预览阶段等价，但通用 JSON 的元信息都在文件里，
    所以不需要元信息表单——只需一次只读匹配。
    """
    if isinstance(document, (str, Path)):
        from xcpc_core.importer.formal_store import load_raw_contest

        parsed = ContestJsonDocument.model_validate(load_raw_contest(Path(document)))
    elif isinstance(document, ContestJsonDocument):
        parsed = document
    else:
        parsed = ContestJsonDocument.model_validate(document)

    root = repo_root or find_repo_root()
    session, close_session = _resolve_session(session)
    try:
        player_store = PlayerStore(session)
        tier_name = _preview_tier_name(parsed, session=session, repo_root=root)

        rows: list[dict[str, Any]] = []
        will_create_players: list[str] = []
        ambiguous: list[dict[str, Any]] = []
        for index, row in enumerate(parsed.standings, start=1):
            label = row.team_name or "、".join(row.members)
            matched: list[dict[str, str]] = []
            row_unmatched: list[str] = []
            row_ambiguous: list[str] = []
            for name in row.members:
                found = find_by_name(name, store=player_store)
                if len(found) == 1:
                    matched.append({"name": name, "player_id": found[0].id})
                elif len(found) > 1:
                    row_ambiguous.append(name)
                else:
                    will_create_players.append(name)
                    row_unmatched.append(name)
            if row_ambiguous:
                ambiguous.append({
                    "row": index,
                    "name": label,
                    "members": row_ambiguous,
                    "candidates": {
                        name: [
                            {"player_id": p.id, "name": p.name, "grade": p.grade}
                            for p in find_by_name(name, store=player_store)
                        ]
                        for name in row_ambiguous
                    },
                })
            rows.append({
                "index": index,
                "name": label,
                "members": row.members,
                "rank": row.rank,
                "matched": matched,
                "to_create": row_unmatched,
                "ambiguous": row_ambiguous,
                "blocked": bool(row_ambiguous),
            })

        return {
            "contest_id": parsed.contest_id,
            "title": parsed.title,
            "date": parsed.date.isoformat(),
            "format": parsed.format,
            "entity": parsed.entity,
            "tier_name": tier_name,
            "scoring": parsed.scoring,
            "counts_for_points": parsed.counts_for_points,
            "counts_for_ranking": parsed.counts_for_ranking,
            "allow_claims": parsed.allow_claims,
            "n_teams": parsed.n_teams or len(parsed.standings),
            "max_value": parsed.max_value,
            "rows": rows,
            "players_to_create": sorted(set(will_create_players)),
            "ambiguous": ambiguous,
            "blocked_count": sum(1 for item in rows if item["blocked"]),
            "existing_contest": session.get(ContestRow, parsed.contest_id) is not None,
        }
    finally:
        if close_session:
            session.close()


def _preview_tier_name(
    document: ContestJsonDocument, *, session: Session, repo_root: Path
) -> str:
    """预览只解析等级名，**不建等级**（写入阶段才 ensure）。"""
    if document.tier:
        found = find_tier_by_name(document.tier, session=session)
        if found is not None:
            return found.name
        from xcpc_core.tier.service import builtin_config_entries, load_config_weights

        for label, _coefficient in (load_config_weights(repo_root) or builtin_config_entries()).values():
            if label == document.tier:
                return label
        raise ValueError(f"赛事等级不存在: {document.tier}")
    if document.contest_type:
        from xcpc_core.tier.service import builtin_config_entries, load_config_weights

        config = load_config_weights(repo_root) or builtin_config_entries()
        if document.contest_type not in config:
            raise ValueError(f"未知赛事类型: {document.contest_type}（config 中无对应等级）")
        return config[document.contest_type][0]
    return "未分级"


def import_contest_json(
    document: ContestJsonDocument | dict[str, Any] | Path | str,
    *,
    auto_create_players: bool = True,
    default_grade: int | None = None,
    decisions: dict[str, dict[str, Any]] | None = None,
    plog: Plog | None = None,
    repo_root: Path | None = None,
    session: Session | None = None,
    write_raw: bool = True,
) -> ContestJsonImportResult:
    """导入一场通用比赛（任意赛制 × 无形式限制）。

    ``document`` 可以是已解析的 DTO、原始 dict，或指向模板 JSON 文件的路径。
    raw 归档写到 ``data/raw/contests/{contest_id}.json``（P-U3 统一目录）。

    ``decisions`` 为**姓名歧义的人工决议**（与 xlsx staged 同口径）：
    ``{"张三": {"player_id": "p001"}}`` 指定已有选手，或
    ``{"张三": {"action": "new", "grade": 2025}}`` 强制新建。未提供决议的歧义行
    仍按旧行为跳过并报告。
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
            # 人工决议优先：已决议的姓名直接取 ID（或强制新建），并保持原始顺序
            player_ids, row_unmatched, row_created, row_blocked = _resolve_row_members(
                row.members,
                decisions=decisions or {},
                contest_id=parsed.contest_id,
                team_name=label,
                rank=row.rank or 0,
                player_store=player_store,
                auto_create=auto_create_players,
                default_grade=default_grade,
                today=today,
                plog=plog,
            )
            unmatched_players.extend(row_unmatched)
            players_created.extend(row_created)

            if player_ids is None:
                reason = "姓名存在歧义且未提供决议" if row_blocked else "队员无法解析"
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
