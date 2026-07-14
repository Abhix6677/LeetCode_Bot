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

## Setup Instructions

### Prerequisites

- Python 3.11+
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Local Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/LeetCode-Bot.git
cd LeetCode-Bot
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

4. Run the bot:

```bash
python main.py
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

## Deploy to Railway (Free)

Railway offers a free tier that can host your bot 24/7.

### Steps:

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/LeetCode-Bot.git
   git push -u origin main
   ```

2. **Go to [Railway.app](https://railway.app)** and sign up with your GitHub account.

3. **Create a new project:**
   - Click "New Project"
   - Select "Deploy from GitHub Repo"
   - Choose your LeetCode-Bot repository

4. **Add environment variable:**
   - In your Railway project, go to "Variables"
   - Add: `TELEGRAM_BOT_TOKEN` = `your_bot_token_here`

5. **Railway will auto-detect** the `Procfile` and start running your bot.

6. **Enable the web service** (required for Railway):
   - Railway needs a web process to stay alive
   - The bot uses polling, so no webhook setup needed

### Alternative: Deploy to Render (Free)

1. Go to [Render.com](https://render.com) and sign up
2. Create a "Background Worker" (not Web Service)
3. Connect your GitHub repo
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python main.py`
6. Add environment variable: `TELEGRAM_BOT_TOKEN`

## License

MIT License
