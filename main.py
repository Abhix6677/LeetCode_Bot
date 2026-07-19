#!/usr/bin/env python3

import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from bot.telegram_bot import LeetCodeBot

# Load environment variables
load_dotenv()

# Get Telegram bot token from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

if not TELEGRAM_BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN not found in .env file")
    exit(1)

# ── Health-check HTTP server (for Render Web Service compatibility) ──────────
PORT = int(os.getenv("PORT", "8080"))

class HealthHandler(BaseHTTPRequestHandler):
    """Minimal health-check endpoint — responds 200 OK on GET / and HEAD /."""

    def _respond(self, *, include_body: bool):
        """Send 200 OK with headers. Writes body only if include_body is True."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        if include_body:
            self.wfile.write(b"OK")

    def do_GET(self):
        self._respond(include_body=True)

    def do_HEAD(self):
        self._respond(include_body=False)

    def log_message(self, format, *args):
        """Suppress default request logging to stderr."""
        pass

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"Health server listening on port {PORT}")
    server.serve_forever()

# Start the health server in a background daemon thread
health_thread = threading.Thread(target=start_health_server, daemon=True)
health_thread.start()
print(f"Health server thread started on port {PORT}")

# ── Data directory ──────────────────────────────────────────────────────────
DATA_DIR = "database"
os.makedirs(DATA_DIR, exist_ok=True)
print(f"Data directory '{DATA_DIR}/' ready")

print("Starting LeetCode Daily Task Bot...")
print(f"Bot Token: {TELEGRAM_BOT_TOKEN[:5]}...{TELEGRAM_BOT_TOKEN[-5:]}")

# ── Create and run the bot ──────────────────────────────────────────────────
bot = LeetCodeBot(TELEGRAM_BOT_TOKEN, admin_user_id=int(ADMIN_USER_ID) if ADMIN_USER_ID else None)
bot.run()