#!/usr/bin/env python3
"""
Repair a corrupted plex_debrid SQLite database (e.g. "database disk image is malformed").

Uses SQLite's .recover to extract all readable data into a new database, then replaces
the original. Requires sqlite3 CLI (usually bundled with SQLite).

Usage:
  python scripts/repair_sqlite_db.py [--config-dir DIR]

  --config-dir  Directory containing plex_debrid.sqlite3 (default: current directory)
"""

import argparse
import os
import shutil
import subprocess
import sys


def get_db_path(config_dir: str) -> str:
    return os.path.abspath(os.path.join(config_dir, "plex_debrid.sqlite3"))


def run_recover(db_path: str, recovered_path: str) -> bool:
    """Run sqlite3 .recover and pipe into a new database. Returns True on success."""
    try:
        # Remove existing recovered file so sqlite3 creates a new DB
        if os.path.exists(recovered_path):
            os.remove(recovered_path)
        # .recover outputs SQL; pipe it into sqlite3 to create the new DB
        p1 = subprocess.Popen(
            ["sqlite3", db_path, ".recover"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        p2 = subprocess.Popen(
            ["sqlite3", recovered_path],
            stdin=p1.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        p1.stdout.close()
        out, err = p2.communicate(timeout=300)
        if p1.wait(timeout=5) != 0:
            stderr = p1.stderr.read().decode(errors="replace") if p1.stderr else ""
            print(f"sqlite3 .recover failed: {stderr}")
            return False
        if p2.returncode != 0:
            print(f"sqlite3 reimport failed: {err.decode(errors='replace')}")
            return False
    except FileNotFoundError:
        print("sqlite3 CLI not found. Install SQLite (e.g. brew install sqlite3).")
        return False
    except subprocess.TimeoutExpired:
        print("sqlite3 .recover timed out.")
        return False
    except Exception as e:
        print(f"Error running recover: {e}")
        return False

    if not os.path.isfile(recovered_path) or os.path.getsize(recovered_path) == 0:
        print("Recovered database is missing or empty; source may be too damaged.")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair corrupted plex_debrid SQLite database using sqlite3 .recover"
    )
    parser.add_argument(
        "--config-dir",
        default=".",
        help="Directory containing plex_debrid.sqlite3 (default: current directory)",
    )
    args = parser.parse_args()
    config_dir = os.path.abspath(args.config_dir)
    db_path = get_db_path(config_dir)

    if not os.path.isfile(db_path):
        print(f"Database not found: {db_path}")
        return 1

    backup_path = db_path + ".corrupt.backup"
    recovered_path = db_path + ".recovered"

    print(f"Database: {db_path}")
    print("Creating backup of corrupted database...")
    try:
        shutil.copy2(db_path, backup_path)
    except Exception as e:
        print(f"Backup failed: {e}")
        return 1
    print(f"Backup saved to: {backup_path}")

    print("Running sqlite3 .recover (this may take a while for large DBs)...")
    if not run_recover(db_path, recovered_path):
        print("\nRecovery failed. Your original file is unchanged.")
        print("You can try:")
        print("  1. Install/upgrade SQLite (3.29+): brew install sqlite3")
        print("  2. Manually: sqlite3 path/to/plex_debrid.sqlite3 '.recover' | sqlite3 recovered.sqlite3")
        print("  3. Last resort: remove the database so the app creates a new one (you lose local state; Real-Debrid cache will resync from the API).")
        return 1

    print("Replacing original database with recovered copy...")
    try:
        shutil.move(recovered_path, db_path)
    except Exception as e:
        print(f"Replace failed: {e}")
        print(f"Recovered database is at: {recovered_path}")
        return 1

    print("Done. Database has been repaired. You can delete the backup when satisfied:")
    print(f"  rm {backup_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
