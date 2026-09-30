"""Admin 比赛管理状态：统一创建表单 + 列表筛选与删除（/admin/contests）。"""

from __future__ import annotations

from datetime import date

import reflex as rx
import reflex_local_auth

from xcpc_core.audit import record as audit_record
from xcpc_core.contest import api as contest_api
from xcpc_core.contest.exceptions import ContestError, ContestNotFoundError
from xcpc_core.contest.models import ContestCreate
from xcpc_core.tier import api as tier_api

from xcpc_web.states.admin.base import AdminState

FORMAT_LABELS = {"icpc": "ICPC", "ioi": "IOI"}
ENTITY_LABELS = {"player": "个人", "team": "团队"}
SCORING_LABELS = {"formula": "按名次/解题", "award_only": "仅按奖项"}


class AdminContestsState(AdminState):
    """``/admin/contests`` 状态。"""

    search: str = ""

    # 统一创建表单
    form_contest_id: str = ""
    form_title: str = ""
    form_date: str = ""
    form_format: str = "icpc"
    form_entity: str = "team"
    form_tier: str = ""  # 选项形如 "7. ICPC 省赛"
    form_n_teams: str = ""
    form_max_value: str = ""
    form_scoring: str = "formula"
    form_counts_for_points: bool = True
    form_counts_for_ranking: bool = False
    form_allow_claims: bool = True

    admin_feedback: str = ""
    admin_error: str = ""

    def on_load(self):
        """第 1 层守卫：非 admin 重定向。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        self.admin_feedback = ""
        self.admin_error = ""
        return None

    # ---- 表单 setter ----

    def set_search(self, value: str) -> None:
        self.search = value

    def set_form_contest_id(self, value: str) -> None:
        self.form_contest_id = value

    def set_form_title(self, value: str) -> None:
        self.form_title = value

    def set_form_date(self, value: str) -> None:
        self.form_date = value

    def set_form_format(self, value: str) -> None:
        self.form_format = value

    def set_form_entity(self, value: str) -> None:
        self.form_entity = value

    def set_form_tier(self, value: str) -> None:
        self.form_tier = value

    def set_form_n_teams(self, value: str) -> None:
        self.form_n_teams = value

    def set_form_max_value(self, value: str) -> None:
        self.form_max_value = value

    def set_form_scoring(self, value: str) -> None:
        self.form_scoring = value

    def set_form_counts_for_points(self, value: bool) -> None:
        self.form_counts_for_points = value

    def set_form_counts_for_ranking(self, value: bool) -> None:
        self.form_counts_for_ranking = value

    def set_form_allow_claims(self, value: bool) -> None:
        self.form_allow_claims = value

    # ---- 展示 var ----

    @rx.var(cache=False)
    def tier_options(self) -> list[str]:
        if not self.is_admin:
            return []
        try:
            return [f"{t.id}. {t.name}" for t in tier_api.list_tiers()]
        except Exception:
            return []

    def _selected_tier_id(self) -> int | None:
        prefix = self.form_tier.split(".", 1)[0].strip()
        return int(prefix) if prefix.isdigit() else None

    @rx.var(cache=False)
    def contests(self) -> list[dict]:
        """全部比赛（按文本条件筛选）。"""
        if not self.is_admin:
            return []
        try:
            contests = contest_api.list_contests()
        except Exception:
            return []

        search = self.search.strip().casefold()
        result: list[dict] = []
        for contest in contests:
            haystack = " ".join(
                [
                    contest.id,
                    contest.title,
                    contest.format,
                    contest.entity,
                    contest.season,
                    str(contest.competition_year),
                    contest.source_file or "",
                ]
            ).casefold()
            if search and search not in haystack:
                continue
            result.append(self._contest_view(contest))
        return result

    @rx.var(cache=False)
    def contest_count(self) -> int:
        if not self.is_admin:
            return 0
        return len(self.contests)

    @rx.var(cache=False)
    def points_count(self) -> int:
        if not self.is_admin:
            return 0
        return sum(item["counts_for_points"] == "计入" for item in self.contests)

    @rx.var(cache=False)
    def ranking_count(self) -> int:
        if not self.is_admin:
            return 0
        return sum(item["counts_for_ranking"] == "计入" for item in self.contests)

    # ---- 事件 ----

    @rx.event
    def create_contest(self):
        """统一入口创建比赛（无成绩数据；数据随后经导入或选手申报进入）。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_feedback = ""
        self.admin_error = ""
        contest_id = self.form_contest_id.strip()
        title = self.form_title.strip()
        if not contest_id or not title:
            self.admin_error = "请填写比赛 ID 与名称"
            return
        try:
            contest_date = date.fromisoformat(self.form_date.strip())
        except ValueError:
            self.admin_error = "日期格式应为 YYYY-MM-DD"
            return
        n_teams = int(self.form_n_teams.strip()) if self.form_n_teams.strip() else None
        max_value = int(self.form_max_value.strip()) if self.form_max_value.strip() else None
        try:
            saved = contest_api.save_contest(ContestCreate(
                id=contest_id,
                title=title,
                date=contest_date,
                format=self.form_format,  # type: ignore[arg-type]
                entity=self.form_entity,  # type: ignore[arg-type]
                tier_id=self._selected_tier_id(),
                n_teams=n_teams,
                max_value=max_value,
                scoring=self.form_scoring,  # type: ignore[arg-type]
                counts_for_points=self.form_counts_for_points,
                counts_for_ranking=self.form_counts_for_ranking,
                allow_claims=self.form_allow_claims,
            ))
        except Exception as exc:
            self.admin_error = str(exc)
            return

        self._write_audit(
            action="contest.create",
            target=contest_id,
            diff={
                "title": title,
                "format": self.form_format,
                "entity": self.form_entity,
                "scoring": self.form_scoring,
                "counts_for_points": self.form_counts_for_points,
                "counts_for_ranking": self.form_counts_for_ranking,
            },
        )
        self.admin_feedback = f"已创建比赛「{saved.title}」（{saved.id}）"
        self.form_contest_id = ""
        self.form_title = ""
        self.form_date = ""
        self.form_n_teams = ""
        self.form_max_value = ""

    @rx.event
    def delete_contest(self, contest_id: str):
        """通过 contest.api 删除比赛及其 standings。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_feedback = ""
        self.admin_error = ""
        try:
            detail = contest_api.get_contest(contest_id)
        except ContestNotFoundError as exc:
            self.admin_error = str(exc)
            return
        try:
            contest_api.delete_contest(contest_id)
        except ContestError as exc:
            self.admin_error = str(exc)
            return

        self._write_audit(
            action="contest.delete",
            target=contest_id,
            diff={
                "title": detail.contest.title,
                "date": detail.contest.date.isoformat(),
                "standings_count": len(detail.standings),
            },
        )
        self.admin_feedback = f"已删除比赛：{detail.contest.title}（{contest_id}）"

    @staticmethod
    def _contest_view(contest) -> dict:
        return {
            "id": contest.id,
            "title": contest.title,
            "date": contest.date.isoformat(),
            "season": contest.season,
            "format_label": FORMAT_LABELS.get(contest.format, contest.format),
            "entity_label": ENTITY_LABELS.get(contest.entity, contest.entity),
            "scoring_label": SCORING_LABELS.get(contest.scoring, contest.scoring),
            "n_teams": contest.n_teams if contest.n_teams is not None else "—",
            "max_value": contest.max_value if contest.max_value is not None else "—",
            "counts_for_points": "计入" if contest.counts_for_points else "不计",
            "counts_for_ranking": "计入" if contest.counts_for_ranking else "不计",
            "allow_claims": "可申报" if contest.allow_claims else "不申报",
            "source_file": contest.source_file or "—",
        }

    def _write_audit(self, *, action: str, target: str, diff: dict) -> None:
        try:
            audit_record(
                action=action,
                target=target,
                user_id=self.authenticated_user.id,
                diff_json=diff,
            )
        except Exception:
            pass
