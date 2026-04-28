#!/usr/bin/env python3
"""
Migrate plex_debrid SQLite DB to support show inactivity cleanup tracking.

Adds columns to media_show if missing:
  - collected_episode_count INTEGER DEFAULT 0
  - last_collection_progress_at TEXT

Also initializes existing rows with safe defaults:
  - collected_episode_count = 0 where NULL
  - last_collection_progress_at = COALESCE(updated_at, datetime('now')) where NULL

Usage:
  python scripts/migrate_show_progress_columns.py --db /path/to/plex_debrid.sqlite3
  python scripts/migrate_show_progress_columns.py --db /path/to/plex_debrid.sqlite3 --dry-run
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from datetime import datetime


def ensure_columns(conn: sqlite3.Connection, dry_run: bool) -> list[str]:
    actions = []
    cols = [r[1] for r in conn.execute("PRAGMA table_info(media_show)").fetchall()]

    if "collected_episode_count" not in cols:
        actions.append("ADD COLUMN media_show.collected_episode_count INTEGER DEFAULT 0")
        if not dry_run:
            conn.execute("ALTER TABLE media_show ADD COLUMN collected_episode_count INTEGER DEFAULT 0")

    if "last_collection_progress_at" not in cols:
        actions.append("ADD COLUMN media_show.last_collection_progress_at TEXT")
        if not dry_run:
            conn.execute("ALTER TABLE media_show ADD COLUMN last_collection_progress_at TEXT")

    actions.append("INITIALIZE media_show.collected_episode_count where NULL")
    actions.append("INITIALIZE media_show.last_collection_progress_at where NULL")
    if not dry_run:
        conn.execute("UPDATE media_show SET collected_episode_count = 0 WHERE collected_episode_count IS NULL")
        conn.execute(
            "UPDATE media_show SET last_collection_progress_at = COALESCE(updated_at, datetime('now')) "
            "WHERE last_collection_progress_at IS NULL"
        )
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate media_show progress-tracking columns.")
    parser.add_argument("--db", required=True, help="Path to plex_debrid.sqlite3")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without modifying DB")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating timestamped .bak copy before migration",
    )
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return 1

    if not args.dry_run and not args.no_backup:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{db_path}.bak.{stamp}"
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    try:
        actions = ensure_columns(conn, args.dry_run)
        if args.dry_run:
            print("Dry-run mode: no changes applied.")
            for action in actions:
                print(f"- {action}")
        else:
            conn.commit()
            print("Migration complete.")
            for action in actions:
                print(f"- {action}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

