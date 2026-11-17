import os
import json
import random
import logging
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from PIL import Image, ImageDraw, ImageFont
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
PRIVACY = os.getenv("PRIVACY", "public")
TEST_MODE = os.getenv("TEST_MODE", "False").lower() == "true"
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
HISTORY_FILE = BASE_DIR / "history.json"
LATEST_LONG_FILE = BASE_DIR / "latest_long.json"
LOG_FILE = BASE_DIR / "bot.log"

OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

if not CLAUDE_API_KEY:
    logging.error("CLAUDE_API_KEY не найден в .env!")
    raise ValueError("Missing CLAUDE_API_KEY")

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

SCHEDULE = {
    0: "LONG",    # Понедельник
    1: "SKIP",    # Вторник
    2: "SHORTS",  # Среда
    3: "SKIP",    # Четверг
    4: "SHORTS",  # Пятница
    5: "SKIP",    # Суббота
    6: "SHORTS"   # Воскресенье
}

def send_telegram(text: str):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        url = "https://api." + f"telegram.org/bot{TG_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": TG_CHAT_ID, "text": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logging.info("Уведомление в Telegram отправлено.")
    except Exception as e:
        logging.warning(f"Ошибка отправки в Telegram: {e}")

def get_available_files(folder: Path, category: str, cooldown_days: int = 3) -> list:
    all_files = list(f.name for f in folder.iterdir() if f.is_file() and not f.name.startswith("."))
    if not all_files:
        raise FileNotFoundError(f"Папка пуста: {folder}")

    history = {}
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = {}

    cat_hist = history.get(category, {})
    if isinstance(cat_hist, list):
        cat_hist = {}

    cutoff = datetime.now() - timedelta(days=cooldown_days)
    available = list()
    for fname in all_files:
        last_used = cat_hist.get(fname)
        if not last_used:
            available.append(fname)
        else:
            try:
                if datetime.fromisoformat(last_used) < cutoff:
                    available.append(fname)
            except ValueError:
                available.append(fname)

    if not available:
        sorted_old = sorted(all_files, key=lambda x: cat_hist.get(x, ""))
        limit = max(2, len(all_files) // 2)
        available = list(sorted_old)[:limit]
    return available

def mark_files_used(category: str, filenames: list):
    history = {}
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = {}

    cat_hist = history.get(category, {})
    if isinstance(cat_hist, list):
        cat_hist = {}

    now_str = datetime.now().isoformat()
    for fname in filenames:
        cat_hist[fname] = now_str

    history[category] = cat_hist
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")

def get_ai_plan(v_type: str, avail_videos: list, avail_audios: list, latest_long: dict = None, forced_hours: int = None) -> dict:
    if v_type == "LONG":
        h = forced_hours if forced_hours else random.choice((1, 2, 3))
        vid_count = min(3, len(avail_videos))
        dur_label = "15 Seconds [TEST]" if TEST_MODE else f"{h} Hours"
        prompt = (
            f"You are a YouTube meditation channel SEO director. "
            f"Available videos: {json.dumps(avail_videos)}. "
            f"Available audios: {json.dumps(avail_audios)}. "
            f"Pick 1 audio and {vid_count} matching videos for a calming sleep/meditation session ({dur_label}). "
            f"CTR & SEO Rules from YouTube Studio: "
            f"1. Thumbnail text MUST be concise (2-3 uppercase words) focusing on benefit + frequency (e.g. 'DEEP SLEEP 432HZ', 'PINEAL GLAND 963HZ'). "
            f"2. The FIRST 2 sentences of 'desc' MUST contain high-volume search queries like '432 Hz sleep music', '528 Hz healing frequency', or 'deep sleep meditation'. "
            f"3. Title MUST accurately state '{dur_label}' (never lie about duration). "
            f"Return ONLY raw JSON without markdown with keys: "
            f'"selected_videos" (list of {vid_count} exact filenames), '
            f'"selected_audio" (1 exact filename), '
            f'"frequency" (e.g. "432Hz"), '
            f'"hours": {h}, '
            f'"title" (under 85 chars with {dur_label}), '
            f'"thumb" (MAX 3 uppercase words, e.g. "DEEP SLEEP 432HZ"), '
            f'"desc" (SEO description starting with search keywords), '
            f'"tags" (list of 12 search-optimized tags), '
            f'"sec": {h * 3600}'
        )
    else:
        sec = random.randint(45, 55)
        ref_title = latest_long.get("title", "Deep Sleep Meditation") if latest_long else "Deep Sleep Meditation"
        ref_freq = latest_long.get("frequency", "432Hz") if latest_long else "432Hz"
        ref_h = latest_long.get("hours", 2) if latest_long else 2
        prompt = (
            f"You are a YouTube Shorts strategist for a meditation channel. "
            f"This Short is a teaser/excerpt promoting our full {ref_h}-hour video: '{ref_title}' ({ref_freq}). "
            f"Available videos: {json.dumps(avail_videos)}. "
            f"Available audios: {json.dumps(avail_audios)}. "
            f"Pick 1 video and 1 audio. "
            f"Return ONLY raw JSON without markdown with keys: "
            f'"selected_videos" (list of 1 exact filename), '
            f'"selected_audio" (1 exact filename), '
            f'"overlay_text" (short 2-line uppercase call-to-action for screen overlay, e.g. "{ref_freq} HEALING TONE\\nFULL {ref_h}H SLEEP VERSION ↓"), '
            f'"title" (intriguing teaser title under 85 chars with #shorts), '
            f'"thumb" (MAX 2 uppercase words), '
            f'"desc" (short teaser description inviting viewers to watch the full {ref_h}-hour version via Related Video link + #shorts), '
            f'"tags" (list of 10 tags), '
            f'"sec": {sec}'
        )

    res = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=list(({"role": "user", "content": prompt},))
    )
    first_block = next(iter(res.content))
    raw = first_block.text.strip().removeprefix("```json").removesuffix("```").strip()
    plan = json.loads(raw, strict=False)

    valid_vids = list(v for v in plan.get("selected_videos", list()) if v in avail_videos)
    if not valid_vids:
        valid_vids = random.sample(avail_videos, min(3 if v_type == "LONG" else 1, len(avail_videos)))
    plan["selected_videos"] = valid_vids

    if plan.get("selected_audio") not in avail_audios:
        plan["selected_audio"] = random.choice(avail_audios)

    return plan

