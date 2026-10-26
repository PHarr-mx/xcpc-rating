"""积分页状态（/points）：我的认证、提交认证、个人/队伍积分榜。

权限纪律与 ProfileState 一致：认证主体一律取 ``bound_player_id``（服务端推导），
不接受客户端传入 player_id；队伍赛从本人现役队伍中选择（service 再校验成员身份）。
表单按比赛的计分方式切换：formula 场次填解题数/名次，award_only 场次选奖项。
"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth

import xcpc_core.contest.api as contest_api
import xcpc_core.points.api as points_api
from xcpc_core.points.models import PointsClaimCreate

from xcpc_web.states.auth import AuthState

STATUS_LABELS = {"staged": "待审核", "approved": "已通过", "rejected": "已驳回"}
AWARD_LABELS = {"gold": "金奖", "silver": "银奖", "bronze": "铜奖", "honorable": "优胜奖"}


class PointsState(AuthState):
    """``/points`` 状态。"""

    # 提交认证表单
    claim_contest: str = ""  # 下拉选项形如 "{contest_id}. {title}"
    claim_team_id: str = ""
    claim_value: str = ""
    claim_rank: str = ""
    claim_award: str = ""
    claim_note: str = ""
    claim_error: str = ""
    claim_feedback: str = ""

    def on_load(self):
        """页面加载：未登录重定向登录页。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        self.claim_error = ""
        self.claim_feedback = ""
        return None

    # ---- 表单 setter ----

    def set_claim_contest(self, value: str) -> None:
        self.claim_contest = value

    def set_claim_team_id(self, value: str) -> None:
        self.claim_team_id = value

    def set_claim_value(self, value: str) -> None:
        self.claim_value = value

    def set_claim_rank(self, value: str) -> None:
        self.claim_rank = value

    def set_claim_award(self, value: str) -> None:
        self.claim_award = value

    def set_claim_note(self, value: str) -> None:
        self.claim_note = value

    # ---- 展示 var ----

    @rx.var(cache=False)
    def contests(self) -> list[dict]:
        """可申报的比赛：允许申报且计入积分。"""
        if not self.is_authenticated:
            return []
        try:
            all_contests = contest_api.list_contests()
        except Exception:
            return []
        return [
            {
                "id": c.id,
                "title": c.title,
                "date_label": c.date.isoformat(),
                "entity": c.entity,
                "scoring": c.scoring,
                "max_value": c.max_value,
                "n_teams": c.n_teams,
            }
            for c in all_contests
            if c.allow_claims and c.counts_for_points
        ]

    @rx.var(cache=False)
    def contest_options(self) -> list[str]:
        return [f'{c["id"]}. {c["title"]}' for c in self.contests]

    @rx.var(cache=False)
    def award_options(self) -> list[str]:
        """奖项申报选项（奖项基线表 + 中文标签）。"""
        if not self.is_authenticated:
            return []
        try:
            from xcpc_core.tier import api as tier_api

            return [
                f'{a.name}. {AWARD_LABELS.get(a.name, a.name)}'
                for a in tier_api.list_award_levels()
            ]
        except Exception:
            return []

    @rx.var(cache=False)
    def selected_contest(self) -> dict | None:
        prefix = self.claim_contest.split(".", 1)[0].strip()
        for contest in self.contests:
            if contest["id"] == prefix:
                return contest
        return None

    @rx.var(cache=False)
    def selected_is_team(self) -> bool:
        contest = self.selected_contest
        return contest is not None and contest["entity"] == "team"

    @rx.var(cache=False)
    def selected_is_award_only(self) -> bool:
        contest = self.selected_contest
        return contest is not None and contest["scoring"] == "award_only"

    @rx.var(cache=False)
    def selected_hint(self) -> str:
        contest = self.selected_contest
        if contest is None:
            return ""
        if contest["scoring"] == "award_only":
            return "该比赛积分只由奖项决定：选择获奖等级即可，无需填解题数/名次。"
        max_value = contest["max_value"] if contest["max_value"] is not None else "?"
        n_teams = contest["n_teams"] if contest["n_teams"] is not None else "?"
        return f"解题数上限 {max_value}，名次范围 1~{n_teams}。"

    @rx.var(cache=False)
    def my_teams(self) -> list[dict]:
        """提交队伍认证时的可选队伍（本人现役成员身份）。"""
        if not self.is_authenticated or not self.is_bound:
            return []
        return points_api.player_teams(player_id=self.bound_player_id)

    @rx.var(cache=False)
    def my_team_options(self) -> list[str]:
        return [f'{t["team_id"]}. {t["name"]}' for t in self.my_teams]

    @rx.var(cache=False)
    def my_claims(self) -> list[dict]:
        if not self.is_authenticated or not self.is_bound:
            return []
        return [
            {
                "id": c.id,
                "contest_title": c.contest_title or c.contest_id,
                "entity_label": "队伍" if c.entity == "team" else "个人",
                "owner_label": c.team_name or c.player_name or "-",
                "result_label": (
                    AWARD_LABELS.get(c.award or "", c.award)
                    if c.award
                    else f'解 {c.value} · 第 {c.rank} 名'
                ),
                "status_label": STATUS_LABELS.get(c.status, c.status),
                "status": c.status,
            }
            for c in points_api.my_claims(player_id=self.bound_player_id)
        ]

    @rx.var(cache=False)
    def individual_board(self) -> list[dict]:
        if not self.is_authenticated:
            return []
        return [
            {
                "rank": row.rank,
                "player_id": row.player_id,
                "name": row.name,
                "points": f"{row.points:.1f}",
                "entry_count": row.entry_count,
            }
            for row in points_api.individual_leaderboard()
        ]

    @rx.var(cache=False)
    def team_board(self) -> list[dict]:
        if not self.is_authenticated:
            return []
        return [
            {
                "rank": row.rank,
                "name": row.name,
                "team_points": f"{row.team_points:.1f}",
                "member_points": f"{row.member_points:.1f}",
                "composite": f"{row.composite:.1f}",
                "members": "、".join(row.members),
            }
            for row in points_api.team_leaderboard()
        ]

    # ---- 事件 ----

    @rx.event
    def submit_claim(self):
        """提交认证：个人赛自动取绑定选手；队伍赛从本人现役队伍中选择。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        self.claim_error = ""
        self.claim_feedback = ""
        if not self.is_bound:
            self.claim_error = "请先在个人资料页完成选手绑定"
            return
        contest = self.selected_contest
        if contest is None:
            self.claim_error = "请选择比赛"
            return

        value: int | None = None
        rank: int | None = None
        award: str | None = None
        if contest["scoring"] == "award_only":
            award = self.claim_award.split(".", 1)[0].strip() or None
            if not award:
                self.claim_error = "请选择获奖等级"
                return
        else:
            try:
                value = int(self.claim_value.strip())
                rank = int(self.claim_rank.strip())
            except ValueError:
                self.claim_error = "解题数/得分与名次必须为正整数"
                return
            if value < 1 or rank < 1:
                self.claim_error = "解题数与名次至少为 1"
                return

        team_id = None
        if contest["entity"] == "team":
            prefix = self.claim_team_id.split(".", 1)[0].strip()
            team_id = prefix or None
            if not team_id:
                self.claim_error = "请选择所属队伍"
                return
        try:
            points_api.submit_claim(
                params=PointsClaimCreate(
                    contest_id=contest["id"],
                    value=value,
                    rank=rank,
                    award=award,
                    team_id=team_id,
                    note=self.claim_note.strip() or None,
                ),
                submitted_by=self.authenticated_user.id,
                submitter_player_id=self.bound_player_id,  # type: ignore[arg-type]
            )
        except Exception as exc:
            self.claim_error = str(exc)
            return
        self.claim_value = ""
        self.claim_rank = ""
        self.claim_award = ""
        self.claim_note = ""
        self.claim_feedback = "认证已提交，等待 admin 审核"
