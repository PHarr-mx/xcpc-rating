"""staged 导入 API；Web 层只通过此 facade 访问 ImportBatch。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from xcpc_core.importer.models import ContestJsonDocument, FormalImportParams
from xcpc_core.importer.contest_json import (
    import_contest_json as _import_json,
    preview_contest_json as _preview_json,
)
from xcpc_core.importer.staged import (
    confirm_import_batch as _confirm,
    discard_import_batch as _discard,
    get_import_batch as _get,
    list_import_batches as _list,
    stage_formal_xlsx as _stage,
)

_default_session: Session | None = None


def configure_session(session: Session | None) -> None:
    global _default_session
    _default_session = session


def preview_contest_json(
    document: ContestJsonDocument | dict[str, Any] | Path | str,
    *,
    repo_root: Path | None = None,
    session: Session | None = None,
):
    """P-U3 只读预览：校验 + 姓名匹配，不写库不归档。"""
    return _preview_json(
        document, repo_root=repo_root, session=session or _default_session
    )


def import_contest_json(
    document: ContestJsonDocument | dict[str, Any] | Path | str,
    *,
    auto_create_players: bool = True,
    default_grade: int | None = None,
    repo_root: Path | None = None,
    session: Session | None = None,
):
    """P-U3 通用比赛 JSON 导入（Web/CLI 共用入口）。"""
    return _import_json(
        document,
        auto_create_players=auto_create_players,
        default_grade=default_grade,
        repo_root=repo_root,
        session=session or _default_session,
    )


def stage_formal_xlsx(
    path: Path | str,
    params: FormalImportParams,
    *,
    uploaded_by: int,
    filename: str | None = None,
    repo_root: Path | None = None,
    session: Session | None = None,
):
    return _stage(
        path,
        params,
        uploaded_by=uploaded_by,
        filename=filename,
        repo_root=repo_root,
        session=session or _default_session,
    )


def get_import_batch(batch_id: int, *, session: Session | None = None):
    return _get(batch_id, session=session or _default_session)


def list_import_batches(*, status: str | None = None, session: Session | None = None):
    return _list(status=status, session=session or _default_session)


def discard_import_batch(batch_id: int, *, session: Session | None = None) -> None:
    _discard(batch_id, session=session or _default_session)


def confirm_import_batch(
    batch_id: int,
    decisions: dict[str, Any],
    *,
    repo_root: Path | None = None,
    session: Session | None = None,
):
    return _confirm(
        batch_id,
        decisions,
        repo_root=repo_root,
        session=session or _default_session,
    )
