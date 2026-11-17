# YouTube Meditation & Shorts Automation Bot

End-to-end automated content pipeline built with **Python**, **FFmpeg**, **Claude API (Anthropic)**, **YouTube Data API v3**, and **Telegram Bot API**. The bot acts as an AI creative director—selecting harmonious audio-visual pairs, stitching multi-clip long-form sleep videos (1–3 hours), slicing promotional YouTube Shorts teasers with on-screen call-to-action overlays, rendering high-CTR thumbnails, and publishing everything on a weekly schedule.

## Key Features
- **AI Creative Director (`Claude API`):** Analyzes available media filenames to match complementary video loops and audio tracks, generating SEO-first descriptions and high-intent tags.
- **Content Funnel (`1 LONG + 3 Linked Shorts`):** Publishes a 1–3 hour sleep/meditation session on Mondays and automatically slices 3 teaser Shorts (Wed/Fri/Sun) from the same track with dynamic text overlays driving viewers to the full version.
- **Multi-Clip Stitching & Fast Rendering (`FFmpeg`):** Normalizes and concatenates up to 3 background video loops into a seamless block, using stream copying (`-c:v copy`) for rapid multi-hour rendering with minimal CPU overhead.
- **CTR-Optimized Thumbnails (`Pillow`):** Applies calming deep blue-violet color grading and high-contrast typography focused on healing frequencies and benefits.
- **3-Day Media Cooldown & Auto-Cleanup:** Tracks asset usage timestamps in `history.json` to prevent consecutive repeats and automatically purges heavy temporary/rendered files after upload.
- **Telegram Alerts & Unattended Execution:** Sends instant Telegram notifications with direct YouTube links, asset summaries, Related Video reminders, or error tracebacks; scheduled via Windows Task Scheduler.

## Tech Stack
- **Language:** Python 3.14
- **AI Integration:** Anthropic Claude API (`claude-sonnet-4-6`)
- **Media Processing:** FFmpeg, Pillow (PIL)
- **APIs & Auth:** YouTube Data API v3, Google OAuth 2.0, Telegram Bot API
- **Automation:** Windows Task Scheduler

## Project Structure
```text
yt-meditation-bot/
├── assets/
│   ├── audio_long/             # Full-length meditation & frequency tracks
│   ├── audio_shorts/           # Standalone short ambient tracks
│   ├── video_loops/            # Source background video loops
│   └── font.ttf                # Custom typography for thumbnails & overlays
├── bot.py                      # Main AI director & automation pipeline
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
└── client_secrets.example.json # Google OAuth template
```

## Setup & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com
   cd YT-bot
   ```

2. **Install dependencies & FFmpeg:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure `ffmpeg` is installed and available in your system `PATH`).*

3. **Configure credentials:**
   - Copy `.env.example` to `.env` and fill in `CLAUDE_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`.
   - Enable **YouTube Data API v3** in Google Cloud Console, download your OAuth 2.0 credentials, and save them as `client_secrets.json` in the project root.

4. **Run the bot:**
   ```bash
   python bot.py
   ```
   *(Optional overrides for testing: `FORCE_TYPE=LONG FORCE_HOURS=2 TEST_MODE=True python bot.py`).*
