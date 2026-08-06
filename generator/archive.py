"""
generator/archive.py
─────────────────────
Telegram User Account Archive Manager using Telethon.

• Creates one private channel per language (Solutions - Java, etc.)
• Posts formatted solution messages.
• Returns the message_id for fast retrieval later.
• Gracefully disabled when TG_API_ID / TG_API_HASH are not set.

Environment variables required:
    TG_API_ID    – from https://my.telegram.org/apps
    TG_API_HASH  – from https://my.telegram.org/apps
    TG_PHONE     – phone number for OTP login (e.g. +911234567890)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

LANGUAGES = ["Java", "Python", "C++", "C", "JavaScript"]
CHANNEL_NAMES = {
    "java":       "Solutions - Java",
    "python":     "Solutions - Python",
    "c++":        "Solutions - C++",
    "c":          "Solutions - C",
    "javascript": "Solutions - JavaScript",
}


import queue
import concurrent.futures
import threading
import asyncio

class ArchiveManager:
    """
    Wraps Telethon for archive operations using a dedicated background thread.
    """
    def __init__(self, db, session_file: str = "generator2.session"):
        self._db = db
        self._session_file = session_file
        self._client = None
        self._enabled = False

        self._api_id = os.getenv("TG_API_ID")
        self._api_hash = os.getenv("TG_API_HASH")

        if not self._api_id or not self._api_hash:
            logger.warning("[Archive] TG credentials not set. Disabled.")
            return

        self._enabled = True
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._upload_loop, name="ArchiveThread", daemon=True)
        self._thread.start()

    def _upload_loop(self):
        """Dedicated thread for all Telethon operations."""
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        from telethon.sync import TelegramClient

        try:
            self._client = TelegramClient(self._session_file, int(self._api_id), self._api_hash)
            self._client.session.save_entities = False
            self._client.connect()
            logger.info("[Archive] Telethon connected in dedicated thread.")
        except Exception as e:
            logger.error(f"[Archive] Failed to connect: {e}")
            return

        while True:
            item = self._queue.get()
            if item is None:
                break
            
            action, args, fut = item
            try:
                if action == "login":
                    phone = args[0]
                    self._client.start(phone=lambda: phone or input("Phone number: "))
                    fut.set_result(True)
                elif action == "ensure_channels":
                    from telethon.tl.functions.channels import CreateChannelRequest
                    for lang_key, name in CHANNEL_NAMES.items():
                        if not self._db.get_archive_channel(lang_key):
                            result = self._client(CreateChannelRequest(title=name, about="LeetCode Solution Archive", megagroup=False))
                            self._db.save_archive_channel(lang_key, result.chats[0].id, name)
                    fut.set_result(True)
                elif action == "post":
                    lang, text = args
                    chan_id = self._db.get_archive_channel(lang.lower())
                    if chan_id:
                        msg = self._client.send_message(chan_id, text)
                        logger.info(f"[Archive] Posted to {lang} channel, msg_id={msg.id}")
                        fut.set_result(msg.id)
                    else:
                        fut.set_result(None)
            except Exception as e:
                logger.error(f"[Archive] action {action} failed: {e}")
                fut.set_result(None)

    def _dispatch(self, action, *args):
        if not self._enabled: return None
        fut = concurrent.futures.Future()
        self._queue.put((action, args, fut))
        return fut.result(timeout=120)

    def connect(self):
        pass # Handled by thread

    def login(self):
        phone = os.getenv("TG_PHONE", "")
        self._dispatch("login", phone)

    def ensure_channels(self):
        self._dispatch("ensure_channels")

    def post_solution(self, lang: str, text: str) -> Optional[int]:
        return self._dispatch("post", lang, text)

    def disconnect(self):
        pass
