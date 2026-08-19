"""ProfileState: /profile 自助资料页 —— 绑定申请 + 自助字段编辑。

权限纪律（服务端强制执行）：
- 自助写操作一律取 ``self.bound_player_id``（computed var 从会话推导），
  不接受客户端传入 player_id。
- 已绑定后才允许编辑 handle / aliases / oj_accounts。
- admin-only 字段（name / grade / status）只读展示，不提供写入口。
"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth
from sqlmodel import select

from xcpc_core.player import api as player_api
from xcpc_core.player.exceptions import PlayerNotFoundError, PlayerValidationError
from xcpc_core.player.models import OJAccount, PlayerUpdate, STATUS_LABELS

from .auth import AuthState
from .auth_models import BindingRequest

# 与 xcpc_core.player.models.OJPlatform 对齐
OJ_PLATFORMS: list[str] = ["codeforces", "atcoder", "luogu", "nowcoder"]


class ProfileState(AuthState):
    """自助资料状态：绑定申请 + 自助字段编辑。"""

    # ---- 绑定申请表单 ----
    binding_player_id: str = ""
    binding_reason: str = ""
    binding_feedback: str = ""   # 成功提示
    binding_error: str = ""      # 失败提示

    # ---- 自助编辑表单 ----
    handle: str = ""
    aliases_text: str = ""       # 中英文逗号/换行分隔
    oj_platform: str = "codeforces"
    oj_handle: str = ""
    edit_feedback: str = ""
    edit_error: str = ""

    # ---- 表单字段 setter（reflex 0.9.x 默认关闭自动 setter，需显式定义）----

    def set_binding_player_id(self, value: str) -> None:
        self.binding_player_id = value

    def set_binding_reason(self, value: str) -> None:
        self.binding_reason = value

    def set_handle(self, value: str) -> None:
        self.handle = value

    def set_aliases_text(self, value: str) -> None:
        self.aliases_text = value

    def set_oj_platform(self, value: str) -> None:
        self.oj_platform = value

    def set_oj_handle(self, value: str) -> None:
        self.oj_handle = value

    # ---- 展示用 computed var ----

    @rx.var(cache=True)
    def player(self) -> dict | None:
        """当前绑定选手的 core 侧数据（含自助字段与 admin-only 字段）。"""
        pid = self.bound_player_id
        if not pid:
            return None
        try:
            p = player_api.get_player(pid)
        except PlayerNotFoundError:
            return None
        return {
            "player_id": p.id,
            "name": p.name,
            "grade_label": p.grade_label or ("未设置" if p.grade == 0 else f"{p.grade}级"),
            "status_label": p.status_label
            or (STATUS_LABELS.get(p.status.value) if p.status else "未知"),
            "handle": p.handle,
            "aliases": p.aliases,
            "oj_accounts": [a.model_dump() for a in p.oj_accounts],
        }

    @rx.var(cache=True)
    def oj_accounts(self) -> list[dict]:
        """当前绑定选手的 OJ 账号列表（强类型，供 foreach）。"""
        data = self.player or {}
        return data.get("oj_accounts", [])

    @rx.var(cache=True)
    def bindable_players(self) -> list[dict]:
        """可选绑定的选手：排除离队、已绑定、以及本人已申请过的。"""
        if self.bound_player_id:
            return []
        claimed: set[str] = set()
        if self.is_authenticated:
            with rx.session() as session:
                requests = session.exec(
                    select(BindingRequest).where(
                        BindingRequest.user_id == self.authenticated_user.id
                    )
                ).all()
                claimed = {req.player_id for req in requests}
        players = player_api.list_players(include_left=False)
        return [
            {
                "player_id": p.id,
                "name": p.name,
                "grade_label": p.grade_label or ("未设置" if p.grade == 0 else f"{p.grade}级"),
            }
            for p in players
            if p.id not in claimed
        ]

    # ---- 事件 ----

    def on_load(self):
        """页面加载：未登录重定向登录页；已登录初始化表单。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        self.binding_feedback = ""
        self.binding_error = ""
        self.edit_feedback = ""
        self.edit_error = ""
        if self.is_bound:
            data = self.player or {}
            self.handle = data.get("handle") or ""
            self.aliases_text = "，".join(data.get("aliases") or [])
            self.oj_handle = ""
        return

    @rx.event
    def submit_binding(self):
        """提交绑定申请。player 存在性与重复申请均在服务端校验。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        self.binding_feedback = ""
        self.binding_error = ""
        player_id = self.binding_player_id.strip()
        reason = self.binding_reason.strip()
        if not player_id:
            self.binding_error = "请选择要绑定的选手"
            return
        # 校验选手存在
        try:
            player_api.get_player(player_id)
        except PlayerNotFoundError:
            self.binding_error = "所选选手不存在"
            return
        with rx.session() as session:
            # 同一用户同一选手只允许一条申请
            existing = session.exec(
                select(BindingRequest).where(
                    BindingRequest.user_id == self.authenticated_user.id,
                    BindingRequest.player_id == player_id,
                )
            ).one_or_none()
            if existing is not None:
                self.binding_error = "已对该选手提交过申请，请等待 admin 审批"
                return
            # 已有待审批的申请（其他选手）时不重复申请
            pending = session.exec(
                select(BindingRequest).where(
                    BindingRequest.user_id == self.authenticated_user.id,
                    BindingRequest.status == "pending",
                )
            ).one_or_none()
            if pending is not None:
                self.binding_error = "已有待审批的绑定申请，请等待 admin 处理"
                return
            session.add(
                BindingRequest(
                    user_id=self.authenticated_user.id,
                    player_id=player_id,
                    reason=reason or None,
                    status="pending",
                )
            )
            session.commit()
        self.binding_player_id = ""
        self.binding_reason = ""
        self.binding_feedback = f"已提交对 {player_id} 的绑定申请，等待 admin 审批"

    @rx.event
    def save_profile(self):
        """保存自助字段 handle + aliases（player_id 一律取 bound_player_id）。"""
        if not self.is_authenticated or not self.bound_player_id:
            self.edit_error = "未绑定选手，无法编辑资料"
            return
        self.edit_feedback = ""
        self.edit_error = ""
        handle = self.handle.strip() or None
        aliases = self._parse_aliases(self.aliases_text)
        if handle is None and not aliases:
            self.edit_error = "没有需要保存的字段"
            return
        try:
            player_api.update_player(
                self.bound_player_id,
                PlayerUpdate(handle=handle, aliases=aliases),
            )
        except PlayerValidationError as exc:
            self.edit_error = str(exc)
            return
        self.edit_feedback = "资料已保存"

    @rx.event
    def add_oj_account(self):
        """新增 OJ 账号：platform/handle 来自表单，player_id 取 bound_player_id。"""
        if not self.is_authenticated or not self.bound_player_id:
            self.edit_error = "未绑定选手，无法编辑资料"
            return
        self.edit_feedback = ""
        self.edit_error = ""
        platform = self.oj_platform
        handle = self.oj_handle.strip()
        if not handle:
            self.edit_error = "请填写 OJ 账号"
            return
        current = self.player or {}
        accounts = [OJAccount(**a) for a in current.get("oj_accounts", [])]
        if any(a.platform == platform and a.handle == handle for a in accounts):
            self.edit_error = "该 OJ 账号已存在"
            return
        accounts.append(OJAccount(platform=platform, handle=handle))
        try:
            player_api.update_player(
                self.bound_player_id,
                PlayerUpdate(oj_accounts=accounts),
            )
        except PlayerValidationError as exc:
            self.edit_error = str(exc)
            return
        self.oj_handle = ""
        self.edit_feedback = "OJ 账号已添加"

    @rx.event
    def remove_oj_account(self, platform: str, handle: str):
        """删除 OJ 账号（player_id 取 bound_player_id）。"""
        if not self.is_authenticated or not self.bound_player_id:
            self.edit_error = "未绑定选手，无法编辑资料"
            return
        self.edit_feedback = ""
        self.edit_error = ""
        current = self.player or {}
        accounts = [
            a for a in (OJAccount(**acc) for acc in current.get("oj_accounts", []))
            if not (a.platform == platform and a.handle == handle)
        ]
        try:
            player_api.update_player(
                self.bound_player_id,
                PlayerUpdate(oj_accounts=accounts),
            )
        except PlayerValidationError as exc:
            self.edit_error = str(exc)
            return
        self.edit_feedback = "OJ 账号已删除"

    @staticmethod
    def _parse_aliases(raw: str) -> list[str]:
        """把逗号/中文逗号/换行分隔的文本解析为去重后的别名列表。"""
        seen: list[str] = []
        for item in raw.replace("，", ",").replace("\n", ",").split(","):
            item = item.strip()
            if item and item not in seen:
                seen.append(item)
        return seen
