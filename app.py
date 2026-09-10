from flask import Flask, jsonify, request, send_file, send_from_directory
import glob
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "downloads")
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
DB_PATH = os.path.join(BASE_DIR, "downloader.db")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder=None)
MAX_RETRIES = 5
STALE_SECONDS = 12
MAX_WORKERS = 2
JOBS = {}
JOBS_LOCK = threading.RLock()
CANCEL_EVENTS = {}
EXECUTOR = ThreadPoolExecutor(max_workers=MAX_WORKERS)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        filename TEXT,
        path TEXT,
        status TEXT NOT NULL,
        media_type TEXT DEFAULT 'video',
        quality TEXT,
        size INTEGER DEFAULT 0,
        created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS presets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        settings TEXT NOT NULL,
        created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    defaults = {
        "download_path": DOWNLOAD_FOLDER,
        "theme": "dark",
        "language": "fa",
        "concurrent_downloads": "2",
        "speed_limit": "0",
        "notifications": "true",
        "clipboard_monitor": "false",
    }
    for key, value in defaults.items():
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))
    conn.commit()
    conn.close()


def set_job(job_id, **values):
    with JOBS_LOCK:
        job = JOBS.setdefault(job_id, {})
        job.update(values)
        job["updated_at"] = time.time()


def get_job(job_id):
    with JOBS_LOCK:
        return dict(JOBS.get(job_id, {}))


def format_bytes(value):
    if not value:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024


def format_eta(seconds):
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def human_error(error):
    text = str(error or "").strip()
    lower = text.lower()
    if any(x in lower for x in ("failed to resolve", "getaddrinfo failed", "name or service not known", "dns")):
        return "اتصال DNS برقرار نشد. اینترنت، DNS یا VPN/Proxy را بررسی کنید."
    if any(x in lower for x in ("timed out", "timeout", "connection reset", "connection aborted", "network is unreachable")):
        return "ارتباط با سرور ناپایدار شد. برنامه تلاش مجدد خودکار انجام می‌دهد."
    if "ffmpeg" in lower and ("not found" in lower or "not installed" in lower):
        return "FFmpeg نصب نیست و برای تبدیل یا ادغام صدا و تصویر لازم است."
    if "requested format is not available" in lower:
        return "کیفیت انتخاب‌شده در دسترس نیست. کیفیت دیگری را امتحان کنید."
    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return clean or "دانلود با خطای ناشناخته مواجه شد."


def info_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "retries": MAX_RETRIES,
        "extractor_retries": 3,
        "socket_timeout": 20,
    }


def extract(url, playlist=False):
    opts = info_options()
    opts["noplaylist"] = not playlist
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def clean_title(title):
    title = re.sub(r"[\\/:*?\"<>|]", "_", title or "video")
    title = re.sub(r"\s+", " ", title).strip(" .")
    return title[:180] or "video"


def get_settings():
    conn = db()
    rows = conn.execute("SELECT key,value FROM settings").fetchall()
    conn.close()
    result = {r["key"]: r["value"] for r in rows}
    result["concurrent_downloads"] = int(result.get("concurrent_downloads", 2))
    result["speed_limit"] = int(result.get("speed_limit", 0))
    result["notifications"] = result.get("notifications") == "true"
    result["clipboard_monitor"] = result.get("clipboard_monitor") == "true"
    return result


@app.get("/api/health")
def health():
    return jsonify({"success": True, "yt_dlp": getattr(yt_dlp, "version", "unknown"), "ffmpeg": bool(shutil.which("ffmpeg")), "disk_free": shutil.disk_usage(BASE_DIR).free})


@app.post("/api/info")
def api_info():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    if not url:
        return jsonify({"success": False, "error": "لینک را وارد کنید."}), 400
    try:
        info = extract(url, playlist=False)
        formats = info.get("formats") or []
        heights = sorted({int(f["height"]) for f in formats if f.get("height") and f.get("vcodec") != "none"}, reverse=True)
        return jsonify({"success": True, "kind": "playlist" if info.get("_type") == "playlist" else "video", "title": info.get("title"), "thumbnail": info.get("thumbnail"), "duration": info.get("duration"), "uploader": info.get("uploader"), "webpage_url": info.get("webpage_url", url), "qualities": [{"value": str(h), "resolution": f"{h}p", "label": "4K" if h >= 2160 else "2K" if h >= 1440 else "Full HD" if h >= 1080 else "HD" if h >= 720 else "SD"} for h in heights]})
    except Exception as exc:
        return jsonify({"success": False, "error": human_error(exc)}), 500


@app.post("/api/playlist")
def api_playlist():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    if not url:
        return jsonify({"success": False, "error": "لینک Playlist را وارد کنید."}), 400
    try:
        info = extract(url, playlist=True)
        entries = []
        for index, item in enumerate(info.get("entries") or [], 1):
            if not item:
                continue
            entries.append({"index": index, "id": item.get("id"), "title": item.get("title"), "thumbnail": item.get("thumbnail"), "duration": item.get("duration"), "url": item.get("webpage_url") or item.get("original_url")})
        return jsonify({"success": True, "title": info.get("title") or "Playlist", "uploader": info.get("uploader"), "count": len(entries), "entries": entries})
    except Exception as exc:
        return jsonify({"success": False, "error": human_error(exc)}), 500