def make_thumb(video_src: Path, text: str) -> Path:
    raw = OUTPUT_DIR / "raw.jpg"
    out = OUTPUT_DIR / "thumb.jpg"
    subprocess.run(list((
        "ffmpeg", "-y", "-i", str(video_src),
        "-frames:v", "1", "-update", "1",
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
        str(raw)
    )), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    base = Image.open(raw).convert("RGBA")
    tint = Image.new("RGBA", (1280, 720), (18, 14, 52, 145))
    img = Image.alpha_composite(base, tint).convert("RGB")

    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(ASSETS_DIR / "font.ttf"), 88)
    clean_text = text.upper().strip()
    b = draw.textbbox((0, 0), clean_text, font=font)
    x0, y0, x1, y1 = b
    w, h_text = x1 - x0, y1 - y0
    x, y = (1280 - w) / 2, (720 - h_text) / 2

    draw.text((x + 4, y + 4), clean_text, font=font, fill=(8, 6, 25))
    draw.text((x, y), clean_text, font=font, fill=(245, 248, 255))
    img.save(out, quality=95)
    return out

def make_shorts_overlay(text: str) -> Path:
    overlay_path = OUTPUT_DIR / "overlay.png"
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(ASSETS_DIR / "font.ttf"), 52)

    lines = list(line.strip() for line in text.upper().split("\n") if line.strip())
    y_start = 1380
    for idx, line in enumerate(lines):
        if idx >= 2:
            break
        b = draw.textbbox((0, 0), line, font=font)
        x0, y0, x1, y1 = b
        w, h_text = x1 - x0, y1 - y0
        x = (1080 - w) / 2
        y = y_start + idx * 75
        draw.rounded_rectangle((x - 28, y - 14, x + w + 28, y + h_text + 18), radius=20, fill=(15, 12, 45, 190))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

    img.save(overlay_path)
    return overlay_path

