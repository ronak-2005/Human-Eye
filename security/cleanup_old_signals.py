"""
ml_engine/scripts/cleanup_old_signals.py

DATA RETENTION ENFORCEMENT SCRIPT
Owner: ML Engineer (builds) | Audited by: Security Engineer (quarterly)

PURPOSE:
  Deletes raw behavioral signal data older than 90 days.
  This is a legal requirement (GDPR data minimization) and a
  contractual security requirement.

SCHEDULE:
  Runs daily at 2am UTC via Celery beat.

AUDIT:
  Security Engineer audits this script's execution logs every quarter.
  Log format is FIXED — do not modify the log output structure.
  Any change to log format requires Security Engineer approval.

USAGE:
  # Run manually (for testing):
  python ml_engine/scripts/cleanup_old_signals.py --dry-run
  python ml_engine/scripts/cleanup_old_signals.py --execute

  # Run via Celery (production):
  Registered as task: ml_engine.scripts.cleanup_old_signals.run_cleanup
"""

import argparse
import logging
import sys
from datetime import datetime, timezone, timedelta

# Configure structured logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": %(message)s}',
    level=logging.INFO
)
logger = logging.getLogger("security.data_retention")

RETENTION_DAYS = 90  # FIXED — do not change without Security Engineer approval


def get_cutoff_date() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)


def count_signals_to_delete(db_session, cutoff: datetime) -> int:
    """Count how many records would be deleted. Used for dry run and pre-delete check."""
    from backend.models.behavioral_signal import BehavioralSignal
    return db_session.query(BehavioralSignal)\
        .filter(BehavioralSignal.captured_at < cutoff)\
        .count()


def run_cleanup(db_session=None, dry_run: bool = False) -> dict:
    """
    Main cleanup function. Called by Celery beat daily.
    
    Returns:
        dict with cleanup results (also logged in security audit format)
    
    THIS FUNCTION'S LOG OUTPUT FORMAT IS AUDITED BY SECURITY ENGINEER.
    DO NOT MODIFY THE LOG STATEMENT STRUCTURE.
    """
    from backend.core.database import get_db_session
    from backend.models.behavioral_signal import BehavioralSignal

    if db_session is None:
        db_session = next(get_db_session())

    cutoff = get_cutoff_date()
    run_start = datetime.now(timezone.utc)

    # Count before deletion
    to_delete_count = count_signals_to_delete(db_session, cutoff)

    if dry_run:
        result = {
            "dry_run": True,
            "cutoff_date": cutoff.isoformat(),
            "records_would_delete": to_delete_count,
            "run_at": run_start.isoformat(),
            "retention_policy_days": RETENTION_DAYS
        }
        # Security audit log — FIXED FORMAT
        logger.info(
            '{"event_type": "data_retention_dry_run", '
            f'"cutoff_date": "{cutoff.isoformat()}", '
            f'"records_would_delete": {to_delete_count}, '
            f'"run_at": "{run_start.isoformat()}", '
            f'"retention_policy_days": {RETENTION_DAYS}'
            '}'
        )
        print(f"[DRY RUN] Would delete {to_delete_count} records older than {cutoff.date()}")
        return result

    # Execute deletion
    deleted_count = db_session.query(BehavioralSignal)\
        .filter(BehavioralSignal.captured_at < cutoff)\
        .delete(synchronize_session=False)

    db_session.commit()

    run_end = datetime.now(timezone.utc)
    duration_ms = (run_end - run_start).total_seconds() * 1000

    # ════════════════════════════════════════════════════════════════
    # SECURITY AUDIT LOG — THIS FORMAT IS NON-NEGOTIABLE
    # Security Engineer audits this exact structure quarterly.
    # Any modification requires Security Engineer approval.
    # ════════════════════════════════════════════════════════════════
    logger.info(
        '{"event_type": "data_retention_cleanup", '
        f'"cutoff_date": "{cutoff.isoformat()}", '
        f'"records_deleted": {deleted_count}, '
        f'"records_found_before_delete": {to_delete_count}, '
        f'"run_at": "{run_start.isoformat()}", '
        f'"completed_at": "{run_end.isoformat()}", '
        f'"duration_ms": {round(duration_ms, 1)}, '
        f'"retention_policy_days": {RETENTION_DAYS}, '
        f'"status": "success"'
        '}'
    )

    result = {
        "dry_run": False,
        "cutoff_date": cutoff.isoformat(),
        "records_deleted": deleted_count,
        "duration_ms": round(duration_ms, 1),
        "status": "success"
    }

    return result