def download_options(job_id, url, quality, media_type, title):
    settings = get_settings()
    path = settings["download_path"] or DOWNLOAD_FOLDER
    os.makedirs(path, exist_ok=True)
    outtmpl = os.path.join(path, f"{job_id}.%(ext)s")
    if media_type == "audio":
        fmt = "bestaudio/best"
    elif quality == "best":
        fmt = "bestvideo+bestaudio/best"
    else:
        h = int(quality)
        fmt = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"

    def hook(d):
        if CANCEL_EVENTS[job_id].is_set():
            raise yt_dlp.utils.DownloadCancelled()
        if d.get("status") == "downloading":
            downloaded = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            percent = round(min(99, downloaded * 100 / total), 1) if total else 0
            set_job(job_id, status="downloading", percent=percent, downloaded=format_bytes(downloaded), total=format_bytes(total), speed=format_bytes(d.get("speed") or 0) + "/s" if d.get("speed") else "—", eta=format_eta(d.get("eta")), message="در حال دانلود...", last_progress_at=time.time(), connection_state="connected")
        elif d.get("status") == "finished":
            set_job(job_id, status="processing", percent=99, message="در حال پردازش فایل...", connection_state="processing")

    opts = {"format": fmt, "outtmpl": outtmpl, "merge_output_format": "mp4", "noplaylist": True, "quiet": True, "no_warnings": True, "progress_hooks": [hook], "retries": MAX_RETRIES, "fragment_retries": MAX_RETRIES, "extractor_retries": 3, "file_access_retries": 3, "socket_timeout": 20, "continuedl": True}
    if settings["speed_limit"]:
        opts["ratelimit"] = settings["speed_limit"] * 1024
    if media_type == "audio":
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}, {"key": "EmbedThumbnail"}, {"key": "FFmpegMetadata"}]
        opts["writethumbnail"] = True
    return opts, path


def run_download(job_id, url, quality, media_type="video"):
    event = CANCEL_EVENTS[job_id]
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        if event.is_set():
            set_job(job_id, status="cancelled", message="دانلود لغو شد.", connection_state="cancelled")
            return
        try:
            set_job(job_id, status="starting", retry_count=attempt - 1, message="در حال اتصال به YouTube...", connection_state="connecting")
            with yt_dlp.YoutubeDL(info_options()) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title") or "video"
            opts, folder = download_options(job_id, url, quality, media_type, title)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            files = [f for f in glob.glob(os.path.join(folder, job_id + ".*")) if not f.endswith(".part")]
            if not files:
                raise RuntimeError("فایل خروجی پیدا نشد")
            source = max(files, key=os.path.getmtime)
            ext = os.path.splitext(source)[1]
            filename = clean_title(title) + ext
            destination = os.path.join(folder, filename)
            counter = 1
            while os.path.exists(destination):
                destination = os.path.join(folder, f"{clean_title(title)}_{counter}{ext}")
                counter += 1
            os.replace(source, destination)
            size = os.path.getsize(destination)
            conn = db()
            conn.execute("INSERT INTO history(title,url,filename,path,status,media_type,quality,size,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (title, url, os.path.basename(destination), destination, "completed", media_type, quality, size, time.time()))
            conn.commit(); conn.close()
            set_job(job_id, status="completed", percent=100, downloaded=format_bytes(size), total=format_bytes(size), speed="—", eta="—", message="دانلود با موفقیت انجام شد.", filename=os.path.basename(destination), file_path=destination, connection_state="completed")
            return
        except Exception as exc:
            last_error = exc
            if event.is_set():
                set_job(job_id, status="cancelled", message="دانلود لغو شد.", connection_state="cancelled")
                return
            error = human_error(exc)
            if attempt < MAX_RETRIES:
                wait = min(10, 2 ** (attempt - 1))
                set_job(job_id, status="retrying", retry_count=attempt, message=f"خطا؛ تلاش مجدد در {wait} ثانیه...", error=error, retrying=True, connection_state="retrying")
                time.sleep(wait)
            else:
                break
    set_job(job_id, status="error", message="دانلود ناموفق بود.", error=human_error(last_error), connection_state="failed")


@app.post("/api/download")
def api_download():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    quality = str(data.get("quality", "best"))
    media_type = str(data.get("media_type", "video"))
    if not url:
        return jsonify({"success": False, "error": "لینک وارد نشده است."}), 400
    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {"id": job_id, "status": "queued", "percent": 0, "message": "در صف دانلود...", "created_at": time.time()}
        CANCEL_EVENTS[job_id] = threading.Event()
    EXECUTOR.submit(run_download, job_id, url, quality, media_type)
    return jsonify({"success": True, "job_id": job_id})


@app.get("/api/progress/<job_id>")
def api_progress(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "دانلود پیدا نشد."}), 404
    if job.get("status") == "downloading":
        last = job.get("last_progress_at", job.get("updated_at", time.time()))
        if time.time() - last > STALE_SECONDS:
            job["connection_state"] = "retrying"
            job["message"] = "اتصال ناپایدار است؛ در حال تلاش مجدد..."
    return jsonify({"success": True, **job})


