# LeetCode Daily Task Bot

A Telegram bot that fetches LeetCode questions directly from LeetCode's API and helps you practice daily with progress tracking.

## Features

- **Daily Task** — 1 random LeetCode question per day, persists for 24 hours (resets at 11:59 PM)
- **Topic Questions** — Select a topic and difficulty to practice specific areas
- **Progress Tracking** — Tracks completed questions, streaks, and total solved
- **Inline Buttons** — Next Question and Completed buttons appear directly below messages
- **Per-User Storage** — Each user has isolated progress (no shared data)
- **Hamburger Menu** — Quick access to /start, /today, /progress commands
- **Live API** — Fetches problems directly from LeetCode's REST API (3991+ problems)

## Project Structure

```
LeetCode Bot/
├── main.py                 # Entry point
├── bot/
│   └── telegram_bot.py     # Bot handlers and UI logic
├── database/
│   └── user_{id}.json      # Per-user progress (auto-created, not in git)
├── scheduler/
│   └── task_generator.py   # Task generation and progress management
├── utils/
│   └── leetcode_api.py     # LeetCode REST API wrapper
├── .env                    # Bot token (not in git)
├── .gitignore              # Git ignore rules
├── Procfile                # Deployment config
├── requirements.txt        # Python dependencies
└── runtime.txt             # Python version
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and main menu |
| `/today` | View today's LeetCode task |
| `/progress` | View your completed questions and streak |

## Bot Buttons

| Button | Description |
|--------|-------------|
| 📋 Today's Tasks | Get today's random LeetCode question |
| 📊 My Progress | View completed questions and streak |
| 📚 Topic Questions | Practice by topic and difficulty |
| 📖 Help | Show help menu |
| 🔄 Next Question | Get another question (topic mode) |
| ✅ Completed | Mark current question as done |

