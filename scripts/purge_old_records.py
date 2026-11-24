"""Delete old appointment requests and messages (data minimisation).

Usage (from the project root):
    python -m scripts.purge_old_records --days 365 --dry-run
    python -m scripts.purge_old_records --days 365

Deletes appointment requests whose preferred date, and contact messages whose
received date, are older than --days. Also clears expired sessions and old
rate-limit rows. Agree the retention period with the clinic and schedule this
(e.g. a weekly cron job). The audit log keeps no patient details and is kept.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta

from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.database import make_engine, make_session_factory, utcnow
from app.core.timeutil import today_ist
from app.models import AdminSession, Appointment, ContactMessage, RateLimitHit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=365, help="retention period in days (default 365)")
    parser.add_argument("--dry-run", action="store_true", help="show counts without deleting")
    args = parser.parse_args(argv)
    if args.days < 30:
        print("Refusing to purge with a retention period under 30 days.")
        return 2

    cutoff_date = today_ist() - timedelta(days=args.days)
    cutoff_ts = utcnow() - timedelta(days=args.days)
    session_factory = make_session_factory(make_engine(get_settings().database_url))
    with session_factory() as db:
        n_appt = db.scalar(
            select(func.count()).select_from(Appointment).where(Appointment.preferred_date < cutoff_date)
        )
        n_msg = db.scalar(select(func.count()).select_from(ContactMessage).where(ContactMessage.created_at < cutoff_ts))
        print(f"Appointments with preferred date before {cutoff_date}: {n_appt}")
        print(f"Messages received before {cutoff_ts:%Y-%m-%d}: {n_msg}")
        if args.dry_run:
            print("Dry run: nothing deleted.")
            return 0
        db.execute(delete(Appointment).where(Appointment.preferred_date < cutoff_date))
        db.execute(delete(ContactMessage).where(ContactMessage.created_at < cutoff_ts))
        db.execute(delete(AdminSession).where(AdminSession.expires_at < utcnow()))
        db.execute(delete(RateLimitHit).where(RateLimitHit.created_at < utcnow() - timedelta(days=2)))
        db.commit()
        print("Purge complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
