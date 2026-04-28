#!/usr/bin/env python3
"""
Backfill media_show.watchlisted_at and media_movie.watchlisted_at using Plex Community API activity feed.

The Plex web app shows "Watchlisted at <date>" on the Activity tab for an item (film or TV).
That date comes from the GraphQL API at https://community.plex.tv/api via the
GetActivityFeed query with types including "WATCHLIST". The response includes
nodes with __typename "ActivityWatchlist" and a "date" field (ISO 8601).
Same API works for both movies (e.g. plex://movie/<id>) and shows (plex://show/<id>).

This script:
- Reads Plex user token(s) from settings.json
- For each film (media_movie) or show (media_show) with a Plex-style guid,
  calls the activity feed for that metadata ID and extracts the watchlist date
- Updates watchlisted_at with the fetched date (ISO format)

Usage:
  python scripts/backfill_watchlisted_at_from_plex_activity.py [--type films|tv|both] [--config-dir DIR] [--dry-run] [--delay SEC]

Requires: run from project root so imports and settings path resolve.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

# Project root is parent of scripts/
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Plex Community API: same as Plex Web activity tab
COMMUNITY_API_URL = "https://community.plex.tv/api"

# GraphQL query used by Plex Web for the activity feed (filtered to WATCHLIST for this item)
GET_ACTIVITY_FEED_QUERY = """
query GetActivityFeed($first: PaginationInt!, $after: String, $metadataID: ID, $types: [ActivityType!]!, $includeDescendants: Boolean = false) {
  activityFeed(
    first: $first
    after: $after
    metadataID: $metadataID
    types: $types
    includeDescendants: $includeDescendants
  ) {
    nodes {
      __typename
      date
      id
      metadataItem {
        id
      }
    }
    pageInfo {
      endCursor
      hasNextPage
    }
  }
}
"""


def load_settings(config_dir: str) -> dict:
    path = os.path.join(config_dir, "settings.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Settings not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_plex_tokens(settings: dict) -> list[tuple[str, str]]:
    users = settings.get("Plex users") or []
    tokens = []
    for u in users:
        if isinstance(u, (list, tuple)) and len(u) >= 2:
            tokens.append((str(u[0]), str(u[1])))
    return tokens


def extract_metadata_id_from_guid(guid: str | None) -> str | None:
    """Get Plex metadata ID from media_show/media_movie.guid for use in community API."""
    if not guid or not isinstance(guid, str):
        return None
    s = guid.strip()
    # plex://show/6624b9fa413f5e32010f341a or plex://movie/6447b87c6de855c20103c28c -> id
    if s.startswith("plex://") and "/" in s:
        return s.split("/")[-1] or None
    # Already a raw 24-char hex ID (Plex discover ratingKey)
    if re.match(r"^[a-f0-9]{24}$", s, re.IGNORECASE):
        return s
    return None


def fetch_watchlist_date_for_metadata(
    metadata_id: str,
    token: str,
    session: object | None = None,
) -> str | None:
    """
    Call Plex Community API GetActivityFeed for this item and return the
    watchlist activity date (ISO 8601 string), or None if not found.
    """
    try:
        import urllib.request
        import urllib.error

        body = json.dumps({
            "query": GET_ACTIVITY_FEED_QUERY.strip(),
            "variables": {
                "first": 25,
                "after": None,
                "metadataID": metadata_id,
                "types": ["WATCHLIST"],
                "includeDescendants": True,
            },
            "operationName": "GetActivityFeed",
        }).encode("utf-8")

        req = urllib.request.Request(
            COMMUNITY_API_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "*/*",
                "x-plex-token": token,
                "x-plex-client-identifier": "plex-debrid-backfill",
                "x-plex-product": "Plex Debrid",
                "x-plex-version": "1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [api error] {metadata_id}: {e}", file=sys.stderr)
        return None

    feed = (data or {}).get("data") or {}
    nodes = (feed.get("activityFeed") or {}).get("nodes") or []
    for node in nodes:
        if node.get("__typename") == "ActivityWatchlist":
            date_val = node.get("date")
            if date_val and isinstance(date_val, str):
                return date_val
    return None


def process_table(
    conn,
    table: str,
    token: str,
    dry_run: bool,
    delay: float,
) -> tuple[int, int, int]:
    """Process one table (media_movie or media_show). Returns (updated, skipped, failed)."""
    assert table in ("media_movie", "media_show")
    cursor = conn.execute(
        f"SELECT guid, title, year, watchlisted_at FROM {table} ORDER BY guid"
    )
    rows = cursor.fetchall()
    updated = 0
    skipped = 0
    failed = 0
    for (guid, title, year, current_at) in rows:
        meta_id = extract_metadata_id_from_guid(guid)
        if not meta_id:
            skipped += 1
            continue

        date_str = fetch_watchlist_date_for_metadata(meta_id, token)
        if date_str is None:
            failed += 1
            time.sleep(delay)
            continue

        if current_at == date_str:
            skipped += 1
            time.sleep(delay)
            continue

        label = f"{title or '?'} ({year or '?'})"
        if dry_run:
            print(f"[dry-run] would set watchlisted_at = {date_str!r} for {table} {label} (guid={guid})")
            updated += 1
        else:
            try:
                conn.execute(
                    f"UPDATE {table} SET watchlisted_at = ? WHERE guid = ?",
                    (date_str, guid),
                )
                conn.commit()
                print(f"Updated {table} watchlisted_at = {date_str!r} for {label}")
                updated += 1
            except Exception as e:
                print(f"  [db error] {label}: {e}", file=sys.stderr)
                failed += 1
        time.sleep(delay)
    return updated, skipped, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill watchlisted_at from Plex Community API activity feed (films and/or TV).",
    )
    parser.add_argument(
        "--type",
        choices=("films", "tv", "both"),
        default="both",
        help="Which media to process: films (media_movie), tv (media_show), or both (default)",
    )
    parser.add_argument(
        "--config-dir",
        default=".",
        help="Directory containing settings.json (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would be updated, do not write to DB",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to wait between API calls (default: 0.5)",
    )
    args = parser.parse_args()

    config_dir = os.path.abspath(args.config_dir)
    if config_dir != ".":
        os.chdir(config_dir)
    else:
        config_dir = os.getcwd()

    # Load settings and get first Plex token
    try:
        settings = load_settings(config_dir)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    tokens = get_plex_tokens(settings)
    if not tokens:
        print("No Plex users found in settings.json.", file=sys.stderr)
        return 1
    user_name, token = tokens[0]
    print(f"Using Plex user: {user_name}")

    # Init DB (use project root or config_dir for DB path)
    from store import sqlite_store
    db_path = sqlite_store.init_db(config_dir)
    print(f"Database: {db_path}")

    conn = sqlite_store._get_connection()
    total_updated = 0
    total_skipped = 0
    total_failed = 0

    if args.type in ("films", "both"):
        print("Processing media_movie (films)...")
        u, s, f = process_table(
            conn, "media_movie", token, args.dry_run, args.delay
        )
        total_updated += u
        total_skipped += s
        total_failed += f
        if args.type == "films":
            print(f"Done: updated={total_updated}, skipped={total_skipped}, failed={total_failed}")
            return 0

    if args.type in ("tv", "both"):
        print("Processing media_show (TV)...")
        u, s, f = process_table(
            conn, "media_show", token, args.dry_run, args.delay
        )
        total_updated += u
        total_skipped += s
        total_failed += f

    print(f"Done: updated={total_updated}, skipped={total_skipped}, failed={total_failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
