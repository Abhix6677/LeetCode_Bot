"""
Phase 2: Bulk Upload to Telegram
----------------------------------
Run this AFTER the generator has finished storing all solutions locally.
This script reads every completed solution from the SQLite DB and uploads
them to the appropriate Telegram archive channel, then saves the tg_msg_id.

Usage:
    python bulk_upload_to_telegram.py

Rate-limit: 3 seconds per message to stay under Telegram limits.
Estimated time: ~2.5 hours for 3000+ problems x 5 languages = 15000 msgs.
"""

import os
import json
import time
import logging
import sqlite3
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bulk_upload")

from database.db import Database
from generator.archive import ArchiveManager

THROTTLE_SECONDS = 3  # seconds between each Telegram send

def format_message(title, lang, approach, time_c, space_c, code, hints):
    lines = [
        f"[{lang.upper()}] {title}",
        "",
        "Approach:",
        approach or "(no approach)",
        "",
        f"Time: {time_c or '?'}  |  Space: {space_c or '?'}",
        "",
        "Code:",
        f"```{lang.lower().replace('c++','cpp').replace('c','c').replace('javascript','javascript')}",
        code or "(no code)",
        "```",
        "",
        "Hints:",
    ]
    for i, h in enumerate(hints, 1):
        lines.append(f"  {i}. {h}")
    return "\n".join(lines)

def main():
    db = Database()
    archive = ArchiveManager(db)
    archive.login()
    archive.ensure_channels()

    logger.info("Querying all completed solutions without Telegram IDs...")
    with db._conn() as c:
        rows = c.execute(
            """SELECT s.slug, s.language, s.approach, s.time_c, s.space_c, s.code, s.hints, p.title
               FROM solutions s
               JOIN problems p USING(slug)
               WHERE (s.tg_msg_id IS NULL OR s.tg_msg_id = 0)
                 AND s.code IS NOT NULL AND s.code != ''
               ORDER BY s.slug, s.language"""
        ).fetchall()

    total = len(rows)
    logger.info(f"Found {total} solutions to upload. Estimated time: {total * THROTTLE_SECONDS / 60:.0f} minutes.")

    success = 0
    failed = 0

    for i, row in enumerate(rows, 1):
        slug, lang, approach, time_c, space_c, code, hints_json, title = row
        try:
            hints = json.loads(hints_json) if hints_json else []
        except Exception:
            hints = []

        formatted = format_message(title, lang, approach, time_c, space_c, code, hints)

        tg_msg_id = archive.post_solution(lang, formatted)
        if tg_msg_id:
            chan_id = db.get_archive_channel(lang.lower())
            db.update_tg_ids(slug, lang, tg_msg_id, chan_id)
            success += 1
            logger.info(f"[{i}/{total}] OK: {slug} ({lang}) -> msg_id={tg_msg_id}")
        else:
            failed += 1
            logger.warning(f"[{i}/{total}] FAIL: {slug} ({lang})")

        time.sleep(THROTTLE_SECONDS)

    logger.info(f"Bulk upload complete! Success={success}, Failed={failed}")

    if success > 0:
        logger.info("Now wiping local text data to save space...")
        db.wipe_local_text()
        logger.info("Done! All solutions are now stored in Telegram channels.")

if __name__ == "__main__":
    main()
