"""
database/db.py
──────────────
Singleton SQLite manager with in-memory RAM cache.

• RAM cache  – instant lookups (0ms).
• SQLite     – persistent source of truth (<5ms).
• JSON files – read once on first startup for migration; never written here.

Thread-safe: all writes use a dedicated lock.
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
_DB_LOCK = threading.Lock()
_INSTANCE: "Database | None" = None


def get_db(db_path: str = "database/bot.db") -> "Database":
    """Return the singleton Database instance (creates it on first call)."""
    global _INSTANCE
    if _INSTANCE is None:
        with _DB_LOCK:
            if _INSTANCE is None:
                _INSTANCE = Database(db_path)
    return _INSTANCE


# ──────────────────────────────────────────────────────────────────────────────

class Database:
    """SQLite + RAM cache manager."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS problems (
        slug        TEXT PRIMARY KEY,
        number      INTEGER UNIQUE,
        title       TEXT,
        difficulty  TEXT,
        topic       TEXT,
        url         TEXT,
        description TEXT,
        fetched_at  TEXT
    );

    CREATE TABLE IF NOT EXISTS solutions (
        slug        TEXT,
        language    TEXT,
        approach    TEXT,
        time_c      TEXT,
        space_c     TEXT,
        code        TEXT,
        hints       TEXT,       -- JSON array of 3 strings
        intuition   TEXT,
        key_idea    TEXT,
        step_by_step TEXT,
        tg_msg_id   INTEGER,
        tg_chan_id  INTEGER,
        generated_at TEXT,
        solution_version TEXT,
        prompt_version TEXT,
        model_name TEXT,
        PRIMARY KEY (slug, language)
    );

    CREATE TABLE IF NOT EXISTS archive_channels (
        language     TEXT PRIMARY KEY,
        channel_id   INTEGER,
        channel_name TEXT
    );

    CREATE TABLE IF NOT EXISTS generator_queue (
        slug        TEXT PRIMARY KEY,
        status      TEXT    DEFAULT 'NEW',
        retries     INTEGER DEFAULT 0,
        error_msg   TEXT,
        created_at  TEXT    DEFAULT (datetime('now')),
        updated_at  TEXT    DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS upload_queue (
        slug        TEXT,
        language    TEXT,
        status      TEXT    DEFAULT 'PENDING',
        error_msg   TEXT,
        created_at  TEXT    DEFAULT (datetime('now')),
        PRIMARY KEY (slug, language)
    );
    """

    def __init__(self, db_path: str = "database/bot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self._write_lock = threading.Lock()

        # RAM cache
        self._ram_solutions: Dict[str, Dict[str, Dict]] = {}  # slug → lang → data
        self._ram_hints:     Dict[str, Dict[str, List]]  = {}  # slug → lang → [h1,h2,h3]
        self._ram_desc:      Dict[str, str]               = {}  # slug → description

        self._setup_schema()
        self._load_to_ram()
        logger.info(
            f"[DB] Ready | db={db_path} | "
            f"solutions={sum(len(v) for v in self._ram_solutions.values())} "
            f"| descriptions={len(self._ram_desc)}"
        )

    # ── internal helpers ──────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _setup_schema(self):
        with self._conn() as c:
            c.executescript(self.SCHEMA)
            
            # Migrate existing solutions table
            try:
                c.execute("ALTER TABLE solutions ADD COLUMN solution_version TEXT")
                c.execute("ALTER TABLE solutions ADD COLUMN prompt_version TEXT")
                c.execute("ALTER TABLE solutions ADD COLUMN model_name TEXT")
            except Exception:
                pass
                
            # If the old generator_queue exists (with 'language' column), drop it and recreate
            # because the queue architecture changed completely from per-lang to per-slug.
            try:
                # Check if old table structure exists
                row = c.execute("PRAGMA table_info(generator_queue)").fetchall()
                cols = [r[1] for r in row]
                if 'language' in cols:
                    logger.info("Dropping legacy generator_queue (per-language) for new (per-slug) architecture...")
                    c.execute("DROP TABLE generator_queue")
                    c.executescript(self.SCHEMA)
            except Exception as e:
                logger.error(f"[DB] Migration check error: {e}")

    def _load_to_ram(self):
        """Load everything from SQLite into memory at startup."""
        with self._conn() as c:
            # Add columns if missing
            try:
                c.execute("ALTER TABLE solutions ADD COLUMN intuition TEXT")
                c.execute("ALTER TABLE solutions ADD COLUMN key_idea TEXT")
                c.execute("ALTER TABLE solutions ADD COLUMN step_by_step TEXT")
            except Exception:
                pass
            for slug, lang, approach, time_c, space_c, code, hints_json, intuition, key_idea, step_by_step in c.execute(
                "SELECT slug, language, approach, time_c, space_c, code, hints, intuition, key_idea, step_by_step FROM solutions"
            ):
                self._put_ram(slug, lang, approach, time_c, space_c, code, hints_json, intuition, key_idea, step_by_step)

            for slug, desc in c.execute("SELECT slug, description FROM problems WHERE description IS NOT NULL"):
                self._ram_desc[slug] = desc

    def _put_ram(self, slug, lang, approach, time_c, space_c, code, hints_json, intuition=None, key_idea=None, step_by_step=None):
        k = lang.lower()
        if slug not in self._ram_solutions:
            self._ram_solutions[slug] = {}
            self._ram_hints[slug] = {}
        self._ram_solutions[slug][k] = {
            "approach": approach or "",
            "time":     time_c  or "O(?)",
            "space":    space_c or "O(?)",
            "code":     code    or "",
            "intuition": intuition or "",
            "key_idea": key_idea or "",
            "step_by_step": step_by_step or ""
        }
        if hints_json:
            try:
                self._ram_hints[slug][k] = json.loads(hints_json)
            except Exception:
                pass

    # ── read API (used by bot) ────────────────────────────────────────────────

    def get_solution(self, slug: str, lang: str) -> Optional[Dict]:
        """Lookup solution. Returns tg_msg_id/tg_chan_id if Telegram-uploaded, else full local data."""
        k = lang.lower()
        # Check RAM first (has full data after generation)
        if slug in self._ram_solutions and k in self._ram_solutions[slug]:
            sol = self._ram_solutions[slug][k]
            # Also try to get tg_ids from DB
            try:
                with self._conn() as c:
                    row = c.execute(
                        "SELECT tg_msg_id, tg_chan_id FROM solutions WHERE slug=? AND language=?",
                        (slug, k)
                    ).fetchone()
                    if row and row[0] and row[1]:
                        sol = dict(sol)
                        sol["tg_msg_id"] = row[0]
                        sol["tg_chan_id"] = row[1]
            except Exception:
                pass
            return sol

        # Fallback: read full data from SQLite
        try:
            with self._conn() as c:
                row = c.execute(
                    "SELECT approach, time_c, space_c, code, hints, intuition, key_idea, step_by_step, tg_msg_id, tg_chan_id FROM solutions WHERE slug=? AND language=?",
                    (slug, k)
                ).fetchone()
                if row:
                    approach, time_c, space_c, code, hints_json, intuition, key_idea, step_by_step, tg_msg_id, tg_chan_id = row
                    self._put_ram(slug, lang, approach, time_c, space_c, code, hints_json, intuition, key_idea, step_by_step)
                    sol = self._ram_solutions[slug][k]
                    if tg_msg_id and tg_chan_id:
                        sol = dict(sol)
                        sol["tg_msg_id"] = tg_msg_id
                        sol["tg_chan_id"] = tg_chan_id
                    return sol
        except Exception as e:
            logger.error(f"[DB] get_solution fallback error: {e}")
        return None


    def get_hints(self, slug: str, lang: str) -> Optional[List[str]]:
        """RAM-first hints lookup. Falls back to SQLite."""
        k = lang.lower()
        if slug in self._ram_hints and k in self._ram_hints[slug]:
            return self._ram_hints[slug][k]
            
        sol = self.get_solution(slug, lang)
        if sol:
            return self._ram_hints[slug][k]
        return None

    def get_description(self, slug: str) -> Optional[str]:
        """RAM-first description lookup. Falls back to SQLite."""
        if slug in self._ram_desc:
            return self._ram_desc[slug]
        with self._conn() as c:
            row = c.execute("SELECT description FROM problems WHERE slug=?", (slug,)).fetchone()
        if row and row[0]:
            self._ram_desc[slug] = row[0]
            return row[0]
        return None

    def is_solution_ready(self, slug: str, lang: str) -> bool:
        return self.get_solution(slug, lang) is not None

    # ── write API (used by generator) ────────────────────────────────────────

    def save_problem(self, slug: str, number: int, title: str, difficulty: str,
                     topic: str, url: str, description: str):
        with self._write_lock:
            with self._conn() as c:
                c.execute(
                    """INSERT OR REPLACE INTO problems
                       (slug, number, title, difficulty, topic, url, description, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (slug, number, title, difficulty, topic, url, description,
                     datetime.utcnow().isoformat())
                )
        self._ram_desc[slug] = description

    def save_solution(self, slug: str, lang: str, approach: str, time_c: str,
                      space_c: str, code: str, hints: List[str],
                      intuition: str = "", key_idea: str = "", step_by_step: str = "",
                      tg_msg_id: int = None, tg_chan_id: int = None,
                      solution_version: str = "1.0", prompt_version: str = "1.0", model_name: str = "unknown"):
        hints_json = json.dumps(hints, ensure_ascii=False)
        with self._write_lock:
            with self._conn() as c:
                c.execute(
                    """INSERT OR REPLACE INTO solutions
                       (slug, language, approach, time_c, space_c, code, hints,
                        intuition, key_idea, step_by_step,
                        tg_msg_id, tg_chan_id, generated_at, solution_version, prompt_version, model_name)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (slug, lang.lower(), approach, time_c, space_c, code,
                     hints_json, intuition, key_idea, step_by_step, tg_msg_id, tg_chan_id,
                     datetime.utcnow().isoformat(), solution_version, prompt_version, model_name)
                )
        # Store full data in RAM for fast bot access
        self._put_ram(slug, lang, approach, time_c, space_c, code, hints_json, intuition, key_idea, step_by_step)


    def wipe_local_text(self):
        """Wipes all local solution text from the database to save space, leaving only hints and Telegram IDs."""
        with self._write_lock:
            with self._conn() as c:
                c.execute(
                    """UPDATE solutions 
                       SET approach='', time_c='', space_c='', code='', intuition='', key_idea='', step_by_step=''"""
                )
        logger.info("[DB] Wiped all local text data from solutions table.")


    def update_tg_ids(self, slug: str, lang: str, tg_msg_id: int, tg_chan_id: int):
        with self._write_lock:
            with self._conn() as c:
                c.execute(
                    "UPDATE solutions SET tg_msg_id=?, tg_chan_id=? WHERE slug=? AND language=?",
                    (tg_msg_id, tg_chan_id, slug, lang.lower())
                )

    # ── queue API ─────────────────────────────────────────────────────────────

    def enqueue(self, slug: str) -> bool:
        """Add a generation job. Returns True if newly added, False if already exists."""
        try:
            with self._write_lock:
                with self._conn() as conn:
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO generator_queue (slug) VALUES (?)",
                        (slug,)
                    )
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[DB] enqueue error: {e}")
            return False

    def get_pending_jobs(self, limit: int = 8) -> List[str]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT slug FROM generator_queue
                   WHERE status IN ('NEW', 'RETRY') AND retries < 3
                   ORDER BY created_at ASC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [r[0] for r in rows]

    def mark_job(self, slug: str, status: str, error_msg: str = None):
        with self._write_lock, self._conn() as c:
            if error_msg:
                c.execute("UPDATE generator_queue SET status=?, error_msg=?, updated_at=datetime('now') WHERE slug=?",
                          (status, error_msg, slug))
            else:
                c.execute("UPDATE generator_queue SET status=?, updated_at=datetime('now') WHERE slug=?",
                          (status, slug))
            c.commit()

    def enqueue_upload(self, slug: str, language: str):
        with self._write_lock, self._conn() as c:
            c.execute('''INSERT OR REPLACE INTO upload_queue 
                         (slug, language, status, error_msg, created_at)
                         VALUES (?, ?, 'PENDING', NULL, datetime('now'))''', 
                         (slug, language))
            c.commit()

    def get_pending_uploads(self, limit: int = 10) -> List[tuple]:
        with self._conn() as c:
            # We want to get uploads that are PENDING or FAILED with retries (for now just PENDING)
            c.execute("BEGIN IMMEDIATE")
            rows = c.execute("SELECT slug, language FROM upload_queue WHERE status='PENDING' LIMIT ?", (limit,)).fetchall()
            for r in rows:
                c.execute("UPDATE upload_queue SET status='UPLOADING' WHERE slug=? AND language=?", (r[0], r[1]))
            c.commit()
            return rows

    def mark_upload(self, slug: str, language: str, status: str, error_msg: str = None):
        with self._write_lock, self._conn() as c:
            c.execute("UPDATE upload_queue SET status=?, error_msg=? WHERE slug=? AND language=?", 
                      (status, error_msg, slug, language))
            c.commit()

    def increment_retry(self, slug: str, error_msg: str = None):
        with self._write_lock:
            with self._conn() as c:
                c.execute(
                    """UPDATE generator_queue
                       SET retries=retries+1, status='RETRY', error_msg=?, updated_at=datetime('now')
                       WHERE slug=?""",
                    (error_msg, slug)
                )

    def save_archive_channel(self, language: str, channel_id: int, channel_name: str):
        with self._write_lock:
            with self._conn() as c:
                c.execute(
                    "INSERT OR REPLACE INTO archive_channels (language, channel_id, channel_name) VALUES (?,?,?)",
                    (language.lower(), channel_id, channel_name)
                )

    def get_archive_channel(self, language: str) -> Optional[int]:
        with self._conn() as c:
            row = c.execute(
                "SELECT channel_id FROM archive_channels WHERE language=?",
                (language.lower(),)
            ).fetchone()
        return row[0] if row else None

    # ── migration ─────────────────────────────────────────────────────────────

    def migrate_from_json(self,
                          solution_cache: str = "database/solution_cache.json",
                          hint_cache:     str = "database/hint_cache.json",
                          problem_cache:  str = "database/problem_cache.json"):
        """
        One-time import of legacy JSON caches into SQLite.
        Safe to call multiple times — uses INSERT OR REPLACE.
        """
        count = 0
        
        # Run ALTER TABLE to add columns if they don't exist (for existing databases)
        try:
            with self._conn() as c:
                c.execute("ALTER TABLE solutions ADD COLUMN intuition TEXT")
                c.execute("ALTER TABLE solutions ADD COLUMN key_idea TEXT")
                c.execute("ALTER TABLE solutions ADD COLUMN step_by_step TEXT")
        except sqlite3.OperationalError:
            pass # Columns already exist

        # 1. solution_cache.json (had embedded hints from old architecture)
        if os.path.exists(solution_cache):
            try:
                with open(solution_cache, encoding="utf-8") as f:
                    data = json.load(f)
                for slug, langs in data.items():
                    for lang, entry in langs.items():
                        self.save_solution(
                            slug=slug, lang=lang,
                            approach = entry.get("approach", ""),
                            time_c   = entry.get("time", "O(?)"),
                            space_c  = entry.get("space", "O(?)"),
                            code     = entry.get("code", ""),
                            hints    = entry.get("hints", []),
                        )
                        count += 1
                logger.info(f"[DB] Migrated {count} entries from solution_cache.json")
            except Exception as e:
                logger.error(f"[DB] solution_cache migration error: {e}")

        # 2. hint_cache.json (separate hints from new architecture)
        if os.path.exists(hint_cache):
            try:
                with open(hint_cache, encoding="utf-8") as f:
                    hdata = json.load(f)
                for slug, langs in hdata.items():
                    for lang, hints in langs.items():
                        # Merge into existing solution row if present
                        sol = self.get_solution(slug, lang)
                        if sol:
                            self.save_solution(
                                slug=slug, lang=lang,
                                approach = sol["approach"],
                                time_c   = sol["time"],
                                space_c  = sol["space"],
                                code     = sol["code"],
                                hints    = hints,
                            )
            except Exception as e:
                logger.error(f"[DB] hint_cache migration error: {e}")

        # 3. problem_cache.json (descriptions)
        if os.path.exists(problem_cache):
            try:
                with open(problem_cache, encoding="utf-8") as f:
                    pdata = json.load(f)
                for slug, desc in pdata.items():
                    self._ram_desc[slug] = desc
                    with self._write_lock:
                        with self._conn() as c:
                            c.execute(
                                "UPDATE problems SET description=? WHERE slug=?",
                                (desc, slug)
                            )
                logger.info(f"[DB] Migrated {len(pdata)} descriptions from problem_cache.json")
            except Exception as e:
                logger.error(f"[DB] problem_cache migration error: {e}")
