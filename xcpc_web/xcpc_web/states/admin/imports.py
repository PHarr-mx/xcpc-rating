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

    # ---- 通用 JSON 通道（P-U3）----
    json_path: str = ""
    json_filename: str = ""
    json_preview: dict = {}
    #: 歧义姓名 → 决议。``{"张三": "p001"}`` 指定选手，``{"张三": "new:2025"}`` 强制新建。
    json_decisions: dict[str, str] = {}

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

    # ---- 通用 JSON 通道 ----

    @rx.event
    async def handle_json_upload(self, files: list[rx.UploadFile]):
        """上传通用比赛 JSON：只做只读预览，不写库。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_error = ""
        self.admin_feedback = ""
        self.json_preview = {}
        if not files:
            self.admin_error = "请选择一个 JSON 文件"
            return
        upload = files[0]
        filename = Path(upload.filename or "contest.json").name
        if not filename.casefold().endswith(".json"):
            self.admin_error = "通用比赛导入只接受 .json 文件"
            return

        fd, target_name = tempfile.mkstemp(
            prefix=f"xcpc-json-{self.authenticated_user.id}-", suffix=".json"
        )
        close(fd)
        target = Path(target_name)
        try:
            if getattr(upload, "path", None):
                shutil.copyfile(upload.path, target)
            else:
                target.write_bytes(await upload.read())
            preview = importer_api.preview_contest_json(target)
        except Exception as exc:
            target.unlink(missing_ok=True)
            self.admin_error = f"解析失败：{exc}"
            return

        self._remove_json_file()
        self.json_path = str(target)
        self.json_filename = filename
        self.json_preview = preview
        self.json_decisions = {}
        self.admin_feedback = f"已解析：{filename}，请核对匹配结果后确认写入"

    def _remove_json_file(self) -> None:
        if not self.json_path:
            return
        try:
            Path(self.json_path).unlink(missing_ok=True)
        except OSError:
            pass

    def _reset_json_state(self) -> None:
        self._remove_json_file()
        self.json_path = ""
        self.json_filename = ""
        self.json_preview = {}
        self.json_decisions = {}

    @rx.var(cache=False)
    def json_rows(self) -> list[dict]:
        """预览行 → 展示视图（匹配数/新建数/是否受阻）。"""
        if not self.is_admin or not self.json_preview:
            return []
        return [
            {
                "index": row["index"],
                "name": row["name"],
                "members": "、".join(row["members"]),
                "rank": row["rank"] if row["rank"] is not None else "-",
                "matched": len(row["matched"]),
                "to_create": len(row["to_create"]),
                "blocked": row["blocked"],
                "status": "姓名歧义" if row["blocked"] else (
                    "全部已存在" if not row["to_create"] else "将新建选手"
                ),
            }
            for row in self.json_preview.get("rows", [])
        ]

    @rx.var(cache=False)
    def json_has_preview(self) -> bool:
        return self.is_admin and bool(self.json_preview)

    @rx.var(cache=False)
    def json_header(self) -> dict:
        """预览头部展示字段（Var 里不能拼接字符串，故在 State 预算）。"""
        preview = self.json_preview
        if not self.is_admin or not preview:
            return {}
        players = preview.get("players_to_create") or []
        blocked = preview.get("blocked_count") or 0
        return {
            "title": preview.get("title", ""),
            "contest_id": preview.get("contest_id", ""),
            "tier_name": preview.get("tier_name", ""),
            "format_entity": f"{preview.get('format', '')} × {preview.get('entity', '')}",
            "to_create_label": f"将新建选手 {len(players)} 名",
            "rows_label": f"{len(preview.get('rows') or [])} 条成绩",
            "existing": bool(preview.get("existing_contest")),
            "blocked": blocked > 0,
        }

    @rx.event
    def set_json_decision(self, name: str, value: str) -> None:
        """记录一名歧义选手的决议（下拉选择）。空值 = 清除决议。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        decisions = dict(self.json_decisions)
        if value:
            decisions[name] = value
        else:
            decisions.pop(name, None)
        self.json_decisions = decisions

    @rx.var(cache=False)
    def json_decision_options(self) -> list[str]:
        """歧义下拉的选项：全量选手 + ``new``（强制新建）。

        与 xlsx 通道的 ``player_option_ids`` 同口径——Reflex 的 rx.select 只接受
        State 级扁平列表，不能按行传 Var 列表。
        """
        if not self.is_admin:
            return []
        try:
            return ["new", *(p.id for p in player_api.list_players(include_left=True))]
        except Exception:
            return ["new"]

    @rx.var(cache=False)
    def json_ambiguous(self) -> list[dict]:
        """歧义明细 + 该姓名的当前决议（供页面渲染下拉）。"""
        if not self.is_admin or not self.json_preview:
            return []
        rows: list[dict] = []
        for item in self.json_preview.get("ambiguous") or []:
            for name in item["members"]:
                candidates = (item.get("candidates") or {}).get(name) or []
                rows.append({
                    "row": item["row"],
                    "team": item["name"],
                    "name": name,
                    "current": self.json_decisions.get(name, ""),
                    "options": [c["player_id"] for c in candidates],
                    "option_labels": [
                        f'{c["player_id"]} {c["name"]}' for c in candidates
                    ],
                })
        return rows

    @rx.var(cache=False)
    def json_unresolved_count(self) -> int:
        """尚未决议的歧义姓名数（确认前必须为 0 才允许写入那些行）。"""
        if not self.is_admin or not self.json_preview:
            return 0
        total = 0
        for item in self.json_preview.get("ambiguous") or []:
            for name in item["members"]:
                if not self.json_decisions.get(name):
                    total += 1
        return total

    def _decisions_payload(self) -> dict:
        """把 ``{"张三": "p001" | "new:2025"}`` 转成 core 的 decisions 结构。"""
        payload: dict = {}
        for name, value in self.json_decisions.items():
            if not value:
                continue
            if value.startswith("new"):
                _, _, grade = value.partition(":")
                payload[name] = {"action": "new", "grade": int(grade) if grade else None}
            else:
                payload[name] = {"player_id": value}
        return payload

    @rx.event
    def confirm_json_import(self):
        """确认写入：真正的落库与归档。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_error = ""
        self.admin_feedback = ""
        if not self.json_path:
            self.admin_error = "请先上传 JSON 文件"
            return
        try:
            result = importer_api.import_contest_json(
                self.json_path, decisions=self._decisions_payload()
            )
        except Exception as exc:
            self.admin_error = f"导入失败：{exc}"
            return
        audit_record(
            action="import.json_confirm",
            target=result.contest_id,
            user_id=self.authenticated_user.id,
            diff_json={
                "contest_id": result.contest_id,
                "standings": result.standings_imported,
                "players_created": len(result.players_created),
                "source_file": result.source_file,
            },
        )
        self._reset_json_state()
        self.admin_feedback = (
            f"已导入「{result.title}」：{result.standings_imported} 条成绩，"
            f"新建选手 {len(result.players_created)} 名，赛事等级「{result.tier_name}」"
        )

    @rx.event
    def discard_json_import(self):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self._reset_json_state()
        self.admin_feedback = "已取消，未写入任何数据"
        self.admin_error = ""

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