def make_video(v_type: str, sec: int, video_paths: list, audio_path: Path, overlay_text: str = "") -> Path:
    out = OUTPUT_DIR / "video.mp4"
    concat_list = OUTPUT_DIR / "concat.txt"
    combined_loop = OUTPUT_DIR / "loop_temp.mp4"
    if v_type == "LONG":
        vf = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24,format=yuv420p"
        clip_files = list()
        for idx, v_path in enumerate(video_paths):
            clip_out = OUTPUT_DIR / f"clip_{idx}.mp4"
            subprocess.run(list((
                "ffmpeg", "-y", "-i", str(v_path), "-t", "10", "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-an", str(clip_out)
            )), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            clip_files.append(clip_out)

        concat_list.write_text("\n".join(f"file '{c.as_posix()}'" for c in clip_files), encoding="utf-8")
        subprocess.run(list((
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", str(combined_loop)
        )), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        first_vid = next(iter(video_paths))
        overlay_png = make_shorts_overlay(overlay_text or "DEEP SLEEP FREQUENCY\nFULL VERSION IN LINK ↓")
        subprocess.run(list((
            "ffmpeg", "-y", "-i", str(first_vid), "-i", str(overlay_png),
            "-t", "10",
            "-filter_complex", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24,overlay=0:0,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-an", str(combined_loop)
        )), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cmd = list(("ffmpeg", "-y", "-stream_loop", "-1", "-i", str(combined_loop)))
    if v_type == "SHORTS":
        offset = random.randint(30, 120)
        cmd.extend(("-ss", str(offset)))
    cmd.extend((
        "-stream_loop", "-1", "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", str(sec),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        str(out)
    ))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out

def upload_yt(video: Path, thumb: Path, meta: dict, v_type: str) -> str:
    token = BASE_DIR / "token.json"
    scopes = list(("https://www.googleapis" + ".com/auth/youtube.upload",))
    creds = Credentials.from_authorized_user_file(str(token), scopes) if token.exists() else None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(BASE_DIR / "client_secrets.json"), scopes)
            creds = flow.run_local_server(port=0)
        token.write_text(creds.to_json(), encoding="utf-8")

    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["desc"],
            "tags": meta["tags"],
            "categoryId": "10"
        },
        "status": {
            "privacyStatus": PRIVACY,
            "selfDeclaredMadeForKids": False
        }
    }
    req = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video), chunksize=25 * 1024 * 1024, resumable=True)
    )
    res = None
    while res is None:
        status, res = req.next_chunk()
        if status:
            logging.info(f"Загрузка на YouTube: {int(status.progress() * 100)}%")

    if v_type == "LONG":
        yt.thumbnails().set(videoId=res["id"], media_body=MediaFileUpload(str(thumb))).execute()

    vid_id = res["id"]
    url = "https://" + f"youtu.be/{vid_id}"
    logging.info(f"Видео опубликовано! Ссылка: {url}")
    return url

def cleanup_temp():
    for f in OUTPUT_DIR.iterdir():
        if f.is_file():
            try:
                f.unlink()
            except Exception as e:
                logging.warning(f"Не удалось удалить {f.name}: {e}")

