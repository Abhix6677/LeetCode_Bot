#!/usr/bin/env python3

import os
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

print("Starting LeetCode Daily Task Bot...")
print(f"Bot Token: {TELEGRAM_BOT_TOKEN[:5]}...{TELEGRAM_BOT_TOKEN[-5:]}")

# Create and run the bot
bot = LeetCodeBot(TELEGRAM_BOT_TOKEN, admin_user_id=int(ADMIN_USER_ID) if ADMIN_USER_ID else None)
bot.run()