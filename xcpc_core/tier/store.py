"""tier SQLAlchemy repository：ORM 行 ↔ 领域 DTO 的转换边界。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xcpc_core.db.tables import AwardLevel as AwardLevelRow
from xcpc_core.db.tables import Contest as ContestRow
from xcpc_core.db.tables import Tier as TierRow
from xcpc_core.tier.exceptions import DuplicateAwardLevelError, DuplicateTierError
from xcpc_core.tier.models import AwardLevel, AwardLevelCreate, Tier, TierCreate


class TierStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- 读 ----

    def get(self, tier_id: int) -> Tier | None:
        row = self.session.get(TierRow, tier_id)
        return self._to_tier(row) if row is not None else None

    def get_award_level(self, level_id: int) -> AwardLevel | None:
        row = self.session.get(AwardLevelRow, level_id)
        return self._to_award(row) if row is not None else None

    def find_by_name(self, name: str) -> Tier | None:
        row = self.session.scalar(select(TierRow).where(TierRow.name == name))
        return self._to_tier(row) if row is not None else None

    def find_award_by_name(self, name: str) -> AwardLevel | None:
        row = self.session.scalar(select(AwardLevelRow).where(AwardLevelRow.name == name))
        return self._to_award(row) if row is not None else None

    def list_tiers(self) -> list[Tier]:
        rows = self.session.scalars(
            select(TierRow).order_by(TierRow.sort_order, TierRow.id)
        ).all()
        return [self._to_tier(row) for row in rows]

    def list_award_levels(self) -> list[AwardLevel]:
        rows = self.session.scalars(
            select(AwardLevelRow).order_by(AwardLevelRow.sort_order, AwardLevelRow.id)
        ).all()
        return [self._to_award(row) for row in rows]

    def count_contests(self, tier_id: int) -> int:
        return len(self.session.scalars(
            select(ContestRow.id).where(ContestRow.tier_id == tier_id)
        ).all())

    # ---- 写 ----

    def insert(self, tier: TierCreate, *, commit: bool = True) -> Tier:
        row = TierRow(name=tier.name, coefficient=tier.coefficient, sort_order=tier.sort_order)
        self.session.add(row)
        self._commit(commit, DuplicateTierError(f"赛事等级已存在: {tier.name}"))
        self.session.refresh(row)
        return self._to_tier(row)

    def insert_award_level(self, level: AwardLevelCreate, *, commit: bool = True) -> AwardLevel:
        row = AwardLevelRow(
            name=level.name, base_points=level.base_points, sort_order=level.sort_order
        )
        self.session.add(row)
        self._commit(commit, DuplicateAwardLevelError(f"奖项等级已存在: {level.name}"))
        self.session.refresh(row)
        return self._to_award(row)

    def update(self, tier_id: int, *, name: str, coefficient: float, sort_order: int, commit: bool = True) -> Tier:
        row = self.session.get(TierRow, tier_id)
        if row is None:
            return None  # type: ignore[return-value]
        row.name = name
        row.coefficient = coefficient
        row.sort_order = sort_order
        self._commit(commit, DuplicateTierError(f"赛事等级已存在: {name}"))
        self.session.refresh(row)
        return self._to_tier(row)

    def update_award_level(
        self, level_id: int, *, name: str, base_points: float, sort_order: int, commit: bool = True
    ) -> AwardLevel | None:
        row = self.session.get(AwardLevelRow, level_id)
        if row is None:
            return None
        row.name = name
        row.base_points = base_points
        row.sort_order = sort_order
        self._commit(commit, DuplicateAwardLevelError(f"奖项等级已存在: {name}"))
        self.session.refresh(row)
        return self._to_award(row)

    def delete(self, tier_id: int, *, commit: bool = True) -> None:
        row = self.session.get(TierRow, tier_id)
        if row is None:
            return
        self.session.delete(row)
        self._commit(commit)

    def delete_award_level(self, level_id: int, *, commit: bool = True) -> None:
        row = self.session.get(AwardLevelRow, level_id)
        if row is None:
            return
        self.session.delete(row)
        self._commit(commit)

    # ---- 内部 ----

    @staticmethod
    def _to_tier(row: TierRow) -> Tier:
        return Tier(id=row.id, name=row.name, coefficient=row.coefficient, sort_order=row.sort_order)

    @staticmethod
    def _to_award(row: AwardLevelRow) -> AwardLevel:
        return AwardLevel(
            id=row.id, name=row.name, base_points=row.base_points, sort_order=row.sort_order
        )

    def _commit(self, commit: bool, duplicate_error: Exception | None = None) -> None:
        if not commit:
            # 供调用方随后 refresh/读取自增 id：先 flush 保证行已可见
            self.session.flush()
            return
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            if duplicate_error is not None:
                raise duplicate_error from None
            raise
