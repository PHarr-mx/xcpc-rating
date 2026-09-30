"""Admin 赛事等级管理状态：等级 CRUD + 奖项基线 CRUD（/admin/tiers）。"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth

from xcpc_core.tier import api as tier_api
from xcpc_core.tier.models import AwardLevelCreate, AwardLevelUpdate, TierCreate, TierUpdate

from xcpc_web.states.admin.base import AdminState


class AdminTiersState(AdminState):
    """``/admin/tiers`` 状态。"""

    admin_error: str = ""
    admin_feedback: str = ""

    # 等级表单
    form_tier_name: str = ""
    form_tier_coefficient: str = ""
    form_tier_sort: str = "0"
    # 编辑中的等级 id（空串 = 非编辑态）
    editing_tier_id: str = ""

    # 奖项表单
    form_award_name: str = ""
    form_award_points: str = ""
    form_award_sort: str = "0"
    editing_award_id: str = ""

    def on_load(self):
        """第 1 层守卫：非 admin 重定向。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        self.admin_error = ""
        self.admin_feedback = ""
        return None

    # ---- setter ----

    def set_form_tier_name(self, value: str) -> None:
        self.form_tier_name = value

    def set_form_tier_coefficient(self, value: str) -> None:
        self.form_tier_coefficient = value

    def set_form_tier_sort(self, value: str) -> None:
        self.form_tier_sort = value

    def set_form_award_name(self, value: str) -> None:
        self.form_award_name = value

    def set_form_award_points(self, value: str) -> None:
        self.form_award_points = value

    def set_form_award_sort(self, value: str) -> None:
        self.form_award_sort = value

    # ---- 展示 var ----

    @rx.var(cache=False)
    def tiers(self) -> list[dict]:
        if not self.is_admin:
            return []
        try:
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "coefficient": f"{t.coefficient:g}",
                    "sort_order": t.sort_order,
                }
                for t in tier_api.list_tiers()
            ]
        except Exception:
            return []

    @rx.var(cache=False)
    def award_levels(self) -> list[dict]:
        if not self.is_admin:
            return []
        try:
            return [
                {
                    "id": a.id,
                    "name": a.name,
                    "label": {"gold": "金奖", "silver": "银奖", "bronze": "铜奖"}.get(a.name, a.name),
                    "base_points": f"{a.base_points:g}",
                    "sort_order": a.sort_order,
                }
                for a in tier_api.list_award_levels()
            ]
        except Exception:
            return []

    # ---- 等级事件 ----

    @rx.event
    def save_tier(self):
        if ret := self._require_admin():
            return ret
        self.admin_error = ""
        self.admin_feedback = ""
        name = self.form_tier_name.strip()
        if not name:
            self.admin_error = "请填写等级名称"
            return
        try:
            coefficient = float(self.form_tier_coefficient.strip())
            sort_order = int(self.form_tier_sort.strip() or "0")
        except ValueError:
            self.admin_error = "系数必须为正数，排序必须为整数"
            return
        try:
            if self.editing_tier_id:
                tier_api.update_tier(
                    int(self.editing_tier_id),
                    TierUpdate(name=name, coefficient=coefficient, sort_order=sort_order),
                )
                self.admin_feedback = f"已更新赛事等级「{name}」"
            else:
                tier_api.create_tier(TierCreate(name=name, coefficient=coefficient, sort_order=sort_order))
                self.admin_feedback = f"已创建赛事等级「{name}」"
        except Exception as exc:
            self.admin_error = str(exc)
            return
        self._reset_tier_form()

    @rx.event
    def edit_tier(self, tier_id: int):
        rows = [t for t in self.tiers if t["id"] == tier_id]
        if not rows:
            return
        row = rows[0]
        self.editing_tier_id = str(tier_id)
        self.form_tier_name = row["name"]
        self.form_tier_coefficient = row["coefficient"]
        self.form_tier_sort = str(row["sort_order"])

    @rx.event
    def cancel_edit_tier(self):
        self._reset_tier_form()

    @rx.event
    def delete_tier(self, tier_id: int):
        if ret := self._require_admin():
            return ret
        self.admin_error = ""
        try:
            tier_api.delete_tier(tier_id)
            self.admin_feedback = f"已删除赛事等级 #{tier_id}"
        except Exception as exc:
            self.admin_error = str(exc)

    def _reset_tier_form(self):
        self.editing_tier_id = ""
        self.form_tier_name = ""
        self.form_tier_coefficient = ""
        self.form_tier_sort = "0"

    # ---- 奖项事件 ----

    @rx.event
    def save_award(self):
        if ret := self._require_admin():
            return ret
        self.admin_error = ""
        self.admin_feedback = ""
        name = self.form_award_name.strip()
        if not name:
            self.admin_error = "请填写奖项名称（如 gold）"
            return
        try:
            base_points = float(self.form_award_points.strip())
            sort_order = int(self.form_award_sort.strip() or "0")
        except ValueError:
            self.admin_error = "基线分必须为非负数，排序必须为整数"
            return
        try:
            if self.editing_award_id:
                tier_api.update_award_level(
                    int(self.editing_award_id),
                    AwardLevelUpdate(name=name, base_points=base_points, sort_order=sort_order),
                )
                self.admin_feedback = f"已更新奖项「{name}」"
            else:
                tier_api.create_award_level(
                    AwardLevelCreate(name=name, base_points=base_points, sort_order=sort_order)
                )
                self.admin_feedback = f"已创建奖项「{name}」"
        except Exception as exc:
            self.admin_error = str(exc)
            return
        self._reset_award_form()

    @rx.event
    def edit_award(self, level_id: int):
        rows = [a for a in self.award_levels if a["id"] == level_id]
        if not rows:
            return
        row = rows[0]
        self.editing_award_id = str(level_id)
        self.form_award_name = row["name"]
        self.form_award_points = row["base_points"]
        self.form_award_sort = str(row["sort_order"])

    @rx.event
    def cancel_edit_award(self):
        self._reset_award_form()

    @rx.event
    def delete_award(self, level_id: int):
        if ret := self._require_admin():
            return ret
        self.admin_error = ""
        try:
            tier_api.delete_award_level(level_id)
            self.admin_feedback = f"已删除奖项 #{level_id}"
        except Exception as exc:
            self.admin_error = str(exc)

    def _reset_award_form(self):
        self.editing_award_id = ""
        self.form_award_name = ""
        self.form_award_points = ""
        self.form_award_sort = "0"
