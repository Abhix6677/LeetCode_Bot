import logging
import time
import threading
from typing import Optional
from generator.worker import GeneratorWorker

logger = logging.getLogger(__name__)

class TelegramUploader:
    def __init__(self, db, archive, poll_interval: float = 2.0):
        self._db = db
        self._archive = archive
        self._interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="UploaderThread", daemon=True)
        self._thread.start()
        logger.info("[Uploader] Telegram Uploader Thread started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        self._archive.connect()
        while self._running:
            try:
                uploads = self._db.get_pending_uploads(limit=5)
                if not uploads:
                    time.sleep(self._interval)
                    continue

                for slug, language in uploads:
                    self._process_upload(slug, language)
                    time.sleep(0.5)  # slight delay to prevent Telegram rate limits
            except Exception as e:
                logger.error(f"[Uploader] Loop error: {e}")
                time.sleep(5)

    def _process_upload(self, slug: str, language: str):
        try:
            # 1. Fetch solution from DB
            row = self._db._conn().execute(
                "SELECT p.title, s.approach, s.time_c, s.space_c, s.code, s.hints, s.intuition, s.key_idea, s.step_by_step "
                "FROM solutions s LEFT JOIN problems p ON s.slug = p.slug "
                "WHERE s.slug=? AND s.language=?", 
                (slug, language.lower())
            ).fetchone()

            if not row:
                self._db.mark_upload(slug, language, "FAILED", "Solution not found in DB")
                return

            title, approach, time_c, space_c, code, hints_str, intuition, key_idea, step_by_step = row
            if not title:
                title = slug.replace("-", " ").title()
            
            # parse hints
            import json
            hints = []
            if hints_str:
                try:
                    hints = json.loads(hints_str)
                except:
                    pass

            # 2. Format message
            formatted_text = GeneratorWorker._format_archive_message(
                title=title, lang=language, approach=approach, time_c=time_c, space_c=space_c,
                code=code, hints=hints, intuition=intuition, key_idea=key_idea, step_by_step=step_by_step
            )

            # 3. Post to Telegram
            msg_id = self._archive.post_solution(language, formatted_text)
            
            if msg_id:
                # 4. Save msg_id to solutions
                with self._db._write_lock, self._db._conn() as c:
                    c.execute("UPDATE solutions SET tg_msg_id=? WHERE slug=? AND language=?", (msg_id, slug, language))
                    c.commit()
                
                # Mark upload queue COMPLETED
                self._db.mark_upload(slug, language, "COMPLETED")
                logger.info(f"[Uploader] Uploaded {slug} ({language}) -> msg_id={msg_id}")
            else:
                self._db.mark_upload(slug, language, "FAILED", "Telegram returned None msg_id")

        except Exception as e:
            logger.error(f"[Uploader] Error uploading {slug} ({language}): {e}")
            self._db.mark_upload(slug, language, "FAILED", str(e))