@app.post("/api/cancel/<job_id>")
def api_cancel(job_id):
    event = CANCEL_EVENTS.get(job_id)
    if not event:
        return jsonify({"success": False, "error": "دانلود پیدا نشد."}), 404
    event.set()
    set_job(job_id, status="cancelling", message="در حال لغو دانلود...", connection_state="cancelling")
    return jsonify({"success": True})


@app.post("/api/retry/<job_id>")
def api_retry(job_id):
    job = get_job(job_id)
    if not job or not job.get("url"):
        return jsonify({"success": False, "error": "اطلاعات دانلود قبلی در دسترس نیست."}), 404
    return jsonify({"success": False, "error": "برای retry دوباره همان لینک را به صف اضافه کنید."}), 400


@app.get("/api/file/<job_id>")
def api_file(job_id):
    job = get_job(job_id)
    path = job.get("file_path")
    if not path or not os.path.isfile(path):
        return jsonify({"success": False, "error": "فایل پیدا نشد."}), 404
    return send_file(path, as_attachment=True, download_name=job.get("filename", os.path.basename(path)))


@app.post("/api/thumbnail")
def api_thumbnail():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    if not url:
        return jsonify({"success": False, "error": "لینک وارد نشده است."}), 400
    try:
        info = extract(url)
        thumb = info.get("thumbnail")
        if not thumb:
            raise RuntimeError("Thumbnail پیدا نشد")
        import urllib.request
        filename = clean_title(info.get("title")) + "_thumbnail.jpg"
        path = os.path.join(DOWNLOAD_FOLDER, filename)
        urllib.request.urlretrieve(thumb, path)
        return send_file(path, as_attachment=True, download_name=filename)
    except Exception as exc:
        return jsonify({"success": False, "error": human_error(exc)}), 500


@app.get("/api/history")
def api_history():
    limit = min(int(request.args.get("limit", 100)), 500)
    conn = db(); rows = conn.execute("SELECT * FROM history ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall(); conn.close()
    return jsonify({"success": True, "items": [dict(r) for r in rows]})


@app.delete("/api/history/<int:item_id>")
def api_delete_history(item_id):
    conn = db(); row = conn.execute("SELECT path FROM history WHERE id=?", (item_id,)).fetchone()
    if row and row["path"] and os.path.isfile(row["path"]):
        try: os.remove(row["path"])
        except OSError: pass
    conn.execute("DELETE FROM history WHERE id=?", (item_id,)); conn.commit(); conn.close()
    return jsonify({"success": True})


@app.delete("/api/history")
def api_clear_history():
    conn = db(); conn.execute("DELETE FROM history"); conn.commit(); conn.close()
    return jsonify({"success": True})


@app.get("/api/settings")
def api_get_settings():
    return jsonify({"success": True, "settings": get_settings()})


@app.put("/api/settings")
def api_put_settings():
    data = request.get_json(silent=True) or {}
    conn = db()
    for key, value in data.items():
        if key not in {"download_path", "theme", "language", "concurrent_downloads", "speed_limit", "notifications", "clipboard_monitor"}:
            continue
        if isinstance(value, bool): value = "true" if value else "false"
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
    conn.commit(); conn.close()
    return jsonify({"success": True, "settings": get_settings()})


@app.get("/api/presets")
def api_presets():
    conn = db(); rows = conn.execute("SELECT * FROM presets ORDER BY created_at DESC").fetchall(); conn.close()
    return jsonify({"success": True, "items": [{**dict(r), "settings": json.loads(r["settings"])} for r in rows]})


@app.post("/api/presets")
def api_create_preset():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "Preset")).strip() or "Preset"
    settings = data.get("settings") or {}
    conn = db(); cur = conn.execute("INSERT INTO presets(name,settings,created_at) VALUES(?,?,?)", (name, json.dumps(settings, ensure_ascii=False), time.time())); conn.commit(); pid = cur.lastrowid; conn.close()
    return jsonify({"success": True, "id": pid})


@app.delete("/api/presets/<int:preset_id>")
def api_delete_preset(preset_id):
    conn = db(); conn.execute("DELETE FROM presets WHERE id=?", (preset_id,)); conn.commit(); conn.close()
    return jsonify({"success": True})


@app.get("/api/jobs")
def api_jobs():
    with JOBS_LOCK:
        return jsonify({"success": True, "items": list(JOBS.values())})


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def frontend(path):
    if FRONTEND_DIST and os.path.isdir(FRONTEND_DIST):
        requested = os.path.join(FRONTEND_DIST, path)
        if path and os.path.isfile(requested):
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")
    return jsonify({"success": True, "message": "Vue frontend is not built. Run: cd frontend && npm install && npm run build"})


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)