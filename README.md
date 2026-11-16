# YouTube Meditation & Shorts Automation Bot

Automated end-to-end content pipeline built with **Python**, **FFmpeg**, **Claude API (Anthropic)**, and **YouTube Data API v3**. The bot generates either long-form sleep/meditation videos (3–8 hours) or vertical YouTube Shorts based on a weekly schedule, renders custom thumbnails, and publishes them automatically.

## Key Features
- **AI-Powered SEO Metadata:** Uses Claude API to generate high-converting titles, descriptions, tags, and thumbnail overlays tailored to video format (`LONG` vs `SHORTS`).
- **Fast Video Rendering (`FFmpeg`):** Creates a short 10-second encoded video loop and concatenates multi-hour tracks using stream copying (`-c:v copy`) for minimal CPU load and rapid processing.
- **Automated Thumbnail Generation (`Pillow`):** Extracts a frame from the source footage, applies dynamic dark overlay contrast, and centers custom typography.
- **Smart Media Rotation:** Tracks previously used audio and video assets in `history.json` to prevent consecutive duplicates.
- **Production OAuth 2.0 & Scheduling:** Supports automatic token refresh (`google-auth`) and unattended daily execution via Windows Task Scheduler.
- **Structured Logging & Cleanup:** Logs execution stages and errors to `bot.log` and removes temporary render files after upload.

## Tech Stack
- **Language:** Python 3.14
- **AI Integration:** Anthropic Claude API (`claude-sonnet-4-6`)
- **Media Processing:** FFmpeg, Pillow (PIL)
- **APIs & Auth:** YouTube Data API v3, Google OAuth 2.0
- **Automation:** Windows Task Scheduler

## Project Structure
```text
yt-meditation-bot/
├── assets/
│   ├── audio_long/        # Background tracks for 3-8h videos
│   ├── audio_shorts/      # Short ambient tracks (45-58s)
│   ├── video_loops/       # Source background video loops
│   └── font.ttf           # Custom font for thumbnails
├── bot.py                 # Main automation pipeline
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
└── client_secrets.example.json
```

## Setup & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com
   cd YT-Bot
   ```

2. **Install dependencies & FFmpeg:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure `ffmpeg` is installed and added to your system `PATH`).*

3. **Configure credentials:**
   - Copy `.env.example` to `.env` and add your `CLAUDE_API_KEY`.
   - Enable **YouTube Data API v3** in Google Cloud Console, download your OAuth credentials, and save them as `client_secrets.json` in the project root.

4. **Run the bot:**
   ```bash
   python bot.py
   ```
   *(On the first run, complete the Google OAuth consent flow in your browser to generate `token.json` for future unattended runs).*
