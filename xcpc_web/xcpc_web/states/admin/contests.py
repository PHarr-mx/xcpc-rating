"""Admin 比赛管理状态：列表、筛选与删除。"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth

from xcpc_core.audit import record as audit_record
from xcpc_core.contest import api as contest_api
from xcpc_core.contest.exceptions import ContestError, ContestNotFoundError

from xcpc_web.states.admin.base import AdminState

SOURCE_LABELS = {
    "formal": "正式赛",
    "training": "训练赛",
}


class AdminContestsState(AdminState):
    """``/admin/contests`` 状态。"""

    search: str = ""
    source_filter: str = "all"

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

    def set_search(self, value: str) -> None:
        self.search = value

    def set_source_filter(self, value: str) -> None:
        self.source_filter = value

    @rx.var(cache=False)
    def contests(self) -> list[dict]:
        """按 source_type 与文本条件筛选比赛。"""
        if not self.is_admin:
            return []
        source_type = None if self.source_filter == "all" else self.source_filter
        try:
            contests = contest_api.list_contests(source_type=source_type)
        except Exception:
            return []

        search = self.search.strip().casefold()
        result: list[dict] = []
        for contest in contests:
            view = self._contest_view(contest)
            haystack = " ".join(
                [
                    contest.id,
                    contest.title,
                    contest.source_type,
                    contest.contest_type or "",
                    contest.division or "",
                    contest.format,
                    contest.season,
                    str(contest.competition_year),
                    contest.source_file or "",
                ]
            ).casefold()
            if search and search not in haystack:
                continue
            result.append(view)
        return result

    @rx.var(cache=False)
    def contest_count(self) -> int:
        if not self.is_admin:
            return 0
        return len(self.contests)

    @rx.var(cache=False)
    def formal_count(self) -> int:
        if not self.is_admin:
            return 0
        return sum(item["source_type"] == "formal" for item in self.contests)

    @rx.var(cache=False)
    def training_count(self) -> int:
        if not self.is_admin:
            return 0
        return sum(item["source_type"] == "training" for item in self.contests)

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
                "source_type": detail.contest.source_type,
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
            "source_type": contest.source_type,
            "source_label": SOURCE_LABELS.get(contest.source_type, contest.source_type),
            "competition_year": contest.competition_year,
            "season": contest.season,
            "contest_type": contest.contest_type or "—",
            "division": contest.division or "—",
            "format": contest.format,
            "total_teams": contest.total_teams if contest.total_teams is not None else "—",
            "school_teams_count": (
                contest.school_teams_count
                if contest.school_teams_count is not None
                else "—"
            ),
            "rated": "是" if contest.rated else "否",
            "weight": contest.weight,
            "weight_source": contest.weight_source,
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
