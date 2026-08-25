"""Admin 队伍管理状态：列表、搜索、创建、别名编辑与删除。"""

from __future__ import annotations

import re

from pydantic import ValidationError

import reflex as rx
import reflex_local_auth

from xcpc_core.audit import record as audit_record
from xcpc_core.player import api as player_api
from xcpc_core.team import api as team_api
from xcpc_core.team.exceptions import (
    TeamAlreadyExistsError,
    TeamError,
    TeamNotFoundError,
)
from xcpc_core.team.models import TeamCreate, TeamUpdate

from xcpc_web.states.admin.base import AdminState


class AdminTeamsState(AdminState):
    """``/admin/teams`` 状态。

    队伍的身份由成员集合决定。按照 core 约束，编辑已有队伍时只追加别名；
    换员应通过新建队伍完成，不能原地修改旧队伍的 ``members``。
    """

    search: str = ""

    form_open: bool = False
    editing_team_id: str = ""
    form_id: str = ""
    form_members_text: str = ""
    form_aliases_text: str = ""

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

    def set_form_id(self, value: str) -> None:
        self.form_id = value

    def set_form_members_text(self, value: str) -> None:
        self.form_members_text = value

    def set_form_aliases_text(self, value: str) -> None:
        self.form_aliases_text = value

    # ---- computed var（第 3 层守卫） ----

    @rx.var(cache=False)
    def teams(self) -> list[dict]:
        """按队伍 ID、成员、member_key 或别名搜索队伍。"""
        if not self.is_admin:
            return []
        try:
            teams = team_api.list_teams()
            players = player_api.list_players(include_left=True)
        except Exception:
            return []

        player_names = {player.id: player.name for player in players}
        search = self.search.strip().casefold()
        result: list[dict] = []
        for team in teams:
            view = self._team_view(team, player_names)
            haystack = " ".join(
                [
                    team.id,
                    team.member_key,
                    *team.members,
                    *team.aliases,
                    view["member_names"],
                ]
            ).casefold()
            if search and search not in haystack:
                continue
            result.append(view)
        return result

    @rx.var(cache=False)
    def team_count(self) -> int:
        if not self.is_admin:
            return 0
        return len(self.teams)

    @rx.var(cache=False)
    def form_title(self) -> str:
        return "编辑队伍别名" if self.editing_team_id else "新建队伍"

    @rx.var(cache=False)
    def form_description(self) -> str:
        if self.editing_team_id:
            return "成员集合只读；如需换员，请新建一支队伍。保存时只会追加新别名，不会删除已有别名。"
        return "队伍身份由成员集合决定。同一成员集合只能创建一支队伍，队名请填写到别名。"

    @rx.var(cache=False)
    def id_error(self) -> str:
        return self.field_errors.get("id", "")

    @rx.var(cache=False)
    def members_error(self) -> str:
        return self.field_errors.get("members", "")

    @rx.var(cache=False)
    def aliases_error(self) -> str:
        return self.field_errors.get("aliases", "")

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
    def open_edit(self, team_id: str):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._clear_messages()
        try:
            team = team_api.get_team(team_id)
        except TeamNotFoundError as exc:
            self.admin_error = str(exc)
            return
        self.editing_team_id = team.id
        self.form_id = team.id
        self.form_members_text = ",".join(team.members)
        self.form_aliases_text = "\n".join(team.aliases)
        self.form_open = True

    @rx.event
    def close_form(self):
        self.form_open = False
        self._clear_form()

    @rx.event
    def save_team(self):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._clear_messages()

        if self.editing_team_id:
            self._save_aliases()
            return

        members = self._parse_members(self.form_members_text)
        aliases = self._parse_aliases(self.form_aliases_text)
        try:
            data = TeamCreate(
                id=self.form_id.strip() or None,
                members=members,
                aliases=aliases,
            )
        except ValidationError as exc:
            self._set_validation_errors(exc)
            return

        unknown_members = self._unknown_members(data.members)
        if unknown_members:
            self.field_errors = {
                "members": f"以下 player_id 不存在：{', '.join(unknown_members)}"
            }
            self.admin_error = "请修正表单中的错误"
            return

        existing = team_api.find_by_members(data.members)
        if existing is not None:
            alias_text = "、".join(existing.aliases) or "无别名"
            self.field_errors = {
                "members": f"队员组合已存在：{existing.id}（{alias_text}）"
            }
            self.admin_error = f"队员组合已存在：{existing.member_key}"
            return

        try:
            team = team_api.create_team(data)
        except TeamAlreadyExistsError as exc:
            self.field_errors = {"members": str(exc)}
            self.admin_error = str(exc)
            return
        except TeamError as exc:
            message = str(exc)
            self.field_errors = {"general": message}
            self.admin_error = message
            return

        self._write_audit(
            action="team.create",
            target=team.id,
            diff={
                "members": team.members,
                "member_key": team.member_key,
                "aliases": team.aliases,
            },
        )
        self.admin_feedback = f"已创建队伍：{team.id}（{self._aliases_label(team.aliases)}）"
        self.form_open = False
        self._clear_form(keep_messages=True)

    @rx.event
    def delete_team(self, team_id: str):
        """物理删除队伍；历史比赛数据不在此处级联修改。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._clear_messages()
        try:
            team = team_api.delete_team(team_id)
        except TeamError as exc:
            self.admin_error = str(exc)
            return
        self._write_audit(
            action="team.delete",
            target=team.id,
            diff={"members": team.members, "aliases": team.aliases},
        )
        self.admin_feedback = f"已删除队伍：{team.id}"

    # ---- 内部工具 ----

    def _save_aliases(self) -> None:
        team_id = self.editing_team_id
        try:
            current = team_api.get_team(team_id)
        except TeamNotFoundError as exc:
            self.admin_error = str(exc)
            return

        aliases = self._parse_aliases(self.form_aliases_text)
        additions = [alias for alias in aliases if alias not in current.aliases]
        if not additions:
            self.admin_feedback = f"队伍未修改：{team_id}"
            self.form_open = False
            self._clear_form(keep_messages=True)
            return

        updated = current
        try:
            for alias in additions:
                updated = team_api.update_team(team_id, TeamUpdate(alias=alias))
        except TeamError as exc:
            self.admin_error = str(exc)
            return

        self._write_audit(
            action="team.update",
            target=updated.id,
            diff={"added_aliases": additions},
        )
        self.admin_feedback = f"已更新队伍别名：{updated.id}"
        self.form_open = False
        self._clear_form(keep_messages=True)

    @staticmethod
    def _parse_members(value: str) -> list[str]:
        """支持每行一个、逗号、分号或空格分隔的 player_id。"""
        return [item for item in re.split(r"[,，;；\s]+", value.strip()) if item]

    @staticmethod
    def _parse_aliases(value: str) -> list[str]:
        result: list[str] = []
        for item in value.replace("，", ",").replace("；", ",").replace("\n", ",").split(","):
            item = item.strip()
            if item and item not in result:
                result.append(item)
        return result

    @staticmethod
    def _unknown_members(members: list[str]) -> list[str]:
        unknown: list[str] = []
        for player_id in members:
            try:
                player_api.get_player(player_id)
            except Exception:
                unknown.append(player_id)
        return unknown

    @staticmethod
    def _aliases_label(aliases: list[str]) -> str:
        return "、".join(aliases) if aliases else "无别名"

    @staticmethod
    def _team_view(team, player_names: dict[str, str]) -> dict:
        member_names = "、".join(
            f"{player_names.get(player_id, '未知选手')}（{player_id}）"
            for player_id in team.members
        )
        return {
            "id": team.id,
            "members": team.members,
            "member_key": team.member_key,
            "size": team.size,
            "member_names": member_names or "—",
            "aliases": "、".join(team.aliases) or "—",
            "created_at": team.created_at.isoformat() if team.created_at else "",
            "updated_at": team.updated_at.isoformat() if team.updated_at else "",
        }

    def _set_validation_errors(self, exc: ValidationError) -> None:
        errors: dict[str, str] = {}
        for item in exc.errors():
            loc = item.get("loc", ("general",))
            field = str(loc[0]) if loc else "general"
            errors.setdefault(field, str(item.get("msg", "字段校验失败")))
        self.field_errors = errors or {"general": "表单校验失败"}
        self.admin_error = "请修正表单中的错误"

    def _clear_messages(self) -> None:
        self.admin_feedback = ""
        self.admin_error = ""
        self.field_errors = {}

    def _clear_form(self, *, keep_messages: bool = False) -> None:
        self.form_open = False
        self.editing_team_id = ""
        self.form_id = ""
        self.form_members_text = ""
        self.form_aliases_text = ""
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
