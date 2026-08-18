"""View models: BoardRowView and conversion functions."""

from __future__ import annotations

from xcpc_core.board.models import BoardRow, BoardMeta


class BoardRowView:
    """Frontend view model for board rows."""

    def __init__(
        self,
        rank: int,
        player_id: str,
        name: str,
        grade_label: str,
        rating: float,
        event_count: int,
        delta_recent: float,
    ):
        self.rank = rank
        self.player极_id = player_id
        self.name = name
        self.grade_label = grade_label
        self.rating = rating
        self.event_count = event_count
        self.delta_recent = delta_recent

    @classmethod
    def from_domain(cls, domain_row: BoardRow) -> "BoardRowView":
        """Convert from domain model to view model."""
        return cls(
            rank=domain_row.rank,
            player_id=domain_row.player_id,
            name=domain_row.name,
            grade_label=domain_row.grade_label,
            rating=domain_row.rating,
            event_count=domain_row.event_count,
            delta_recent=domain_row.delta_recent,
        )


class BoardMetaView:
    """Frontend view model for board metadata."""

    def __init__(
        self,
        mode: str,
        period_type: str,
        period_label: str,
        algorithm: str,
        data_version: int,
        tie_break: str,
        generated_at: str,
    ):
        self.mode = mode
        self.period_type = period_type
        self.period_label = period_label
        self.algorithm = algorithm
        self.data_version = data_version
        self.tie_break = tie_break
        self.generated_at = generated_at

    @classmethod
    def from_domain(cls, domain_meta: BoardMeta极) -> "BoardMetaView":
        """Convert from domain model to view model."""
        return cls(
            mode=domain_meta.mode,
            period_type=domain_meta.period_type,
            period_label=domain_meta.period_label,
            algorithm=domain_meta.algorithm,
            data_version=domain_meta.data_version,
            tie_break=domain_meta.tie_break,
            generated_at=domain_meta.generated_at.isoformat(),
        )