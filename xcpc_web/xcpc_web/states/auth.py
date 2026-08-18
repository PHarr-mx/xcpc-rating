"""AuthState: extends reflex-local-auth with project roles and binding."""

from __future__ import annotations

import reflex as rx
import reflex_local_auth
from sqlmodel import select

from .auth_models import UserProfile


class AuthState(reflex_local_auth.LocalAuthState):
    """Global auth state: extends LocalAuthState with role and binding."""

    @rx.var(cache=True)
    def profile(self) -> dict | None:
        if not self.is_authenticated:
            return None
        with rx.session() as session:
            profile = session.exec(
                select(UserProfile).where(
                    UserProfile.user_id == self.authenticated_user.id
                )
            ).one_or_none()
        if profile is None:
            return None
        return {
            "user_id": profile.user_id,
            "role": profile.role,
            "bound_player_id": profile.bound_player_id,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "last_login_at": profile.last_login_at.isoformat() if profile.last_login_at else None,
        }

    @rx.var(cache=True)
    def is_admin(self) -> bool:
        return self.profile is not None and self.profile.get("role") == "admin"

    @rx.var(cache=True)
    def bound_player_id(self) -> str | None:
        if self.profile is None:
            return None
        return self.profile.get("bound_player_id")

    @rx.var(cache=True)
    def is_bound(self) -> bool:
        return self.bound_player_id is not None
