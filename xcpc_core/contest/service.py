from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from xcpc_core.contest.exceptions import ContestNotFoundError
from xcpc_core.contest.models import Contest, ContestCreate, ContestDetail
from xcpc_core.contest.store import ContestStore
from xcpc_core.db.meta import bump_data_version
from xcpc_core.tier.service import TierService
from xcpc_core.tier.store import TierStore
from xcpc_core.utils.calendar import competition_year, season_label


class ContestService:
    def __init__(self, store: ContestStore | None = None, *, session: Session | None = None) -> None:
        self.store = store or ContestStore()

    def _resolve_tier_id(self, tier_id: int | None) -> int:
        """tier 未指定时落到「未分级」兜底等级；与比赛同会话，避免跨库写。"""
        if tier_id is not None:
            return tier_id
        return TierService(TierStore(self.store.session)).ensure_fallback().id

    def save_contest(self, data: ContestCreate, *, today: date | None = None, commit: bool = True) -> Contest:
        """保存比赛（含成绩）。已存在则整批替换 standings——重复导入以最新为准。

        tier_id 未指定时落到「未分级」兜底等级（系数 1.0），保证积分/排名公式总有系数可用。
        """
        contest = Contest(
            id=data.id,
            title=data.title,
            date=data.date,
            competition_year=competition_year(data.date),
            season=season_label(data.date),
            format=data.format,
            entity=data.entity,
            tier_id=self._resolve_tier_id(data.tier_id),
            n_teams=data.n_teams,
            school_teams_count=data.school_teams_count,
            max_value=data.max_value,
            scoring=data.scoring,
            counts_for_points=data.counts_for_points,
            counts_for_ranking=data.counts_for_ranking,
            allow_claims=data.allow_claims,
            source_file=data.source_file,
        )
        bump_data_version(self.store.session)
        if self.store.get(data.id) is None:
            self.store.insert(contest, data.standings, commit=commit)
        else:
            self.store.update(contest, data.standings, commit=commit)
        return contest

    def get_contest(self, contest_id: str) -> ContestDetail:
        contest = self.store.get(contest_id)
        if contest is None:
            raise ContestNotFoundError(contest_id)
        return ContestDetail(contest=contest, standings=self.store.list_standings(contest_id))

    def list_contests(self, *, tier_id: int | None = None) -> list[Contest]:
        return self.store.list_all(tier_id=tier_id)

    def delete_contest(self, contest_id: str) -> None:
        if self.store.get(contest_id) is None:
            return
        bump_data_version(self.store.session)
        self.store.delete(contest_id)