if __name__ == "__main__":
    try:
        v_type = os.getenv("FORCE_TYPE") or SCHEDULE[datetime.now().weekday()]
        if v_type == "SKIP":
            logging.info("Сегодня день отдыха по контент-плану (1 LONG + 3 SHORTS в неделю). Выход.")
            exit(0)

        forced_h = int(os.getenv("FORCE_HOURS")) if os.getenv("FORCE_HOURS") else None
        latest_long = json.loads(LATEST_LONG_FILE.read_text(encoding="utf-8")) if LATEST_LONG_FILE.exists() else None

        if v_type == "SHORTS" and latest_long:
            long_audio_path = ASSETS_DIR / "audio_long" / latest_long["audio"]
            long_vid_path = ASSETS_DIR / "video_loops" / random.choice(latest_long["videos"])
            if long_audio_path.exists() and long_vid_path.exists():
                avail_videos = list((long_vid_path.name,))
                avail_audios = list((long_audio_path.name,))
                audio_dir = ASSETS_DIR / "audio_long"
            else:
                avail_videos = get_available_files(ASSETS_DIR / "video_loops", "video_loops", cooldown_days=3)
                avail_audios = get_available_files(ASSETS_DIR / "audio_shorts", "audio_shorts", cooldown_days=3)
                audio_dir = ASSETS_DIR / "audio_shorts"
        else:
            avail_videos = get_available_files(ASSETS_DIR / "video_loops", "video_loops", cooldown_days=3)
            audio_dir = ASSETS_DIR / ("audio_long" if v_type == "LONG" else "audio_shorts")
            avail_audios = get_available_files(audio_dir, audio_dir.name, cooldown_days=3)

        logging.info(f"1/4 ИИ формирует контент-план ({v_type})...")
        plan = get_ai_plan(v_type, avail_videos, avail_audios, latest_long=latest_long, forced_hours=forced_h)

        chosen_vids = list(ASSETS_DIR / "video_loops" / v for v in plan["selected_videos"])
        chosen_audio = audio_dir / plan["selected_audio"]

        logging.info(f"Выбраны видео: {plan['selected_videos']} | Аудио: {plan['selected_audio']}")
        logging.info(f"Заголовок: {plan['title']}")

        logging.info("2/4 Создание обложки в сине-фиолетовых тонах...")
        first_vid = next(iter(chosen_vids))
        thumb = make_thumb(first_vid, plan["thumb"])

        logging.info("3/4 Рендеринг видео через FFmpeg...")
        duration = 15 if TEST_MODE else plan["sec"]
        video = make_video(v_type, duration, chosen_vids, chosen_audio, plan.get("overlay_text", ""))

        logging.info("4/4 Публикация на YouTube...")
        video_url = upload_yt(video, thumb, plan, v_type)

        if v_type == "LONG":
            LATEST_LONG_FILE.write_text(json.dumps({
                "title": plan["title"],
                "url": video_url,
                "frequency": plan.get("frequency", "432Hz"),
                "hours": plan.get("hours", 2),
                "videos": plan["selected_videos"],
                "audio": plan["selected_audio"]
            }, indent=2, ensure_ascii=False), encoding="utf-8")
            mark_files_used("video_loops", plan["selected_videos"])
            mark_files_used("audio_long", list((plan["selected_audio"],)))

        cleanup_temp()
        logging.info("Цикл автоматизации успешно завершён.")

        if v_type == "LONG":
            send_telegram(
                f"✅ Опубликовано новое ДЛИННОЕ видео ({plan.get('hours', 2)} ч)!\n\n"
                f"🎬 {plan['title']}\n"
                f"🎞 Футажи: {', '.join(plan['selected_videos'])}\n"
                f"🎵 Трек: {plan['selected_audio']}\n"
                f"🔗 {video_url}"
            )
        else:
            ref_info = f"\n👉 Привяжи в YouTube Studio как «Связанное видео»: {latest_long['title']} ({latest_long['url']})" if latest_long else ""
            send_telegram(
                f"✅ Опубликован новый SHORTS-тизер!\n\n"
                f"🎬 {plan['title']}\n"
                f"🔗 {video_url}{ref_info}"
            )
    except Exception as e:
        logging.exception(f"Ошибка при выполнении бота: {e}")
        send_telegram(f"❌ Ошибка при запуске YT-Bot:\n{e}")
        raise
