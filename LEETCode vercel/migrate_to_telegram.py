import os
import json
import time
from database.db import Database
from generator.archive import ArchiveManager

def migrate():
    db = Database()
    archive = ArchiveManager(db)
    archive.login()
    archive.ensure_channels()
    
    print("Fetching local solutions that need to be migrated to Telegram...")
    with db._conn() as c:
        rows = c.execute(
            "SELECT slug, language, approach, time_c, space_c, code, hints, title FROM solutions JOIN problems USING(slug) WHERE (approach != '' OR code != '') AND (tg_msg_id IS NULL OR tg_msg_id = 0)"
        ).fetchall()
        
    print(f"Found {len(rows)} local solutions to migrate.")
    
    for i, row in enumerate(rows, 1):
        slug, lang, approach, time_c, space_c, code, hints_json, title = row
        print(f"[{i}/{len(rows)}] Migrating {slug} ({lang})...")
        
        try:
            hints = json.loads(hints_json) if hints_json else []
        except Exception:
            hints = []
            
        lines = [
            f"[SOLUTION] {title} - {lang.capitalize()}",
            "",
            "Approach:",
            approach or "",
            "",
            f"Time: {time_c or '?'}  |  Space: {space_c or '?'}",
            "",
            "Code:",
            f"```{lang.lower()}",
            code or "",
            "```",
            "",
            "Hints:",
        ]
        for idx, h in enumerate(hints, 1):
            lines.append(f"  {idx}. {h}")
            
        formatted = "\n".join(lines)
        
        tg_msg_id = archive.post_solution(lang, formatted)
        if tg_msg_id:
            chan_id = db.get_archive_channel(lang.lower())
            db.update_tg_ids(slug, lang, tg_msg_id, chan_id)
            print(f"  -> OK: msg_id={tg_msg_id}")
        else:
            print(f"  -> FAIL: could not post {slug} ({lang})")
        
        time.sleep(3)  # 3s throttle = ~20 msgs/min to stay safe

    print("Wiping local text data...")
    db.wipe_local_text()
    print("Migration complete! All solutions are now in Telegram channels.")
    
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    migrate()
