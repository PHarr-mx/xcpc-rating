"""比赛详情页 State（P5）：路由参数 contest_id，加载元信息 + 成绩表。

路由参数 contest_id 由 Reflex 动态路由注入（勿声明同名 var）；统一从
router.page.params 读取。formal/training 同页，列形态由 contest.format 决定。
"""

from __future__ import annotations

import reflex as rx
from xcpc_core.contest import api as contest_api
from xcpc_core.contest.exceptions import ContestNotFoundError
from xcpc_core.player import api as player_api

from .auth import AuthState

_AWARD_LABELS = {"gold": "金奖", "silver": "银奖", "bronze": "铜奖", "honorable": "优胜奖"}
_FORMAT_LABELS = {"icpc": "ICPC 赛制", "ioi": "OI 赛制"}
_ENTITY_LABELS = {"team": "团队赛", "player": "个人赛"}
_SCORING_LABELS = {"formula": "按名次/解题计分", "award_only": "积分仅由奖项决定"}


class ContestDetailState(AuthState):
    """contest 为元信息视图 dict；standings 为成绩行视图（队员姓名已解析）。"""

    contest: dict | None = None
    standings: list[dict] = []
    not_found: bool = False

    @rx.var(cache=False)
    def is_oi(self) -> bool:
        """OI 赛制 → 成绩表切「得分」列；其余（icpc）显示解题+罚时。"""
        return bool(self.contest) and self.contest["format"] == "ioi"

    @rx.var(cache=False)
    def meta_line(self) -> str:
        """元信息一行：日期 · 形式 · 赛制 · 等级 · 实体数 · 计分方式。"""
        if not self.contest:
            return ""
        c = self.contest
        parts = [c["date"], c["entity_label"], c["type_label"]]
        if c["tier_label"]:
            parts.append(c["tier_label"])
        if c["n_teams"] is not None:
            parts.append(f"实体数 {c['n_teams']}")
        if c["school_teams_count"] is not None:
            parts.append(f"本校 {c['school_teams_count']} 队")
        parts.append(c["scoring_label"])
        return " · ".join(parts)

    def on_load(self) -> None:
        params = self.router.page.params
        contest_id = params.get("contest_id", "")
        self.contest = None
        self.standings = []
        self.not_found = False
        if not contest_id:
            self.not_found = True
            return
        try:
            detail = contest_api.get_contest(contest_id)
        except ContestNotFoundError:
            self.not_found = True
            return

        contest = detail.contest
        from xcpc_core.tier import api as tier_api

        tier = tier_api.get_tier(contest.tier_id) if contest.tier_id else None
        self.contest = {
            "id": contest.id,
            "title": contest.title,
            "date": contest.date.isoformat(),
            "format": contest.format,  # is_oi 判定用
            "type_label": _FORMAT_LABELS.get(contest.format, contest.format),
            "entity_label": _ENTITY_LABELS.get(contest.entity, contest.entity),
            "tier_label": tier.name if tier else "未分级",
            "scoring_label": _SCORING_LABELS.get(contest.scoring, contest.scoring),
            "n_teams": contest.n_teams,
            "school_teams_count": contest.school_teams_count,
        }

        # 队员姓名解析：历史成绩应能显示已离队选手的名字，故 include_left=True
        names = {p.id: p.name for p in player_api.list_players(include_left=True)}
        self.standings = [self._row_view(s, names) for s in detail.standings]

    @staticmethod
    def _row_view(standing, names: dict[str, str]) -> dict:
        """成绩行 → 视图 dict：姓名解析、打星标记、奖项中文，全部服务端预算。"""
        members = "、".join(names.get(pid, pid) for pid in standing.player_ids) or "—"
        team_name = standing.team_name or "—"
        if standing.manually_added:
            team_name += "（打星）"
        award = standing.award
        return {
            "rank": standing.rank,
            "team_name": team_name,
            "members": members,
            "solved": standing.solved,
            "penalty": standing.penalty,
            "score": standing.score,
            "school_rank": standing.school_rank,
            "award_label": (_AWARD_LABELS.get(award, award) if award else ""),
        }
