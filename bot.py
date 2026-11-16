import os
import json
import random
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from PIL import Image, ImageDraw, ImageFont
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Загрузка переменных окружения из .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
PRIVACY = os.getenv("PRIVACY", "public")
TEST_MODE = os.getenv("TEST_MODE", "False").lower() == "true"

OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
HISTORY_FILE = BASE_DIR / "history.json"
LOG_FILE = BASE_DIR / "bot.log"

OUTPUT_DIR.mkdir(exist_ok=True)

# Настройка логирования в файл и консоль
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

if not CLAUDE_API_KEY:
    logging.error("CLAUDE_API_KEY не найден в .env! Проверьте конфигурацию.")
    raise ValueError("Missing CLAUDE_API_KEY")

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
SCHEDULE = {0: "LONG", 1: "SHORTS", 2: "LONG", 3: "SHORTS", 4: "LONG", 5: "SHORTS", 6: "SHORTS"}


def pick_unique_media(folder: Path, category: str) -> Path:
    """Выбирает медиафайл, избегая недавних повторов."""
    files = [f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")]
    if not files:
        raise FileNotFoundError(f"Папка пуста: {folder}")

    history = {}
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = {}

    used = history.get(category, [])
    available = [f for f in files if f.name not in used]
    if not available:
        used = []
        available = files

    chosen = random.choice(available)
    used.append(chosen.name)
    history[category] = used[-max(1, len(files) - 1):]
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    return chosen


def get_meta(v_type: str) -> dict:
    """Генерирует SEO-метаданные через Claude API."""
    if v_type == "LONG":
        h = random.choice([3, 5, 8])
        freq = random.choice(["528Hz", "432Hz", "396Hz", "852Hz"])
        prompt = (
            f"Return ONLY raw JSON without markdown for YouTube sleep frequency video in English. "
            f"Formula: {{Benefit}} {{Frequency}} Miracle Tone - {h} Hours Deep Sleep. "
            f'Keys: "title" (under 85 chars), "thumb" (MAX 3 uppercase words), '
            f'"desc" (SEO description), "tags" (list of 5 tags), "sec": {h * 3600}'
        )
    else:
        inst = random.choice(["Tibetan Singing Bowls", "Deep Gong Bath", "Crystal Singing Bowls"])
        freq = random.choice(["528Hz", "432Hz", "963Hz"])
        sec = random.randint(45, 58)
        prompt = (
            f"Return ONLY raw JSON without markdown for viral YouTube Shorts ({inst}, {freq}) in English. "
            f"Formula: {{Benefit}} {freq} {inst} - {sec} Seconds #shorts. "
            f'Keys: "title" (under 90 chars, with #shorts), "thumb" (MAX 2 uppercase words), '
            f'"desc" (short description + #shorts), "tags" (list of 5 tags), "sec": {sec}'
        )

    res = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = res.content[0].text.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(raw)


def make_thumb(video_src: Path, text: str) -> Path:
    """Извлекает кадр и рендерит обложку с затемнением и заголовком."""
    raw = OUTPUT_DIR / "raw.jpg"
    out = OUTPUT_DIR / "thumb.jpg"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video_src),
        "-frames:v", "1", "-update", "1",
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
        str(raw)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    img = Image.alpha_composite(
        Image.open(raw).convert("RGBA"),
        Image.new("RGBA", (1280, 720), (0, 0, 0, 110))
    ).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(ASSETS_DIR / "font.ttf"), 76)
    b = draw.textbbox((0, 0), text.upper(), font=font)
    w, h_text = b[2] - b[0], b[3] - b[1]
    draw.text(((1280 - w) / 2, (720 - h_text) / 2), text.upper(), font=font, fill=(255, 255, 255))
    img.save(out, quality=95)
    return out


def make_video(v_type: str, sec: int, chosen_video: Path) -> Path:
    """Собирает итоговый видеоролик через FFmpeg без повторного перекодирования длинного потока."""
    folder = "audio_long" if v_type == "LONG" else "audio_shorts"
    audio = pick_unique_media(ASSETS_DIR / folder, folder)
    logging.info(f"Выбран аудиотрек: {audio.name}")

    loop_vid = OUTPUT_DIR / "loop_temp.mp4"
    out = OUTPUT_DIR / "video.mp4"
    vf = (
        "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24"
        if v_type == "LONG"
        else "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24"
    )

    subprocess.run([
        "ffmpeg", "-y", "-i", str(chosen_video), "-t", "10", "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-an", str(loop_vid)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(loop_vid),
        "-stream_loop", "-1", "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", str(sec),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        str(out)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def upload_yt(video: Path, thumb: Path, meta: dict, v_type: str) -> str:
    """Авторизуется в YouTube Data API v3 и загружает видео с обложкой."""
    token = BASE_DIR / "token.json"
    scopes = ["https://www.googleapis.com" + "/auth/youtube.upload"]
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
        media_body=MediaFileUpload(str(video), chunksize=10 * 1024 * 1024, resumable=True)
    )
    res = None
    while res is None:
        status, res = req.next_chunk()
        if status:
            logging.info(f"Прогресс загрузки на YouTube: {int(status.progress() * 100)}%")

    if v_type == "LONG":
        yt.thumbnails().set(videoId=res["id"], media_body=MediaFileUpload(str(thumb))).execute()

    url = f"https://youtu.be{res['id']}"
    logging.info(f"Видео успешно опубликовано! Ссылка: {url}")
    return url


def cleanup_temp():
    """Удаляет временные файлы сборки после публикации."""
    for temp_name in ["loop_temp.mp4", "raw.jpg"]:
        temp_file = OUTPUT_DIR / temp_name
        if temp_file.exists():
            temp_file.unlink()


if __name__ == "__main__":
    try:
        v_type = SCHEDULE[datetime.now().weekday()]
        chosen_video = pick_unique_media(ASSETS_DIR / "video_loops", "video_loops")
        logging.info(f"Запуск генерации ({v_type}). Видео-футаж: {chosen_video.name}")

        logging.info("1/4 Генерация SEO-метаданных через Claude API...")
        meta = get_meta(v_type)
        logging.info(f"Заголовок: {meta['title']}")

        logging.info("2/4 Создание обложки...")
        thumb = make_thumb(chosen_video, meta["thumb"])

        logging.info("3/4 Рендеринг видео через FFmpeg...")
        duration = 15 if TEST_MODE else meta["sec"]
        video = make_video(v_type, duration, chosen_video)

        logging.info("4/4 Публикация на YouTube...")
        upload_yt(video, thumb, meta, v_type)

        cleanup_temp()
        logging.info("Цикл автоматизации успешно завершён.")
    except Exception as e:
        logging.exception(f"Ошибка при выполнении бота: {e}")
        raise
