import logging
import time
from typing import Dict, List, Optional

from database.db import get_db

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SolutionProvider v2.0
# Reads ONLY from the central SQLite Database (which hits RAM first).
# Zero AI runtime generation. Zero blocking.
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGES = ["Java", "Python", "C++", "C", "JavaScript"]

class SolutionProvider:
    def __init__(self):
        self.db = get_db()
        logger.info("[SolutionProvider] ready (SQLite mode, no runtime AI).")

    # ── public API ───────────────────────────────────────────────────────────

    def get_hint(self, question: Dict, language: str, hint_index: int) -> Optional[str]:
        slug = question.get("titleSlug", "")
        t0 = time.perf_counter()

        hints = self.db.get_hints(slug, language)
        
        elapsed = (time.perf_counter() - t0) * 1000

        if hints:
            idx = max(0, min(hint_index - 1, len(hints) - 1))
            logger.info(f"[Hint] HIT {elapsed:.1f}ms | {slug}/{language} idx={idx+1}")
            return hints[idx]
            
        logger.info(f"[Hint] MISS {elapsed:.1f}ms | {slug}/{language} -> Enqueueing job")
        self.db.enqueue(slug)
        return None

    def get_solution(self, question: Dict, language: str) -> Optional[Dict]:
        slug = question.get("titleSlug", "")
        t0 = time.perf_counter()

        data = self.db.get_solution(slug, language)
        
        elapsed = (time.perf_counter() - t0) * 1000

        if data:
            logger.info(f"[Solution] HIT {elapsed:.1f}ms | {slug}/{language}")
            return data
            
        logger.info(f"[Solution] MISS {elapsed:.1f}ms | {slug}/{language} -> Enqueueing job")
        self.db.enqueue(slug)
        return None

    # Internal helper for telegram bot to know if it should show loading string
    def _get_solution_cached(self, slug: str, lang: str) -> Optional[Dict]:
        return self.db.get_solution(slug, lang)
