"""Admin 选手管理状态：列表、筛选、创建、编辑与软删除。"""

from __future__ import annotations

from pydantic import ValidationError

import reflex as rx
import reflex_local_auth

from xcpc_core.audit import record as audit_record
from xcpc_core.player import api as player_api
from xcpc_core.player.exceptions import (
    PlayerAlreadyExistsError,
    PlayerError,
    PlayerNotFoundError,
    PlayerValidationError,
)
from xcpc_core.player.models import (
    OJAccount,
    PlayerCreate,
    PlayerStatus,
    PlayerUpdate,
    STATUS_LABELS,
)

from xcpc_web.states.admin.base import AdminState

OJ_PLATFORMS: tuple[str, ...] = ("codeforces", "atcoder", "luogu", "nowcoder")
OJ_PLATFORM_LABELS: dict[str, str] = {
    "codeforces": "Codeforces",
    "atcoder": "AtCoder",
    "luogu": "洛谷",
    "nowcoder": "牛客",
}


class AdminPlayersState(AdminState):
    """``/admin/players`` 状态。"""

    # 列表筛选
    search: str = ""
    status_filter: str = "all"
    grade_filter: str = ""

    # 表单
    form_open: bool = False
    editing_player_id: str = ""
    form_id: str = ""
    form_name: str = ""
    form_handle: str = ""
    form_grade: str = ""
    form_status: str = PlayerStatus.active.value
    form_aliases: str = ""
    form_oj_accounts: str = ""

    admin_feedback: str = ""
    admin_error: str = ""
    field_errors: dict[str, str] = {}

    def on_load(self):
        """第 1 层守卫：非 admin 重定向。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        self.admin_feedback = ""
        self.admin_error = ""
        return None

    # ---- 表单 setter（reflex 0.9.x 默认关闭自动 setter） ----

    def set_search(self, value: str) -> None:
        self.search = value

    def set_status_filter(self, value: str) -> None:
        self.status_filter = value

    def set_grade_filter(self, value: str) -> None:
        self.grade_filter = value

    def set_form_id(self, value: str) -> None:
        self.form_id = value

    def set_form_name(self, value: str) -> None:
        self.form_name = value

    def set_form_handle(self, value: str) -> None:
        self.form_handle = value

    def set_form_grade(self, value: str) -> None:
        self.form_grade = value

    def set_form_status(self, value: str) -> None:
        self.form_status = value

    def set_form_aliases(self, value: str) -> None:
        self.form_aliases = value

    def set_form_oj_accounts(self, value: str) -> None:
        self.form_oj_accounts = value

    # ---- computed var（第 3 层守卫） ----

    @rx.var(cache=False)
    def players(self) -> list[dict]:
        """按搜索条件返回选手列表。"""
        if not self.is_admin:
            return []
        try:
            players = player_api.list_players(include_left=True)
        except Exception:
            return []

        search = self.search.strip().casefold()
        status = self.status_filter
        grade = self.grade_filter.strip()
        result: list[dict] = []
        for player in players:
            if status != "all" and player.status.value != status:
                continue
            if grade:
                if not grade.isdigit() or player.grade != int(grade):
                    continue
            haystack = " ".join(
                [
                    player.id,
                    player.name,
                    player.handle or "",
                    *player.aliases,
                    *(f"{account.platform} {account.handle}" for account in player.oj_accounts),
                ]
            ).casefold()
            if search and search not in haystack:
                continue
            result.append(self._player_view(player))
        return result

    @rx.var(cache=False)
    def active_count(self) -> int:
        if not self.is_admin:
            return 0
        return sum(p["status"] == PlayerStatus.active.value for p in self.players)

    @rx.var(cache=False)
    def probation_count(self) -> int:
        if not self.is_admin:
            return 0
        return sum(p["status"] == PlayerStatus.probation.value for p in self.players)

    @rx.var(cache=False)
    def retired_count(self) -> int:
        if not self.is_admin:
            return 0
        return sum(p["status"] == PlayerStatus.retired.value for p in self.players)

    @rx.var(cache=False)
    def left_count(self) -> int:
        if not self.is_admin:
            return 0
        return sum(p["status"] == PlayerStatus.left.value for p in self.players)

    @rx.var(cache=False)
    def form_title(self) -> str:
        return "编辑选手" if self.editing_player_id else "新建选手"

    @rx.var(cache=False)
    def name_error(self) -> str:
        return self.field_errors.get("name", "")

    @rx.var(cache=False)
    def grade_error(self) -> str:
        return self.field_errors.get("grade", "")

    @rx.var(cache=False)
    def handle_error(self) -> str:
        return self.field_errors.get("handle", "")

    @rx.var(cache=False)
    def status_error(self) -> str:
        return self.field_errors.get("status", "")

    @rx.var(cache=False)
    def aliases_error(self) -> str:
        return self.field_errors.get("aliases", "")

    @rx.var(cache=False)
    def oj_accounts_error(self) -> str:
        return self.field_errors.get("oj_accounts", "")

    @rx.var(cache=False)
    def general_error(self) -> str:
        return self.field_errors.get("general", "")

    # ---- 页面事件 ----

    @rx.event
    def open_create(self):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._clear_form()
        self.form_open = True

    @rx.event
    def open_edit(self, player_id: str):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._clear_messages()
        try:
            player = player_api.get_player(player_id)
        except PlayerNotFoundError as exc:
            self.admin_error = str(exc)
            return
        self.editing_player_id = player.id
        self.form_id = player.id
        self.form_name = player.name
        self.form_handle = player.handle or ""
        self.form_grade = str(player.grade)
        self.form_status = player.status.value
        self.form_aliases = "\n".join(player.aliases)
        self.form_oj_accounts = "\n".join(
            f"{account.platform}:{account.handle}" for account in player.oj_accounts
        )
        self.form_open = True

    @rx.event
    def close_form(self):
        self.form_open = False
        self._clear_messages()

    @rx.event
    def save_player(self):
        """保存表单；所有写入均通过 ``player.api``。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._clear_messages()

        aliases = self._parse_aliases(self.form_aliases)
        oj_accounts = self._parse_oj_accounts(self.form_oj_accounts)
        if oj_accounts is None:
            return
        if not self.form_name.strip():
            self.field_errors = {"name": "姓名不能为空"}
            self.admin_error = "请修正表单中的错误"
            return
        try:
            grade = self._parse_grade(self.form_grade)
        except ValueError:
            self.field_errors = {"grade": "入学年必须是数字"}
            self.admin_error = "请修正表单中的错误"
            return
        try:
            status = PlayerStatus(self.form_status)
        except ValueError:
            self.field_errors = {"status": "状态值无效"}
            self.admin_error = "请修正表单中的错误"
            return
        try:
            if self.editing_player_id:
                data = PlayerUpdate(
                    name=self.form_name.strip(),
                    handle=self.form_handle.strip() or None,
                    grade=grade,
                    status=status,
                    aliases=aliases,
                    oj_accounts=oj_accounts,
                )
                player = player_api.update_player(self.editing_player_id, data)
                action = "player.update"
                message = f"已更新选手：{player.name}（{player.id}）"
                diff = {"name": player.name, "grade": player.grade, "status": player.status.value}
            else:
                data = PlayerCreate(
                    id=self.form_id.strip() or None,
                    name=self.form_name.strip(),
                    handle=self.form_handle.strip() or None,
                    grade=grade,
                    status=status,
                    aliases=aliases,
                    oj_accounts=oj_accounts,
                )
                player = player_api.create_player(data)
                action = "player.create"
                message = f"已创建选手：{player.name}（{player.id}）"
                diff = {"name": player.name, "grade": player.grade, "status": player.status.value}
        except ValidationError as exc:
            self._set_validation_errors(exc)
            return
        except PlayerError as exc:
            message = str(exc)
            self.admin_error = message
            if isinstance(exc, PlayerValidationError):
                # core 当前将 handle/OJ 的 DB 唯一约束合并成一个领域错误；
                # Web 端同时标在两个可能相关的字段，避免错误只出现在顶部。
                self.field_errors = {
                    "general": message,
                    "handle": message,
                    "oj_accounts": message,
                }
            else:
                self.field_errors = {"general": message}
            return
        except ValueError as exc:
            self.field_errors = {"grade": str(exc)}
            return

        self._write_audit(action=action, target=player.id, diff=diff)
        self.admin_feedback = message
        self.form_open = False
        self._clear_form(keep_messages=True)

    @rx.event
    def mark_player_left(self, player_id: str):
        """软删除选手：将状态改为 ``left``，保留历史数据。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._clear_messages()
        try:
            player = player_api.mark_left(player_id)
        except PlayerError as exc:
            self.admin_error = str(exc)
            return
        self._write_audit(
            action="player.delete",
            target=player.id,
            diff={"status": PlayerStatus.left.value},
        )
        self.admin_feedback = f"已将选手标记为离队：{player.name}（{player.id}）"

    @rx.event
    def mark_player_retired(self, player_id: str):
        """标记退役：状态改为 ``retired``，档案与榜单保留。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._clear_messages()
        try:
            player = player_api.mark_retired(player_id)
        except PlayerError as exc:
            self.admin_error = str(exc)
            return
        self._write_audit(
            action="player.update",
            target=player.id,
            diff={"status": PlayerStatus.retired.value},
        )
        self.admin_feedback = f"已将选手标记为退役：{player.name}（{player.id}）"

    @rx.event
    def mark_player_active(self, player_id: str):
        """入队：预备队员通过入队考核后转为现役。

        仅 ``probation`` 状态可入队（core 侧守卫）；其余状态按钮本就不显示。
        """
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._clear_messages()
        try:
            player = player_api.mark_active(player_id)
        except PlayerError as exc:
            self.admin_error = str(exc)
            return
        self._write_audit(
            action="player.update",
            target=player.id,
            diff={"status": PlayerStatus.active.value},
        )
        self.admin_feedback = f"选手已入队（转为现役）：{player.name}（{player.id}）"

    # ---- 内部工具 ----

    @staticmethod
    def _parse_aliases(value: str) -> list[str]:
        result: list[str] = []
        for item in value.replace("，", ",").replace("\n", ",").split(","):
            item = item.strip()
            if item and item not in result:
                result.append(item)
        return result

    def _parse_oj_accounts(self, value: str) -> list[OJAccount] | None:
        accounts: list[OJAccount] = []
        for line in value.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                self.field_errors = {"oj_accounts": "每行格式应为 platform:handle，例如 codeforces:tourist"}
                return None
            platform, handle = (part.strip() for part in line.split(":", 1))
            if platform not in OJ_PLATFORMS or not handle:
                self.field_errors = {
                    "oj_accounts": "OJ 平台必须是 codeforces、atcoder、luogu 或 nowcoder，且 handle 不能为空"
                }
                return None
            if any(a.platform == platform and a.handle == handle for a in accounts):
                self.field_errors = {"oj_accounts": f"OJ 账号重复：{platform}:{handle}"}
                return None
            accounts.append(OJAccount(platform=platform, handle=handle))
        return accounts

    @staticmethod
    def _parse_grade(value: str) -> int:
        value = value.strip()
        if not value:
            return 0
        return int(value)

    def _set_validation_errors(self, exc: ValidationError) -> None:
        errors: dict[str, str] = {}
        for item in exc.errors():
            loc = item.get("loc", ("general",))
            field = str(loc[0]) if loc else "general"
            message = str(item.get("msg", "字段校验失败"))
            errors.setdefault(field, message)
        self.field_errors = errors or {"general": "表单校验失败"}
        self.admin_error = "请修正表单中的错误"

    def _clear_messages(self) -> None:
        self.admin_feedback = ""
        self.admin_error = ""
        self.field_errors = {}

    def _clear_form(self, *, keep_messages: bool = False) -> None:
        self.editing_player_id = ""
        self.form_id = ""
        self.form_name = ""
        self.form_handle = ""
        self.form_grade = ""
        self.form_status = PlayerStatus.active.value
        self.form_aliases = ""
        self.form_oj_accounts = ""
        if not keep_messages:
            self._clear_messages()

    def _write_audit(self, *, action: str, target: str, diff: dict) -> None:
        try:
            audit_record(
                action=action,
                target=target,
                user_id=self.authenticated_user.id,
                diff_json=diff,
            )
        except Exception:
            # 审计为 best-effort，不让 core 写入因日志故障回滚。
            pass

    @staticmethod
    def _player_view(player) -> dict:
        status = player.status.value
        return {
            "id": player.id,
            "name": player.name,
            "handle": player.handle or "",
            "grade": player.grade,
            "grade_label": "未设置" if player.grade == 0 else f"{player.grade}级",
            "status": status,
            "status_label": STATUS_LABELS.get(status, status),
            "aliases": "、".join(player.aliases) or "—",
            "oj_accounts": "、".join(
                f"{OJ_PLATFORM_LABELS.get(a.platform, a.platform)}: {a.handle}"
                for a in player.oj_accounts
            ) or "—",
        }
