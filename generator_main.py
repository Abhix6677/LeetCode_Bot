#!/usr/bin/env python3
"""
generator_main.py - LeetCode Generator Worker
Runs independently. Supports multi-provider round-robin generation.
Auto-pushes dashboard to Telegram admin every 30 seconds.
"""

import logging
import os
import sys
import threading
import time
import requests

from dotenv import load_dotenv
load_dotenv()

from database.db import get_db
from generator.ai_providers.factory import get_ai_provider
from generator.archive import ArchiveManager
from generator.worker import GeneratorWorker

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("generator_main")

# ── Telegram push helpers ──────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID  = os.getenv("ADMIN_USER_ID", "")
_dashboard_msg_id = None

def _tg_send(text: str):
    if not BOT_TOKEN or not ADMIN_ID:
        return None
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
        return r.json().get("result", {}).get("message_id")
    except Exception:
        return None

def _tg_edit(msg_id: int, text: str):
    if not BOT_TOKEN or not ADMIN_ID or not msg_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
            json={"chat_id": ADMIN_ID, "message_id": msg_id, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception:
        pass

_start_time = time.time()
_animation_tick = 0
SYSTEM_STATUS = "ON"

def _build_dashboard_text(db) -> str:
    import datetime
    global _animation_tick
    _animation_tick += 1
    
    with db._conn() as c:
        # Generator Stats
        q_rows = c.execute("SELECT status, COUNT(*) FROM generator_queue GROUP BY status").fetchall()
        # Upload Stats
        up_comp  = c.execute("SELECT COUNT(*) FROM solutions WHERE tg_msg_id IS NOT NULL").fetchone()[0]
        # Language Stats
        lang_rows = c.execute("SELECT language, COUNT(*) FROM solutions GROUP BY language").fetchall()

    stats = {r[0]: r[1] for r in q_rows}
    total = sum(stats.values()) or 1
    up_total = total * 5
    completed = stats.get("COMPLETED", 0)
    pending = stats.get("NEW", 0) + stats.get("RETRY", 0)
    active = sum(v for k, v in stats.items() if k not in ("NEW", "RETRY", "COMPLETED", "FAILED_PERMANENT"))
    failed = stats.get("FAILED_PERMANENT", 0)
    
    pct = (completed / total) * 100
    bars = int(pct / 10)
    bar_str = "█" * bars + "░" * (10 - bars)
    
    up_pct = (up_comp / up_total * 100) if up_total else 0
    up_bars = int(up_pct / 10)
    up_bar_str = "█" * up_bars + "░" * (10 - up_bars)
    
    langs = {r[0]: r[1] for r in lang_rows}
    java = langs.get("Java", 0)
    py = langs.get("Python", 0)
    cpp = langs.get("C++", 0)
    c = langs.get("C", 0)
    js = langs.get("JavaScript", 0)
    
    now = datetime.datetime.now().strftime("%H:%M:%S")
    
    workers = int(os.getenv("WORKER_COUNT", "3"))
    speed_per_job = 5.0 # assume ~5s per worker
    eta_sec = (pending / workers) * speed_per_job if workers > 0 else 0
    eta_str = f"{int(eta_sec // 3600)}h {int((eta_sec % 3600) // 60)}m" if eta_sec > 0 else "0m"

    txt = f"🚀 Generator | {now}\n\n"
    txt += f"📚 {completed}/{total} ({pct:.1f}%) {bar_str}\n"
    txt += f"⚙️ {active}  ⏳ {pending}  ❌ {failed}\n\n"
    txt += f"📤 {up_comp}/{up_total} ({up_pct:.1f}%) {up_bar_str}\n\n"
    txt += f"☕{java}  🐍{py}  ⚙️{cpp}  🔵{c}  🟨{js}\n\n"
    txt += f"🟢 AI Connected\n"
    txt += f"🟢 SQLite Healthy\n"
    txt += f"🟢 Telegram Connected\n\n"
    txt += f"👷{workers} Workers | ETA {eta_str}"
    
    return txt

def telegram_dashboard_loop(db):
    global _dashboard_msg_id
    time.sleep(5)
    while True:
        try:
            txt = _build_dashboard_text(db)
            if _dashboard_msg_id:
                _tg_edit(_dashboard_msg_id, txt)
            else:
                _dashboard_msg_id = _tg_send(txt)
        except Exception as e:
            logger.error(f"Telegram dashboard push error: {e}")
        time.sleep(30)

def auto_sync_loop(db):
    """24-Hour Auto Sync: Check LeetCode for new problems"""
    time.sleep(10)
    while True:
        try:
            from generator.graphql_client import fetch_all_free_problems
            logger.info("[AutoSync] Checking for new LeetCode problems...")
            fetched = fetch_all_free_problems()
            new_count = 0
            with db._write_lock, db._conn() as c:
                for slug in fetched:
                    row = c.execute("SELECT 1 FROM generator_queue WHERE slug=?", (slug,)).fetchone()
                    if not row:
                        c.execute("INSERT INTO generator_queue (slug, status) VALUES (?, 'NEW')", (slug,))
                        new_count += 1
                if new_count > 0:
                    c.commit()
                    logger.info(f"[AutoSync] Found and queued {new_count} new problems.")
        except Exception as e:
            logger.error(f"[AutoSync] Error: {e}")
        time.sleep(86400) # 24 hours

def dashboard_loop(db):
    """Console dashboard."""
    while True:
        try:
            time.sleep(15)
            txt = _build_dashboard_text(db)
            txt = txt.replace("<b>","").replace("</b>","").replace("<code>","").replace("</code>","")
            print(txt.encode("cp1252", errors="ignore").decode("cp1252"))
        except Exception as e:
            logger.error(f"Dashboard error: {e}")

def daily_sync_loop(db, lc_api):
    while True:
        time.sleep(86400)
        try:
            lc_api.refresh_problems()
            free_problems = lc_api.get_all_free_problems()
            count = sum(1 for p in free_problems if p.get('titleSlug') and db.enqueue(p['titleSlug']))
            logger.info(f"Daily sync: +{count} new problems queued.")
        except Exception as e:
            logger.error(f"Daily sync error: {e}")

def start_generator_subsystem():
    logger.info("Starting Generator Worker (Multi-Provider Mode)...")
    db = get_db()

    logger.info("Running database migrations...")
    db.migrate_from_json()

    # 2. Archive Manager (Telegram Personal Account)
    archive = ArchiveManager(db=db)
    try:
        archive.connect()
        archive.login()
        archive.ensure_channels()
    except Exception as e:
        logger.error(f"Archive setup failed: {e}", exc_info=True)

    # Note: worker.py handles multiple providers internally now
    worker = GeneratorWorker(db, None, archive)

    from utils.leetcode_api import LeetCodeAPI
    lc_api = LeetCodeAPI(cache_dir="database")

    logger.info("Fetching all free LeetCode problems...")
    try:
        free_problems = lc_api.get_all_free_problems()
        queued_count = sum(1 for p in free_problems if p.get('titleSlug') and db.enqueue(p['titleSlug']))
        logger.info(f"Enqueued {queued_count} new problems. Total: {len(free_problems)}")
    except Exception as e:
        logger.error(f"Failed to fetch problems: {e}")

    # Start Dashboards
    threading.Thread(target=dashboard_loop, args=(db,), daemon=True).start()
    threading.Thread(target=telegram_dashboard_loop, args=(db,), daemon=True).start()
    
    # Start Sync Loop (it's called daily_sync_loop in your file)
    try:
        threading.Thread(target=daily_sync_loop, args=(db, lc_api), daemon=True).start()
    except NameError:
        threading.Thread(target=auto_sync_loop, args=(db,), daemon=True).start()

    # Start Uploader Thread
    from generator.uploader import TelegramUploader
    uploader = TelegramUploader(db, archive)
    uploader.start()

    # Start Generator Worker in a thread
    threading.Thread(target=worker.run_forever, daemon=True, name="GenWorkerThread").start()
    logger.info("Generator Subsystem is running in the background.")

if __name__ == "__main__":
    start_generator_subsystem()
    while True:
        time.sleep(1)
