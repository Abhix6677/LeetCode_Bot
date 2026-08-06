import re

with open("database/db.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update SCHEMA
code = code.replace(
    """        time_c      TEXT,
        space_c     TEXT,
        code        TEXT,
        hints       TEXT,       -- JSON array of 3 strings""",
    """        time_c      TEXT,
        space_c     TEXT,
        code        TEXT,
        hints       TEXT,       -- JSON array of 3 strings
        intuition   TEXT,
        key_idea    TEXT,
        step_by_step TEXT,"""
)

# 2. Update _load_to_ram
code = code.replace(
    """            for slug, lang, approach, time_c, space_c, code, hints_json in c.execute(
                "SELECT slug, language, approach, time_c, space_c, code, hints FROM solutions"
            ):
                self._put_ram(slug, lang, approach, time_c, space_c, code, hints_json)""",
    """            try:
                c.execute("ALTER TABLE solutions ADD COLUMN intuition TEXT")
                c.execute("ALTER TABLE solutions ADD COLUMN key_idea TEXT")
                c.execute("ALTER TABLE solutions ADD COLUMN step_by_step TEXT")
            except:
                pass
            for slug, lang, approach, time_c, space_c, code, hints_json, intuition, key_idea, step_by_step in c.execute(
                "SELECT slug, language, approach, time_c, space_c, code, hints, intuition, key_idea, step_by_step FROM solutions"
            ):
                self._put_ram(slug, lang, approach, time_c, space_c, code, hints_json, intuition, key_idea, step_by_step)"""
)

# 3. Update _put_ram
code = code.replace(
    "def _put_ram(self, slug, lang, approach, time_c, space_c, code, hints_json):",
    "def _put_ram(self, slug, lang, approach, time_c, space_c, code, hints_json, intuition=None, key_idea=None, step_by_step=None):"
)
code = code.replace(
    """        self._ram_solutions[slug][k] = {
            "approach": approach or "",
            "time":     time_c  or "O(?)",
            "space":    space_c or "O(?)",
            "code":     code    or "",
        }""",
    """        self._ram_solutions[slug][k] = {
            "approach": approach or "",
            "time":     time_c  or "O(?)",
            "space":    space_c or "O(?)",
            "code":     code    or "",
            "intuition": intuition or "",
            "key_idea": key_idea or "",
            "step_by_step": step_by_step or ""
        }"""
)

# 4. Update save_solution
code = code.replace(
    """    def save_solution(self, slug: str, lang: str, data: Dict, tg_msg_id: int, tg_chan_id: int):
        with self._write_lock:
            with self._conn() as c:
                c.execute(
                    '''INSERT OR REPLACE INTO solutions (slug, language, approach, time_c, space_c, code, hints, tg_msg_id, tg_chan_id, generated_at)
                       VALUES (?, ?, ?, ?, ?, ?, (SELECT hints FROM solutions WHERE slug=? AND language=?), ?, ?, datetime('now'))''',
                    (slug, lang, data.get("approach",""), data.get("time",""), data.get("space",""), data.get("code",""), slug, lang, tg_msg_id, tg_chan_id)
                )""",
    """    def save_solution(self, slug: str, lang: str, data: Dict, tg_msg_id: int, tg_chan_id: int):
        with self._write_lock:
            with self._conn() as c:
                c.execute(
                    '''INSERT OR REPLACE INTO solutions (slug, language, approach, time_c, space_c, code, hints, intuition, key_idea, step_by_step, tg_msg_id, tg_chan_id, generated_at)
                       VALUES (?, ?, ?, ?, ?, ?, (SELECT hints FROM solutions WHERE slug=? AND language=?), ?, ?, ?, ?, ?, datetime('now'))''',
                    (slug, lang, data.get("approach",""), data.get("time",""), data.get("space",""), data.get("code",""), slug, lang, data.get("intuition",""), data.get("key_idea",""), data.get("step_by_step",""), tg_msg_id, tg_chan_id)
                )"""
)

# 5. Also _put_ram in save_solution memory cache
code = code.replace(
    """            self._put_ram(slug, lang, data.get("approach",""), data.get("time",""), data.get("space",""), data.get("code",""), None)""",
    """            self._put_ram(slug, lang, data.get("approach",""), data.get("time",""), data.get("space",""), data.get("code",""), None, data.get("intuition"), data.get("key_idea"), data.get("step_by_step"))"""
)

with open("database/db.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Patched db.py!")
