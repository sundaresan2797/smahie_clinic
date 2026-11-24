"""Create a clinic staff account, or reset an existing account's password.

Usage (from the project root):
    python -m scripts.create_admin doctor@example.com                 # admin role
    python -m scripts.create_admin reception@example.com --role staff
    python -m scripts.create_admin doctor@example.com --reset         # new password, sign out everywhere
    python -m scripts.create_admin doctor@example.com --deactivate

The password is prompted for interactively and never stored in source code.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import make_engine, make_session_factory
from app.core.security import MIN_PASSWORD_LENGTH, hash_password
from app.models import ADMIN_ROLES, AdminUser
from app.services.auth_service import audit, revoke_all_sessions


def prompt_password() -> str:
    while True:
        first = getpass.getpass(f"New password (min {MIN_PASSWORD_LENGTH} characters): ")
        if len(first) < MIN_PASSWORD_LENGTH:
            print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
            continue
        if getpass.getpass("Repeat password: ") != first:
            print("Passwords did not match.")
            continue
        return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--role", choices=ADMIN_ROLES, default="admin")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--reset", action="store_true", help="reset the password of an existing account")
    group.add_argument("--deactivate", action="store_true", help="disable the account and sign it out")
    args = parser.parse_args(argv)

    try:
        email = validate_email(args.email, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        print(f"Invalid email: {exc}")
        return 2

    engine = make_engine(get_settings().database_url)
    session_factory = make_session_factory(engine)
    with session_factory() as db:
        user = db.scalar(select(AdminUser).where(func.lower(AdminUser.email) == email))

        if args.deactivate:
            if not user:
                print("No such account.")
                return 1
            user.is_active = False
            revoke_all_sessions(db, user)
            audit(db, None, "deactivate", "admin_user", user.id, "via CLI")
            db.commit()
            print(f"Deactivated {email}.")
            return 0

        if args.reset:
            if not user:
                print("No such account. Run without --reset to create it.")
                return 1
            user.password_hash = hash_password(prompt_password())
            user.is_active = True
            revoke_all_sessions(db, user)
            audit(db, None, "password_reset", "admin_user", user.id, "via CLI")
            db.commit()
            print(f"Password reset for {email}; existing sessions were signed out.")
            return 0

        if user:
            print("An account with this email already exists. Use --reset to change its password.")
            return 1
        user = AdminUser(email=email, password_hash=hash_password(prompt_password()), role=args.role, is_active=True)
        db.add(user)
        db.flush()
        audit(db, None, "create_user", "admin_user", user.id, f"role={args.role} via CLI")
        db.commit()
        print(f"Created {args.role} account for {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
