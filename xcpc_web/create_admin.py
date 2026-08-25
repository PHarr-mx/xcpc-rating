"""CLI to create the first admin user in the Reflex auth DB.

Usage:
    python create_admin.py --username admin --password secret          # 创建首个 admin
    python create_admin.py --username admin --password newpass --reset-password  # 重置已有用户密码
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is importable (xcpc_web package + rxconfig).
_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

from sqlalchemy.engine import Engine  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402
from reflex.model import ModelRegistry  # noqa: E402

# Import models so they register in the SQLModel metadata before create_all.
from reflex_local_auth import LocalUser  # noqa: E402
from reflex_local_auth.auth_session import LocalAuthSession  # noqa: E402
from xcpc_web.states.auth_models import UserProfile, BindingRequest  # noqa: E402


def _get_engine() -> Engine:
    import rxconfig  # type: ignore

    url = rxconfig.config.db_url
    if url is None:
        raise SystemExit("db_url is not configured in rxconfig.py")
    engine = create_engine(url)
    ModelRegistry.get_metadata().create_all(engine)
    return engine


def create_admin(username: str, password: str) -> int:
    """Create the first admin in one transaction: LocalUser + UserProfile(role=admin)."""
    engine = _get_engine()
    with Session(engine) as session:
        existing = session.exec(
            select(LocalUser).where(LocalUser.username == username)
        ).one_or_none()
        if existing is not None:
            print(f"User {username!r} already exists (id={existing.id}).", file=sys.stderr)
            sys.exit(1)

        user = LocalUser(
            username=username,
            password_hash=LocalUser.hash_password(password),
            enabled=True,
        )
        session.add(user)
        session.flush()
        session.refresh(user)
        if user.id is None:
            raise RuntimeError("Failed to assign id to new LocalUser")

        profile = session.exec(
            select(UserProfile).where(UserProfile.user_id == user.id)
        ).one_or_none()
        if profile is None:
            session.add(UserProfile(user_id=user.id, role="admin"))
        elif profile.role != "admin":
            profile.role = "admin"
            session.add(profile)
        session.commit()
        return user.id


def reset_password(username: str, password: str) -> int:
    """Reset an existing user's password; invalidate their active sessions."""
    engine = _get_engine()
    with Session(engine) as session:
        existing = session.exec(
            select(LocalUser).where(LocalUser.username == username)
        ).one_or_none()
        if existing is None:
            print(
                f"User {username!r} does not exist; cannot reset password. "
                "Create them first (without --reset-password).",
                file=sys.stderr,
            )
            sys.exit(1)

        existing.password_hash = LocalUser.hash_password(password)
        # 密码变更后使该用户的既有会话失效，防止旧会话继续以原密码持有者身份登录。
        for auth_session in session.exec(
            select(LocalAuthSession).where(LocalAuthSession.user_id == existing.id)
        ):
            session.delete(auth_session)
        session.commit()
        return existing.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset an admin user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="重置已有用户的密码并使其会话失效（用户不存在时报错）。",
    )
    args = parser.parse_args()

    if args.reset_password:
        user_id = reset_password(args.username, args.password)
        print(f"User {args.username!r} password reset (localuser.id={user_id}).")
    else:
        user_id = create_admin(args.username, args.password)
        print(f"Admin user {args.username!r} created (localuser.id={user_id}).")


if __name__ == "__main__":
    main()
