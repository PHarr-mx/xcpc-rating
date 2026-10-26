"""权重试算页状态（/admin/rating，P6）。

试算走 ``xcpc_core.rating.lab``：草稿参数直接构榜（不落库、不进缓存），
与「已应用参数」的榜单逐人 diff；点「应用」才写 YAML + bump + 审计。
"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth

from xcpc_core.rating import lab
from xcpc_core.rating.formula_params import DEFAULT, TUNABLE_FIELDS, FormulaParams

from xcpc_web.states.admin.base import AdminState

#: 参数的可读标签与说明（顺序与 formula_params.TUNABLE_FIELDS 一致）
FIELD_META: dict[str, tuple[str, str]] = {
    "center": ("Center 锚点", "无历史选手的先验分；也是首场表现分的锚点"),
    "logistic_scale": ("Logistic 尺度", "实力差为该值时，期望对局赔率 = odds"),
    "logistic_odds": ("赔率基数", "名次反解方程中的 odds^((X−APerf)/scale) 底数"),
    "g_scale": ("g 变换尺度", "g(X)=2^(X/g_scale)，决定「赢大分、输小分」的强度"),
    "time_decay": ("时间衰减", "0.9^i 中的底数，越小则旧比赛越快失效"),
    "first_perf_inflation": ("首场膨胀", "实体首场表现分相对 Center 的放大倍数"),
    "f_full": ("f(n) 满额", "首场扣减值，随场次增加衰减到 0（初始分收敛）"),
}


def _decorate(row: dict) -> dict:
    """给 diff 行补上展示用派生字段（Var 里不能做数值比较，故在 State 预算）。"""
    delta = row["delta"]
    return {
        **row,
        "delta_text": f"{delta:+.2f}",
        "delta_tone": "green" if delta > 0 else ("red" if delta < 0 else "gray"),
        "rank_moved": row["rank_base"] != row["rank_draft"],
        "has_delta": abs(delta) >= 0.005,
    }


class RatingLabState(AdminState):
    """``/admin/rating`` 状态。"""

    admin_error: str = ""
    admin_feedback: str = ""

    # ---- 草稿参数（字符串存，便于输入框双向绑定）----
    draft_center: str = str(DEFAULT.center)
    draft_logistic_scale: str = str(DEFAULT.logistic_scale)
    draft_logistic_odds: str = str(DEFAULT.logistic_odds)
    draft_g_scale: str = str(DEFAULT.g_scale)
    draft_time_decay: str = str(DEFAULT.time_decay)
    draft_first_perf_inflation: str = str(DEFAULT.first_perf_inflation)
    draft_f_full: str = str(DEFAULT.f_full)

    # ---- 已应用参数（展示用）----
    baseline_params: dict[str, float] = {}
    # ---- 试算结果 ----
    preview_rows: list[dict] = []
    summary: dict[str, float] = {}
    previewed: bool = False

    def on_load(self):
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        self.admin_error = ""
        self.admin_feedback = ""
        self._load_baseline()
        return None

    # ---- 内部 ----

    def _load_baseline(self) -> None:
        applied = lab.load_applied_params()
        self.baseline_params = {field: getattr(applied, field) for field in TUNABLE_FIELDS}
        self._fill_draft(applied)

    def _fill_draft(self, params: FormulaParams) -> None:
        self.draft_center = str(params.center)
        self.draft_logistic_scale = str(params.logistic_scale)
        self.draft_logistic_odds = str(params.logistic_odds)
        self.draft_g_scale = str(params.g_scale)
        self.draft_time_decay = str(params.time_decay)
        self.draft_first_perf_inflation = str(params.first_perf_inflation)
        self.draft_f_full = str(params.f_full)

    def _draft_params(self) -> FormulaParams:
        """构造草稿参数；错误以 ``ValueError`` 抛出由调用方转 admin_error。"""
        raw = {
            "center": self.draft_center,
            "logistic_scale": self.draft_logistic_scale,
            "logistic_odds": self.draft_logistic_odds,
            "g_scale": self.draft_g_scale,
            "time_decay": self.draft_time_decay,
            "first_perf_inflation": self.draft_first_perf_inflation,
            "f_full": self.draft_f_full,
        }
        parsed: dict[str, float] = {}
        for key, text in raw.items():
            try:
                parsed[key] = float(text)
            except (TypeError, ValueError):
                raise ValueError(f"{FIELD_META[key][0]} 不是合法数字：{text!r}") from None
        return DEFAULT.with_overrides(**parsed)

    # ---- setter ----

    def set_draft_center(self, value: str) -> None:
        self.draft_center = value

    def set_draft_logistic_scale(self, value: str) -> None:
        self.draft_logistic_scale = value

    def set_draft_logistic_odds(self, value: str) -> None:
        self.draft_logistic_odds = value

    def set_draft_g_scale(self, value: str) -> None:
        self.draft_g_scale = value

    def set_draft_time_decay(self, value: str) -> None:
        self.draft_time_decay = value

    def set_draft_first_perf_inflation(self, value: str) -> None:
        self.draft_first_perf_inflation = value

    def set_draft_f_full(self, value: str) -> None:
        self.draft_f_full = value

    # ---- 事件 ----

    def run_preview(self) -> None:
        """第 2 层守卫 + 试算（不落库、不进缓存）。"""
        denied = self._require_admin()
        if denied is not None:
            return denied
        self.admin_error = ""
        self.admin_feedback = ""
        try:
            params = self._draft_params()
            result = lab.preview(params)
        except ValueError as exc:
            self.admin_error = str(exc)
            return None
        self.preview_rows = [_decorate(row) for row in result["rows"]]
        self.summary = result["summary"]
        self.previewed = True
        return None

    def reset_to_baseline(self) -> None:
        """把草稿恢复为「已应用参数」。"""
        denied = self._require_admin()
        if denied is not None:
            return denied
        self.admin_error = ""
        self.previewed = False
        self.preview_rows = []
        self.summary = {}
        self._load_baseline()
        self.admin_feedback = "草稿已恢复为当前生效参数"
        return None

    def reset_to_default(self) -> None:
        """把草稿恢复为内置默认值（不改变已应用参数）。"""
        denied = self._require_admin()
        if denied is not None:
            return denied
        self.admin_error = ""
        self.previewed = False
        self.preview_rows = []
        self.summary = {}
        self._fill_draft(DEFAULT)
        self.admin_feedback = "草稿已恢复为内置默认值（尚未应用）"
        return None

    def apply_draft(self) -> None:
        """应用草稿：写 YAML + bump data_version + 审计。"""
        denied = self._require_admin()
        if denied is not None:
            return denied
        self.admin_error = ""
        self.admin_feedback = ""
        try:
            params = self._draft_params()
            result = lab.apply_params(params, user_id=self.authenticated_user.id)
        except ValueError as exc:
            self.admin_error = str(exc)
            return None
        self.baseline_params = {field: getattr(params, field) for field in TUNABLE_FIELDS}
        changed = result["changed"]
        self.admin_feedback = (
            f"已应用，变更 {len(changed)} 项：{', '.join(sorted(changed))}"
            if changed
            else "已应用（参数与当前一致，无变化）"
        )
        return None

    # ---- computed var ----

    @rx.var
    def field_rows(self) -> list[dict[str, str]]:
        """参数表：字段名 / 标签 / 说明 / 当前草稿值 / 已应用值。"""
        return [
            {
                "key": field,
                "label": FIELD_META[field][0],
                "hint": FIELD_META[field][1],
                "draft": getattr(self, f"draft_{field}"),
                "baseline": str(self.baseline_params.get(field, "")),
            }
            for field in TUNABLE_FIELDS
        ]

    @rx.var
    def has_preview(self) -> bool:
        return self.previewed and len(self.preview_rows) > 0