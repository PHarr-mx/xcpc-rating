"""BoardState: board state management."""

from __future__ import annotations

import urllib.parse

import reflex as rx
from xcpc_core.board import api as board_api
from xcpc_core.rating.models import PeriodFilter

# URL query 白名单（docs/14 P1 任务 6）：非法值一律忽略，回落默认
_VALID_MODES = {"all", "formal_only"}
_VALID_PERIOD_TYPES = {"career", "competition_year", "season"}
_VALID_SORTS = {"rating_desc", "rating_asc", "name_asc", "name_desc"}


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

    @staticmethod
    def _board_url(mode: str, period_type: str, period_id, search: str) -> str:
        """当前筛选状态 → 带 query 的榜单 URL。默认值不出现在 URL，保持地址干净。"""
        params: list[str] = []
        if mode != "all":
            params.append(f"mode={mode}")
        if period_type != "career":
            params.append(f"period_type={period_type}")
        if period_id is not None and period_id != "":
            params.append(
                f"period_id={urllib.parse.quote(str(period_id), safe='')}"
            )
        if search:
            params.append(f"search={urllib.parse.quote(search, safe='')}")
        if not params:
            return "/"
        return "/?" + "&".join(params)

    def _sync_url(self):
        """筛选变化后把状态写回 URL（客户端导航，replace 不产生历史记录）。"""
        return rx.redirect(
            self._board_url(self.mode, self.period_type, self.period_id, self.search),
            replace=True,
        )

    def load_board(self):
        snapshot_data = self.board_snapshot
        domain_rows = snapshot_data["rows"]
        domain_meta = snapshot_data["meta"]

        self.rows = self._filter_and_sort_rows(domain_rows)
        self.meta = domain_meta

    def set_mode(self, mode: str):
        if mode not in _VALID_MODES:
            return
        self.mode = mode
        self.load_board()

    def set_period(self, period_type: str, period_id: str | int | None = None):
        if period_type not in _VALID_PERIOD_TYPES:
            return
        self.period_type = period_type
        self.period_id = period_id
        self.load_board()

    def set_search(self, search: str):
        self.search = search
        self.load_board()

    def set_sort(self, sort_by: str):
        if sort_by not in _VALID_SORTS:
            return
        self.sort_by = sort_by
        self.load_board()

    def on_load(self):
        """页面加载：先从 URL query 恢复筛选状态（非法值忽略），再渲染榜单。

        写回 URL 交给各 set_* 事件（返回值即事件，与原行为兼容）。
        """
        params = self.router.page.params
        mode = params.get("mode")
        if mode in _VALID_MODES:
            self.mode = mode
        period_type = params.get("period_type")
        if period_type in _VALID_PERIOD_TYPES:
            self.period_type = period_type
            # period_id 仅在赛年/赛季下有意义；career 显式忽略
            raw_period_id = params.get("period_id", "").strip()
            if raw_period_id:
                self.period_id = raw_period_id
        self.search = params.get("search", "")
        self.load_board()

    def set_mode_sync_url(self, mode: str):
        """UI 入口：改 mode 并同步 URL。"""
        self.set_mode(mode)
        return self._sync_url()

    def set_period_sync_url(self, period_type: str, period_id: str | int | None = None):
        """UI 入口：改周期并同步 URL。"""
        self.set_period(period_type, period_id)
        return self._sync_url()

    def set_search_sync_url(self, search: str):
        """UI 入口：改搜索词并同步 URL。"""
        self.set_search(search)
        return self._sync_url()