def verify_no_stale_signals(db_session) -> dict:
    """
    Verify no signals older than RETENTION_DAYS + 5 days exist.
    Security Engineer runs this check quarterly.
    Returns pass/fail for the audit.
    """
    from backend.models.behavioral_signal import BehavioralSignal

    # 5-day grace window beyond the retention period
    hard_cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS + 5)

    stale_count = db_session.query(BehavioralSignal)\
        .filter(BehavioralSignal.captured_at < hard_cutoff)\
        .count()

    oldest_record = db_session.query(BehavioralSignal)\
        .order_by(BehavioralSignal.captured_at.asc())\
        .first()

    audit_result = {
        "audit_date": datetime.now(timezone.utc).isoformat(),
        "retention_policy_days": RETENTION_DAYS,
        "grace_window_days": 5,
        "stale_records_found": stale_count,
        "oldest_record_date": oldest_record.captured_at.isoformat() if oldest_record else None,
        "audit_pass": stale_count == 0
    }

    if stale_count > 0:
        logger.warning(
            '{"event_type": "data_retention_audit_FAIL", '
            f'"stale_records": {stale_count}, '
            f'"oldest_record": "{oldest_record.captured_at.isoformat() if oldest_record else None}", '
            f'"audit_date": "{datetime.now(timezone.utc).isoformat()}"'
            '}'
        )
    else:
        logger.info(
            '{"event_type": "data_retention_audit_PASS", '
            f'"audit_date": "{datetime.now(timezone.utc).isoformat()}"'
            '}'
        )

    return audit_result


# ─────────────────────────────────────────────────
# CLI entry point — for manual testing and cron use
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HumanEye Signal Data Retention Cleanup")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the deletion"
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run audit check (Security Engineer use — verify no stale data exists)"
    )
    args = parser.parse_args()

    if not any([args.dry_run, args.execute, args.audit]):
        print("Error: specify --dry-run, --execute, or --audit")
        print("Use --dry-run first to see what would be deleted.")
        sys.exit(1)

    # Import db session
    try:
        from backend.core.database import get_db_session
        db = next(get_db_session())
    except ImportError:
        print("Error: cannot import database session. Run from project root.")
        sys.exit(1)

    if args.dry_run:
        result = run_cleanup(db, dry_run=True)
        print(f"\nDRY RUN COMPLETE")
        print(f"Would delete: {result['records_would_delete']} records")
        print(f"Cutoff date:  {result['cutoff_date']}")

    elif args.execute:
        print("Executing deletion...")
        result = run_cleanup(db, dry_run=False)
        print(f"\nDELETION COMPLETE")
        print(f"Deleted:      {result['records_deleted']} records")
        print(f"Duration:     {result['duration_ms']}ms")
        print(f"Status:       {result['status']}")

    elif args.audit:
        print("Running retention audit...")
        result = verify_no_stale_signals(db)
        print(f"\nAUDIT RESULT: {'PASS ✅' if result['audit_pass'] else 'FAIL ❌'}")
        print(f"Stale records found: {result['stale_records_found']}")
        print(f"Oldest record: {result['oldest_record_date']}")
        if not result['audit_pass']:
            print("\nACTION REQUIRED: Stale records exist. Run --execute to clean up.")
            print("Notify Security Engineer if this persists after cleanup.")
            sys.exit(1)
