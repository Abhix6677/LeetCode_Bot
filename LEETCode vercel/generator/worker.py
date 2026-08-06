import logging
import os
import sqlite3
import time
import itertools
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

LANGUAGES = ["Java", "Python", "C++", "C", "JavaScript"]

class GeneratorWorker:
    def __init__(self, db, ai_provider, archive, poll_interval: float = 0.5):
        self._db = db
        self._archive = archive
        self._interval = poll_interval

        # Build multi-provider list: primary + extra models on same base URL
        base_url = os.getenv("AI_BASE_URL", "http://localhost:20128/v1")
        from generator.ai_providers.openai_compatible import OpenAICompatibleProvider
        
        keys = [
            os.getenv("AI_API_KEY_1"),
            os.getenv("AI_API_KEY_2"),
            os.getenv("AI_API_KEY_3"),
            os.getenv("AI_API_KEY_4"),
            os.getenv("AI_API_KEY_5"),
            os.getenv("AI_API_KEY")
        ]
        keys = [k for k in keys if k]
        
        models_env = os.getenv("AI_MODELS", "mistral/mistral-large-latest")
        models = [m.strip() for m in models_env.split(",") if m.strip()]
        
        self._providers = []
        for i, m in enumerate(models):
            key = keys[i % len(keys)] if keys else ""
            self._providers.append(OpenAICompatibleProvider(base_url, key, m, name=m.split("/")[-1]))

        self._provider_cycle = itertools.cycle(self._providers)
        self._provider_lock  = threading.Lock()

        # Reduced to 3 (1 per model) to respect strict rate limits on free AI proxies.
        worker_count = int(os.getenv("WORKER_COUNT", "3"))
        self._pool = ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="gen")
        logger.info(f"[Worker] Multi-provider mode: {[p.name for p in self._providers]} | workers={worker_count}")

    def _next_provider(self):
        with self._provider_lock:
            return next(self._provider_cycle)

    def _validate_solution(self, solution: Dict) -> bool:
        """Strict validation of the AI JSON output."""
        if not solution or not isinstance(solution, dict):
            return False
            
        required_fields = [
            "problem_summary", "intuition", "key_idea", "step_by_step",
            "time_complexity", "space_complexity", "hints",
            "java", "python", "cpp", "c", "javascript"
        ]
        
        for field in required_fields:
            if field not in solution:
                solution[field] = "" # fallback
                
            val = solution[field]
            if field == "hints":
                if not isinstance(val, list) or len(val) != 3:
                    # just supply empty hints instead of failing
                    solution["hints"] = ["", "", ""]
            elif field in ["java", "python", "cpp", "c", "javascript"]:
                if not isinstance(val, str) or not val.strip():
                    logger.error(f"Validation failed: Code for {field} must be a non-empty string")
                    return False
            else:
                if not isinstance(val, str):
                    solution[field] = str(val) if val is not None else ""
                    
        return True

    def _process_job(self, slug: str) -> bool:
        """
        Process a single generation job containing all languages.
        """
        logger.info(f"[Worker] START slug={slug}")
        t_start = time.perf_counter()
        
        self._db.mark_job(slug, "FETCHING")
        try:
            # 1. Fetch description
            description = self._db.get_description(slug)
            if not description:
                from generator.graphql_client import fetch_description
                description = fetch_description(slug) or ""
                if description:
                    self._db.save_problem(
                        slug=slug, number=0, title=slug, difficulty="Unknown",
                        topic="General", url=f"https://leetcode.com/problems/{slug}",
                        description=description,
                    )
            
            # Resolve metadata
            title = slug
            difficulty = "Medium"
            with sqlite3.connect(self._db.db_path) as c:
                row = c.execute("SELECT title, difficulty FROM problems WHERE slug=?", (slug,)).fetchone()
                if row:
                    title, difficulty = row
            
            # 2. Generate with round-robin + fallback across all providers
            self._db.mark_job(slug, "GENERATING")
            solution = None
            used_provider = None
            for attempt in range(len(self._providers)):
                provider = self._next_provider()
                solution = provider.generate_solution(
                    slug=slug, title=title, difficulty=difficulty, description=description
                )
                if solution:
                    used_provider = provider
                    break
                logger.warning(f"[Worker] Provider {provider.name} failed for {slug}, trying next...")

            # 3. Validate
            self._db.mark_job(slug, "VALIDATING")
            if not self._validate_solution(solution):
                logger.warning(f"[Worker] Validation failed for {slug}")
                self._db.increment_retry(slug, "Validation failed")
                return False

            # 4. Save to SQLite (Split data)
            self._db.mark_job(slug, "SAVING")
            
            # Format content before saving
            approach = self._premium_format(solution.get("problem_summary", ""))
            intuition = self._premium_format(solution.get("intuition", ""))
            key_idea = self._premium_format(solution.get("key_idea", ""))
            step_by_step = self._premium_format(solution.get("step_by_step", ""))
            
            time_c = solution.get("time_complexity", "O(?)")
            space_c = solution.get("space_complexity", "O(?)")
            hints = solution.get("hints", [])
            model_name = getattr(used_provider, "name", "unknown") if used_provider else "unknown"
            
            lang_map = {
                "java": "Java",
                "python": "Python",
                "cpp": "C++",
                "c": "C",
                "javascript": "JavaScript"
            }
            
            for json_key, db_lang in lang_map.items():
                code = solution.get(json_key, "")
                
                # 5. Direct Upload to Telegram Archive
                formatted_text = self._format_archive_message(
                    title=title, lang=db_lang, approach=approach, time_c=time_c, space_c=space_c,
                    code=code, hints=hints, intuition=intuition, key_idea=key_idea, step_by_step=step_by_step
                )
                msg_id = self._archive.post_solution(db_lang, formatted_text)
                
                # 6. Save to SQLite with msg_id
                self._db.save_solution(
                    slug=slug, lang=db_lang,
                    approach=approach, time_c=time_c, space_c=space_c, code=code, hints=hints,
                    intuition=intuition, key_idea=key_idea, step_by_step=step_by_step,
                    tg_msg_id=msg_id, tg_chan_id=None,
                    solution_version="2.0", prompt_version="2.0", model_name=model_name
                )
            
            self._db.mark_job(slug, "COMPLETED")
            
            elapsed = (time.perf_counter() - t_start) * 1000
            logger.info(f"[Worker] Generated and queued {slug} in {elapsed:.0f}ms")
            
            return True

        except Exception as e:
            logger.error(f"[Worker] ERROR slug={slug}: {e}", exc_info=True)
            self._db.increment_retry(slug, str(e))
            return False

    @staticmethod
            
    def _premium_format(text: str) -> str:
        """
        Content Formatter:
        - Break long paragraphs
        - Maximum 2 lines per paragraph
        - Add blank lines
        - Format bullets
        """
        if not text:
            return ""
        # Simply split sentences that end in period and space
        sentences = text.replace(". ", ".\\n").split("\\n")
        formatted_blocks = []
        current_block = []
        for s in sentences:
            s = s.strip()
            if not s: continue
            if s.startswith("- ") or s.startswith("* "):
                if current_block:
                    formatted_blocks.append(" ".join(current_block))
                    current_block = []
                formatted_blocks.append("• " + s[2:])
            else:
                current_block.append(s)
                if len(current_block) >= 2:
                    formatted_blocks.append(" ".join(current_block))
                    current_block = []
        if current_block:
            formatted_blocks.append(" ".join(current_block))
            
        return "\\n\\n".join(formatted_blocks)

    @staticmethod
    def _format_archive_message(title: str, lang: str, approach: str, time_c: str, space_c: str, code: str, hints: list, intuition: str = "", key_idea: str = "", step_by_step: str = "") -> str:
        lines = [
            f"💡 **{title} ({lang})**",
            "",
            "📖 **Intuition**",
            intuition or approach,
            "",
            "🎯 **Key Idea**",
            key_idea or approach,
            "",
            "📋 **Step-by-Step**",
            step_by_step,
            "",
            "⚡ **Complexity**",
            f"• Time: `{time_c}`  |  • Space: `{space_c}`",
            "",
            f"💻 **Code ({lang})**",
            f"```{lang.lower()}",
            code,
            "```",
            "",
            "💡 **Hints**",
        ]
        for i, h in enumerate(hints, 1):
            if h.strip():
                lines.append(f"  {i}. {h}")
        return "\\n".join(lines)

    def run_forever(self):
        logger.info("[Worker] Generator started. Polling for jobs (LOCAL-ONLY mode — no Telegram)...")
        while True:
            try:
                jobs = self._db.get_pending_jobs(limit=int(os.getenv("WORKER_COUNT", "50")))
                if jobs:
                    futures = {
                        self._pool.submit(self._process_job, slug): slug
                        for slug in jobs
                    }
                    for fut in as_completed(futures, timeout=300):
                        slug = futures[fut]
                        try:
                            res = fut.result()
                            if res and isinstance(res, tuple) and res[0] is True:
                                _, s, _uploads = res
                                # Phase 1: Save locally only, NO Telegram upload
                                # Run bulk_upload_to_telegram.py after all jobs complete
                                self._db.mark_job(s, "COMPLETED")
                                logger.info(f"[Worker] COMPLETED (local) {s}")
                        except Exception as e:
                            logger.error(f"[Worker] future error slug={slug}: {e}")
                            self._db.increment_retry(slug, str(e))
            except Exception as e:
                logger.error(f"[Worker] poll error: {e}")
            time.sleep(self._interval)

    def enqueue_all_languages(self, slug: str):
        """Deprecated: Now handled by just enqueueing the slug."""
        if self._db.enqueue(slug):
            logger.info(f"[Worker] Queued {slug}")
