"""Admin 用户与绑定审批状态。

三层守卫（docs/09 §4）：
1. on_load —— 非 admin 重定向
2. approve/reject 事件首行 ``_require_admin()`` —— 真正的写保护
3. pending_requests / users computed var —— 非 admin 返回空列表

跨库：绑定事实写 web DB（rx.session()）先 commit，AuditLog 到 core DB
（xcpc_core.audit）best-effort，失败不回滚绑定。
"""

from __future__ import annotations

from datetime import datetime, timezone

import reflex as rx
import reflex_local_auth
from sqlmodel import select

from xcpc_core.audit import record as audit_record
from xcpc_core.player import api as player_api

from xcpc_web.states.admin.base import AdminState
from xcpc_web.states.auth_models import BindingRequest, UserProfile


class AdminUsersState(AdminState):
    """/admin/users：绑定审批 + 用户列表。"""

    admin_feedback: str = ""
    admin_error: str = ""

    @rx.event
    def on_load(self):
        """第 1 层守卫：非 admin 重定向。"""
        if not self.is_authenticated:
            return rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE)
        if not self.is_admin:
            return rx.redirect("/")
        self.admin_feedback = ""
        self.admin_error = ""
        return None

    # ---- computed var（第 3 层守卫：非 admin 返回空）----

    @rx.var(cache=False)
    def pending_requests(self) -> list[dict]:
        """待审批绑定申请（含申请人/目标选手名称）。"""
        if not self.is_admin:
            return []
        with rx.session() as session:
            rows = session.exec(
                select(BindingRequest)
                .where(BindingRequest.status == "pending")
                .order_by(BindingRequest.created_at)
            ).all()
        if not rows:
            return []
        username_map = self._username_map({r.user_id for r in rows})
        name_map = self._player_name_map()
        return [
            {
                "request_id": r.id,
                "user_id": r.user_id,
                "username": username_map.get(r.user_id, f"#{r.user_id}"),
                "player_id": r.player_id,
                "player_name": name_map.get(r.player_id, r.player_id),
                "reason": r.reason or "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]

    @rx.var(cache=False)
    def users(self) -> list[dict]:
        """全部用户（角色 / 绑定状态），只读展示。"""
        if not self.is_admin:
            return []
        with rx.session() as session:
            from reflex_local_auth import LocalUser

            rows = session.exec(
                select(UserProfile, LocalUser)
                .join(LocalUser, LocalUser.id == UserProfile.user_id)
                .order_by(UserProfile.user_id)
            ).all()
        if not rows:
            return []
        name_map = self._player_name_map()
        return [
            {
                "user_id": up.user_id,
                "username": lu.username,
                "role": up.role,
                "bound_player_id": up.bound_player_id,
                "bound_player_name": (
                    name_map.get(up.bound_player_id, up.bound_player_id)
                    if up.bound_player_id
                    else ""
                ),
                "created_at": up.created_at.isoformat() if up.created_at else "",
            }
            for up, lu in rows
        ]


    # ---- 批量建号（五期：不允许自助注册，账号由管理员统一创建）----

    batch_text: str = ""
    batch_default_password: str = ""
    batch_result: list[dict] = []

    def set_batch_text(self, value: str) -> None:
        self.batch_text = value

    def set_batch_default_password(self, value: str) -> None:
        self.batch_default_password = value

    @rx.event
    def clear_batch(self):
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.batch_text = ""
        self.batch_default_password = ""
        self.batch_result = []
        self.admin_error = ""
        self.admin_feedback = ""
        return None

    @rx.event
    def submit_batch(self):
        """批量建号。

        每行格式：``用户名[,初始密码][,绑定选手ID]``
        - 只写用户名 → 用「默认初始密码」
        - 密码留空但给了选手 → 用默认密码
        - 绑定选手可选，指定时直接写 bound_player_id（须未被他人绑定）

        **逐行独立事务**：某行失败不影响其他行，结果逐行报告（成功/跳过/失败）。
        """
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_error = ""
        self.admin_feedback = ""

        raw_lines = [ln.strip() for ln in (self.batch_text or "").splitlines()]
        lines = [ln for ln in raw_lines if ln and not ln.startswith("#")]
        if not lines:
            self.admin_error = "请至少填写一行（格式：用户名[,密码][,选手ID]）"
            return None

        default_pw = (self.batch_default_password or "").strip()
        results: list[dict] = []
        created = 0

        for line in lines:
            parts = [p.strip() for p in line.replace("，", ",").split(",")]
            username = parts[0] if parts else ""
            password = parts[1] if len(parts) > 1 and parts[1] else default_pw
            player_id = parts[2] if len(parts) > 2 else ""

            outcome = self._create_one(
                username=username,
                password=password,
                player_id=player_id or None,
            )
            results.append({"line": line, "username": username, **outcome})
            if outcome["status"] == "created":
                created += 1

        self.batch_result = results
        skipped = sum(1 for r in results if r["status"] == "skipped")
        failed = sum(1 for r in results if r["status"] == "failed")
        self.admin_feedback = f"完成：成功 {created} 个，跳过 {skipped} 个，失败 {failed} 个"
        if created:
            self._audit_batch(created, skipped, failed)
        return None

    def _create_one(
        self, *, username: str, password: str, player_id: str | None
    ) -> dict:
        """建单个账号。返回 ``{"status": created|skipped|failed, "message": str}``。"""
        from reflex_local_auth import LocalUser

        if not username:
            return {"status": "failed", "message": "用户名为空"}
        if len(username) < 3:
            return {"status": "failed", "message": "用户名至少 3 位"}
        if not password or len(password) < 6:
            return {"status": "failed", "message": "密码至少 6 位（或设置默认初始密码）"}

        try:
            with rx.session() as session:
                exists = session.exec(
                    select(LocalUser).where(LocalUser.username == username)
                ).one_or_none()
                if exists is not None:
                    return {"status": "skipped", "message": "用户名已存在"}

                if player_id:
                    taken = session.exec(
                        select(UserProfile).where(UserProfile.bound_player_id == player_id)
                    ).one_or_none()
                    if taken is not None:
                        return {
                            "status": "failed",
                            "message": f"选手 {player_id} 已被 user#{taken.user_id} 绑定",
                        }

                user = LocalUser()
                user.username = username
                user.password_hash = LocalUser.hash_password(password)
                user.enabled = True
                session.add(user)
                session.flush()
                session.refresh(user)
                if user.id is None:
                    return {"status": "failed", "message": "创建失败（无 ID）"}
                session.add(
                    UserProfile(
                        user_id=user.id,
                        role="member",
                        bound_player_id=player_id or None,
                    )
                )
                session.commit()
                user_id = user.id
        except Exception as exc:  # 逐行隔离：一行失败不影响其他行
            return {"status": "failed", "message": str(exc)}

        return {
            "status": "created",
            "message": "已创建" + (f"，并绑定 {player_id}" if player_id else ""),
            "user_id": user_id,
        }

    def _audit_batch(self, created: int, skipped: int, failed: int) -> None:
        try:
            audit_record(
                action="user.batch_create",
                target="admin_users",
                user_id=self.authenticated_user.id,
                diff_json={
                    "created": created,
                    "skipped": skipped,
                    "failed": failed,
                    "usernames": [
                        r["username"] for r in self.batch_result if r["status"] == "created"
                    ],
                },
            )
        except Exception:
            pass

    @rx.var(cache=False)
    def batch_rows(self) -> list[dict]:
        """批量结果视图（含配色，避免在模板里做字符串比较以外的判断）。"""
        if not self.is_admin:
            return []
        return [
            {
                "line": r["line"],
                "username": r["username"],
                "status": r["status"],
                "label": {"created": "成功", "skipped": "跳过", "failed": "失败"}.get(
                    r["status"], r["status"]
                ),
                "tone": {"created": "green", "skipped": "gray", "failed": "red"}.get(
                    r["status"], "gray"
                ),
                "message": r["message"],
            }
            for r in self.batch_result
        ]

    @rx.var(cache=False)
    def player_options(self) -> list[str]:
        """绑定下拉可选选手（含已离队，便于补建历史账号）。"""
        if not self.is_admin:
            return []
        try:
            return [p.id for p in player_api.list_players(include_left=True)]
        except Exception:
            return []

    # ---- 辅助查询（非事件/非 var）----

    def _username_map(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        with rx.session() as session:
            from reflex_local_auth import LocalUser

            us = session.exec(
                select(LocalUser).where(LocalUser.id.in_(user_ids))
            ).all()
        return {u.id: u.username for u in us}

    def _player_name_map(self) -> dict[str, str]:
        try:
            players = player_api.list_players(include_left=True)
        except Exception:
            return {}
        return {p.id: p.name for p in players}

    # ---- 事件（第 2 层守卫：写操作前真校验）----

    @rx.event
    def approve(self, request_id: int):
        """批准绑定申请：申请者获得该选手，其余 pending 申请被驳回。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_feedback = ""
        self.admin_error = ""

        with rx.session() as session:
            req = session.exec(
                select(BindingRequest).where(BindingRequest.id == request_id)
            ).one_or_none()
            if req is None:
                self.admin_error = "申请不存在"
                return
            if req.status != "pending":
                self.admin_error = "该申请已被处理，请刷新页面"
                return
            # 唯一性预检：选手已被别人绑定 / 用户已绑别人
            holder = session.exec(
                select(UserProfile).where(UserProfile.bound_player_id == req.player_id)
            ).one_or_none()
            if holder is not None and holder.user_id != req.user_id:
                self.admin_error = "该选手已绑定其他用户"
                return
            applicant = session.exec(
                select(UserProfile).where(UserProfile.user_id == req.user_id)
            ).one_or_none()
            if applicant is not None and applicant.bound_player_id is not None:
                self.admin_error = "该用户已绑定其他选手"
                return
            # 快照标量（session 关闭后 expire）
            player_id = req.player_id
            applicant_user_id = req.user_id
            # 写绑定事实
            if applicant is not None:
                applicant.bound_player_id = player_id
            req.status = "approved"
            req.reviewed_by = self.authenticated_user.id
            req.reviewed_at = datetime.now(timezone.utc)
            # 自动驳回该用户其余 pending 申请
            for other in session.exec(
                select(BindingRequest).where(
                    BindingRequest.user_id == applicant_user_id,
                    BindingRequest.status == "pending",
                    BindingRequest.id != req.id,
                )
            ).all():
                other.status = "rejected"
                other.reviewed_by = self.authenticated_user.id
                other.reviewed_at = req.reviewed_at
            session.commit()

        # 审计 best-effort（core DB，失败不回滚绑定）
        try:
            audit_record(
                action="binding.approve",
                target=player_id,
                user_id=self.authenticated_user.id,
                diff_json={
                    "request_id": request_id,
                    "applicant_user_id": applicant_user_id,
                },
            )
        except Exception:
            # audit 失败不回滚，仅少一条日志
            pass
        self.admin_feedback = f"已批准绑定：{player_id}"

    @rx.event
    def reject(self, request_id: int):
        """驳回绑定申请：仅改状态，不改绑定。"""
        guard = self._require_admin()
        if guard is not None:
            return guard
        self.admin_feedback = ""
        self.admin_error = ""

        with rx.session() as session:
            req = session.exec(
                select(BindingRequest).where(BindingRequest.id == request_id)
            ).one_or_none()
            if req is None:
                self.admin_error = "申请不存在"
                return
            if req.status != "pending":
                self.admin_error = "该申请已被处理，请刷新页面"
                return
            player_id = req.player_id
            req.status = "rejected"
            req.reviewed_by = self.authenticated_user.id
            req.reviewed_at = datetime.now(timezone.utc)
            session.commit()

        try:
            audit_record(
                action="binding.reject",
                target=player_id,
                user_id=self.authenticated_user.id,
                diff_json={"request_id": request_id},
            )
        except Exception:
            pass
        self.admin_feedback = f"已驳回申请：{player_id}"
