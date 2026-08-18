"""Extended RegistrationState that creates UserProfile on registration.

In reflex 0.9.x an @rx.event override that calls super() queues the parent event
to run asynchronously (so self.new_user_id is still the old value right after),
and an inherited handler is registered under the base class path and runs on a
base-class instance. To guarantee the UserProfile is created, ExtendedRegistrationState
implements handle_registration itself and calls its own _register_user, which
creates LocalUser + UserProfile atomically in one transaction.
"""

from __future__ import annotations

import reflex as rx
import reflex_local_auth
from reflex_local_auth.user import LocalUser

from .auth_models import UserProfile


class ExtendedRegistrationState(reflex_local_auth.RegistrationState):
    """Extends RegistrationState to create UserProfile in the same flow."""

    def _register_user(self, username, password) -> None:
        """Create LocalUser + UserProfile atomically in one transaction."""
        with rx.session() as session:
            new_user = LocalUser()
            new_user.username = username
            new_user.password_hash = LocalUser.hash_password(password)
            new_user.enabled = True
            session.add(new_user)
            session.flush()
            session.refresh(new_user)
            if new_user.id is not None:
                self.new_user_id = new_user.id
                session.add(UserProfile(user_id=new_user.id, role="member"))
            session.commit()

    @rx.event
    def handle_registration(self, form_data: dict):
        """Validate, then create LocalUser + UserProfile in one flow."""
        username = form_data["username"]
        password = form_data["password"]
        validation_errors = self._validate_fields(
            username, password, form_data["confirm_password"]
        )
        if validation_errors:
            self.new_user_id = -1
            return validation_errors
        self._register_user(username, password)
        return type(self).successful_registration
