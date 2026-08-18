"""Auth models: UserProfile and BindingRequest as SQLModel tables.

These tables live in the Reflex SQLModel database (same DB as LocalUser/LocalAuthSession
from reflex-local-auth) because they are accessed via rx.session() in the web layer.

xcpc_core does NOT import these models -- auth is a web-layer concern.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    __tablename__ = "userprofile"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(unique=True, index=True, foreign_key="localuser.id")
    role: str = Field(default="member")
    # player.id lives in the separate xcpc_core DB; FK not enforced across DBs.
    # Validation that the player exists happens in the service layer.
    bound_player_id: str | None = Field(default=None, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime | None = Field(default=None)


class BindingRequest(SQLModel, table=True):
    __tablename__ = "bindingrequest"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="localuser.id")
    # player.id is in the core DB; not an FK here.
    player_id: str = Field(index=True)
    reason: str | None = Field(default=None)
    status: str = Field(default="pending")
    reviewed_by: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: datetime | None = Field(default=None)
