"""Admin 在线正式赛导入（P4d）：上传、预览、匹配决议、确认。"""

from __future__ import annotations

import shutil
import tempfile
from datetime import date
from os import close
from pathlib import Path

import reflex as rx
import reflex_local_auth

from xcpc_core.audit import record as audit_record
from xcpc_core.importer import api as importer_api
from xcpc_core.importer.models import FormalImportParams
from xcpc_core.importer.config import load_school_organizations
from xcpc_core.player import api as player_api

from xcpc_web.states.admin.base import AdminState


class AdminImportState(AdminState):
    """``/admin/import`` 五步导入状态。"""

    upload_path: str = ""
    upload_filename: str = ""
    batch_id: int = 0
    step: int = 1

    form_contest_id: str = ""
    form_date: str = ""
    form_contest_type: str = "icpc_provincial"
    form_default_grade: str = ""
    decisions: dict[str, str] = {}

    admin_feedback: str = ""
    admin_error: str = ""

    def on_load(self):
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        self.admin_feedback = ""
        self.admin_error = ""
        return None

    def set_form_contest_id(self, value: str) -> None:
        self.form_contest_id = value

    def set_form_date(self, value: str) -> None:
        self.form_date = value

    def set_form_contest_type(self, value: str) -> None:
        self.form_contest_type = value

    def set_form_default_grade(self, value: str) -> None:
        self.form_default_grade = value

    def set_decision(self, name: str, value: str) -> None:
        self.decisions = {**self.decisions, name: value}

    def _remove_upload_file(self) -> None:
        """删除本次页面上传的临时文件。

        staged 批次只保存解析后的 payload，不依赖原始上传文件；因此在确认、
        取消或重新上传时都可以安全清理临时文件。清理失败不应阻断业务状态
        的更新，但要避免把异常冒泡到 Reflex 事件。
        """
        if not self.upload_path:
            return
        try:
            Path(self.upload_path).unlink(missing_ok=True)
        except OSError:
            pass

    def _reset_upload_state(self) -> None:
        self._remove_upload_file()
        self.upload_path = ""
        self.upload_filename = ""
        self.batch_id = 0
        self.step = 1
        self.decisions = {}

    @rx.var(cache=False)
    def has_upload(self) -> bool:
        return self.is_admin and bool(self.upload_path)

    @rx.var(cache=False)
    def batch(self) -> dict:
        if not self.is_admin or not self.batch_id:
            return {}
        try:
            detail = importer_api.get_import_batch(self.batch_id)
        except Exception:
            return {}
        payload = detail.payload
        return {
            "batch_id": detail.batch_id,
            "filename": detail.filename,
            "status": detail.status,
            "contest_id": payload.params.contest_id,
            "title": payload.parsed.title,
            "total_teams": payload.parsed.total_teams,
            "school_teams_count": payload.parsed.school_teams_total,
            "standings_count": len(payload.standings),
            "unmatched_count": len(payload.unmatched_players),
            "unmatched_team_count": len(payload.unmatched_teams),
            "award_thresholds": payload.parsed.award_thresholds.model_dump(mode="json") if payload.parsed.award_thresholds else {},
        }

    @rx.var(cache=False)
    def unmatched_players(self) -> list[dict]:
        if not self.is_admin or not self.batch_id:
            return []
        try:
            payload = importer_api.get_import_batch(self.batch_id).payload
        except Exception:
            return []
        result = []
        for item in payload.unmatched_players:
            result.append({
                "name": item.name,
                "team_name": item.team_name,
                "rank": item.rank,
                "candidates": item.candidates,
                "decision": self.decisions.get(item.name, ""),
            })
        return result

    @rx.var(cache=False)
    def player_option_ids(self) -> list[str]:
        """匹配下拉框选项；``new`` 代表确认时新建选手。"""
        if not self.is_admin:
            return []
        try:
            return ["new", *(p.id for p in player_api.list_players(include_left=True))]
        except Exception:
            return ["new"]

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_error = ""
        if not files:
            self.admin_error = "请选择一个 xlsx 文件"
            return
        upload = files[0]
        filename = Path(upload.filename or "upload.xlsx").name
        if not filename.casefold().endswith((".xlsx", ".xlsm")):
            self.admin_error = "只支持 .xlsx 或 .xlsm 文件"
            return
        # 不使用原始文件名拼接固定路径，避免同一管理员的同名上传相互覆盖，
        # 也避免文件名中的路径片段穿透到临时目录之外。
        suffix = Path(filename).suffix.lower()
        fd, target_name = tempfile.mkstemp(
            prefix=f"xcpc-import-{self.authenticated_user.id}-",
            suffix=suffix,
        )
        close(fd)
        target = Path(target_name)
        try:
            if getattr(upload, "path", None):
                shutil.copyfile(upload.path, target)
            else:
                target.write_bytes(await upload.read())
        except Exception:
            target.unlink(missing_ok=True)
            raise

        # 同一页面重新上传时，旧的暂存文件已经没有用途。
        self._remove_upload_file()
        self.upload_path = str(target)
        self.upload_filename = filename
        self.step = 2
        self.admin_feedback = f"已上传：{filename}，请填写比赛元信息"

    @rx.event
    def clear_upload(self):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._reset_upload_state()
        self.admin_feedback = ""
        self.admin_error = ""

    @rx.event(background=True)
    async def stage_parse(self):
        """后台解析 xlsx，避免大文件占用 Reflex 主事件队列。"""
        guard = self._require_admin()
        if guard is not None:
            return guard

        # 只读状态快照；耗时解析和 staged DB 写入均在锁外执行。
        upload_path = self.upload_path
        upload_filename = self.upload_filename
        contest_id = self.form_contest_id.strip()
        form_date = self.form_date.strip()
        contest_type = self.form_contest_type.strip()
        form_default_grade = self.form_default_grade.strip()
        user_id = self.authenticated_user.id
        try:
            if not upload_path:
                raise ValueError("请先上传 xlsx 文件")
            if not contest_id:
                raise ValueError("contest_id 不能为空")
            parsed_date = date.fromisoformat(form_date)
            default_grade = int(form_default_grade) if form_default_grade else None
            summary = importer_api.stage_formal_xlsx(
                upload_path,
                FormalImportParams(
                    contest_id=contest_id,
                    date=parsed_date,
                    contest_type=contest_type,
                    school_organizations=load_school_organizations(),
                    auto_create_players=False,
                    default_grade=default_grade,
                ),
                uploaded_by=user_id,
                filename=upload_filename,
            )
        except Exception as exc:
            async with self:
                self.admin_error = str(exc)
            return

        async with self:
            self.admin_error = ""
            self.batch_id = summary.batch_id
            self.decisions = {}
            self.step = 3 if summary.unmatched_players else 5
            self.admin_feedback = (
                "解析完成，请核对预览并处理未匹配选手"
                if summary.unmatched_players
                else "解析完成，可确认导入"
            )

    @rx.event
    def confirm_import(self):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_error = ""
        try:
            if not self.batch_id:
                raise ValueError("没有可确认的 staged 导入批次")
            result = importer_api.confirm_import_batch(self.batch_id, self.decisions)
            try:
                audit_record(
                    action="import.confirm",
                    target=result.contest_id,
                    user_id=self.authenticated_user.id,
                    diff_json={
                        "batch_id": self.batch_id,
                        "filename": self.upload_filename,
                        "standings_imported": result.standings_imported,
                        "players_created": len(result.players_created),
                    },
                )
            except Exception:
                pass
            self._remove_upload_file()
            self.upload_path = ""
            self.upload_filename = ""
            self.step = 5
            self.admin_feedback = f"导入完成：{result.title}（{result.standings_imported} 支队伍）"
        except Exception as exc:
            self.admin_error = str(exc)

    @rx.event
    def discard_import(self):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_error = ""
        try:
            if self.batch_id:
                importer_api.discard_import_batch(self.batch_id)
            self._reset_upload_state()
            self.admin_feedback = "已取消导入，正式数据未发生变化"
        except Exception as exc:
            self.admin_error = str(exc)
