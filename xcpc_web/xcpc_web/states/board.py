"""BoardState: board state management."""

from __future__ import annotations

import reflex as rx
from xcpc_core.board import api as board_api
from xcpc_core.rating.models import PeriodFilter


class BoardState(rx.State):
    """Board state management."""

    mode: str = "all"
    period_type: str = "career"
    period_id: str | int | None = None
    search: str = ""
    sort_by: str = "rating_desc"

    rows: list[dict] = []
    meta: dict | None = None

    def _get_period_filter(self) -> PeriodFilter:
        return PeriodFilter(
            type=self.period_type,
            id=self.period_id,
        )

    @rx.var(cache=True)
    def board_snapshot(self) -> dict:
        period = self._get_period_filter()
        snapshot = board_api.board(mode=self.mode, period=period)
        return {
            "meta": snapshot.meta.model_dump(),
            "rows": [row.model_dump() for row in snapshot.rows],
        }

    def _filter_and_sort_rows(self, rows: list[dict]) -> list[dict]:
        if self.search:
            search_lower = self.search.lower()
            rows = [
                row for row in rows
                if search_lower in row["player_id"].lower() or search_lower in row["name"].lower()
            ]

        if self.sort_by == "rating_desc":
            rows.sort(key=lambda x: (-x["rating"], x["player_id"]))
        elif self.sort_by == "rating_asc":
            rows.sort(key=lambda x: (x["rating"], x["player_id"]))
        elif self.sort_by == "name_asc":
            rows.sort(key=lambda x: (x["name"], x["player_id"]))
        elif self.sort_by == "name_desc":
            rows.sort(key=lambda x: (-ord(x["name"][0]) if x["name"] else 0, x["player_id"]))

        for i, row in enumerate(rows, 1):
            row["rank"] = i

        return rows

    def load_board(self):
        snapshot_data = self.board_snapshot
        domain_rows = snapshot_data["rows"]
        domain_meta = snapshot_data["meta"]

        self.rows = self._filter_and_sort_rows(domain_rows)
        self.meta = domain_meta

    def set_mode(self, mode: str):
        self.mode = mode
        self.load_board()

    def set_period(self, period_type: str, period_id: str | int | None = None):
        self.period_type = period_type
        self.period_id = period_id
        self.load_board()

    def set_search(self, search: str):
        self.search = search
        self.load_board()

    def set_sort(self, sort_by: str):
        self.sort_by = sort_by
        self.load_board()

    def on_load(self):
        self.load_board()
