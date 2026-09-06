from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import uuid
import glob
import threading
import time
import re

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# -------------------------------------------------
# وضعیت دانلودها
# -------------------------------------------------
DOWNLOAD_JOBS = {}
JOBS_LOCK = threading.Lock()

MAX_DOWNLOAD_RETRIES = 5
PROGRESS_STALE_SECONDS = 12


def set_job(job_id, **values):
    with JOBS_LOCK:
        job = DOWNLOAD_JOBS.setdefault(job_id, {})
        job.update(values)
        job["updated_at"] = time.time()


def get_job(job_id):
    with JOBS_LOCK:
        return dict(DOWNLOAD_JOBS.get(job_id, {}))


def cleanup_job_later(job_id, seconds=300):
    def cleanup():
        time.sleep(seconds)
        with JOBS_LOCK:
            DOWNLOAD_JOBS.pop(job_id, None)

    threading.Thread(target=cleanup, daemon=True).start()


def format_bytes(value):
    if not value:
        return "0 MB"
    if value >= 1024 ** 3:
        return f"{value / 1024 ** 3:.2f} GB"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.1f} MB"
    return f"{value / 1024:.0f} KB"


def format_eta(seconds):
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def human_error(error):
    """Convert common yt-dlp/network errors into a user-friendly Persian message."""
    text = str(error).strip()
    lower = text.lower()

    if (
        "failed to resolve" in lower
        or "getaddrinfo failed" in lower
        or "name or service not known" in lower
        or "temporary failure in name resolution" in lower
    ):
        return (
            "اتصال به سرور دانلود YouTube برقرار نشد (خطای DNS). "
            "برنامه چند بار به‌صورت خودکار تلاش کرد. "
            "لطفاً اینترنت، DNS یا VPN/Proxy را بررسی کنید."
        )

    if (
        "timed out" in lower
        or "timeout" in lower
        or "connection reset" in lower
        or "connection aborted" in lower
        or "network is unreachable" in lower
        or "temporary network" in lower
    ):
        return (
            "ارتباط با سرور دانلود قطع یا ناپایدار شد. "
            "برنامه تلاش مجدد خودکار را انجام داد؛ لطفاً اتصال اینترنت را بررسی کنید."
        )

    if "ffmpeg" in lower and "not installed" in lower:
        return "FFmpeg روی سیستم نصب نیست و برای ترکیب صدا و تصویر لازم است."

    if "requested format is not available" in lower:
        return "کیفیت انتخاب‌شده برای این ویدیو در دسترس نیست. یک کیفیت دیگر را امتحان کنید."

    # Strip ANSI color/control codes from yt-dlp output.
    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return clean or "دانلود با خطای ناشناخته مواجه شد."


# -------------------------------------------------
# وضعیت دانلود
# -------------------------------------------------
@app.route("/progress/<job_id>", methods=["GET"])
def download_progress(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "دانلود پیدا نشد."}), 404

    # اگر thread برای مدتی هیچ progress hook جدیدی نفرستاده، به UI بگوییم
    # ممکن است اتصال در حال retry باشد؛ این باعث می‌شود progress bar گیرکرده به نظر نرسد.
    if job.get("status") == "downloading":
        last_progress = job.get("last_progress_at", job.get("updated_at", time.time()))
        stale_for = time.time() - last_progress
        if stale_for >= PROGRESS_STALE_SECONDS:
            job["connection_state"] = "retrying"
            job["message"] = "اتصال ناپایدار است؛ در حال تلاش مجدد خودکار..."
            job["retrying"] = True
            job["stale_for"] = round(stale_for, 1)
        else:
            job["connection_state"] = "connected"
            job["retrying"] = False

    return jsonify({"success": True, **job})


# -------------------------------------------------
# اطلاعات ویدیو
# -------------------------------------------------
def base_info_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "retries": MAX_DOWNLOAD_RETRIES,
        "extractor_retries": 3,
        "socket_timeout": 20,
    }


@app.route("/info", methods=["POST"])
def get_info():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"success": False, "error": "لطفاً URL را وارد کنید."}), 400

    try:
        with yt_dlp.YoutubeDL(base_info_options()) as ydl:
            info = ydl.extract_info(url, download=False)

        return jsonify({
            "success": True,
            "title": info.get("title", "Unknown"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader")
        })
    except Exception as e:
        return jsonify({"success": False, "error": human_error(e)}), 500


# -------------------------------------------------
# کیفیت‌های واقعی موجود
# -------------------------------------------------
@app.route("/formats", methods=["POST"])
def get_formats():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"success": False, "error": "لطفاً URL را وارد کنید."}), 400

    try:
        with yt_dlp.YoutubeDL(base_info_options()) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = info.get("formats") or []
        heights = set()
        has_audio = False

        for f in formats:
            height = f.get("height")
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")

            if height and vcodec and vcodec != "none":
                heights.add(int(height))
            if acodec and acodec != "none":
                has_audio = True

        def label_for(h):
            if h >= 2160:
                return "4K"
            if h >= 1440:
                return "2K"
            if h >= 1080:
                return "Full HD"
            if h >= 720:
                return "HD"
            if h >= 480:
                return "SD"
            return "کیفیت پایین"

        qualities = [
            {"value": str(h), "label": label_for(h), "resolution": f"{h}p"}
            for h in sorted(heights, reverse=True)
        ]

        if not qualities:
            return jsonify({
                "success": False,
                "error": "هیچ کیفیت ویدیویی برای این لینک پیدا نشد."
            }), 404

        return jsonify({"success": True, "qualities": qualities, "has_audio": has_audio})
    except Exception as e:
        return jsonify({"success": False, "error": human_error(e)}), 500


# -------------------------------------------------
# شروع دانلود
# -------------------------------------------------
@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    quality = str(data.get("quality", "best"))

    if not url:
        return jsonify({"success": False, "error": "URL وارد نشده است."}), 400

    job_id = str(uuid.uuid4())
    set_job(
        job_id,
        status="starting",
        percent=0,
        speed="—",
        eta="—",
        downloaded="0 MB",
        total="—",
        message="در حال آماده‌سازی دانلود...",
        retry_count=0,
        max_retries=MAX_DOWNLOAD_RETRIES,
        retrying=False,
        connection_state="starting",
        last_progress_at=time.time()
    )

    threading.Thread(
        target=run_download,
        args=(job_id, url, quality),
        daemon=True
    ).start()

    return jsonify({"success": True, "job_id": job_id})


def build_download_options(format_string, output_template, progress_hook):
    return {
        "format": format_string,
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],

        # Network resilience.
        "retries": MAX_DOWNLOAD_RETRIES,
        "fragment_retries": MAX_DOWNLOAD_RETRIES,
        "extractor_retries": 3,
        "file_access_retries": 3,
        "socket_timeout": 20,
        "retry_sleep_functions": {
            "http": lambda n: min(8, 1.5 ** n),
            "fragment": lambda n: min(8, 1.5 ** n),
            "extractor": lambda n: min(8, 1.5 ** n),
        },
    }


def run_download(job_id, url, quality):
    file_id = job_id
    output_template = os.path.join(DOWNLOAD_FOLDER, file_id + ".%(ext)s")

    if quality == "audio":
        format_string = "bestaudio/best"
    elif quality == "best":
        format_string = "bestvideo+bestaudio/best"
    else:
        try:
            height = int(quality)
            format_string = (
                f"bestvideo[height<={height}]+bestaudio/"
                f"best[height<={height}]"
            )
        except ValueError:
            format_string = "bestvideo+bestaudio/best"

    def progress_hook(d):
        status = d.get("status")

        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0) or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            percent = min(99, (downloaded / total) * 100) if total else 0
            speed_bps = d.get("speed")

            if speed_bps:
                speed = (
                    f"{speed_bps / 1024 ** 2:.1f} MB/s"
                    if speed_bps >= 1024 ** 2
                    else f"{speed_bps / 1024:.0f} KB/s"
                )
            else:
                speed = "—"

            now = time.time()
            set_job(
                job_id,
                status="downloading",
                percent=round(percent, 1),
                speed=speed,
                eta=format_eta(d.get("eta")),
                downloaded=format_bytes(downloaded),
                total=format_bytes(total) if total else "—",
                message="در حال دریافت فایل...",
                retrying=False,
                connection_state="connected",
                last_progress_at=now,
                stale_for=0
            )

        elif status == "finished":
            set_job(
                job_id,
                status="processing",
                percent=99,
                speed="—",
                eta="—",
                message="دانلود تمام شد؛ در حال پردازش و آماده‌سازی فایل...",
                retrying=False,
                connection_state="processing",
                last_progress_at=time.time()
            )

    set_job(
        job_id,
        status="starting",
        percent=0,
        message="در حال اتصال به YouTube...",
        connection_state="connecting",
        last_progress_at=time.time()
    )

    options = build_download_options(format_string, output_template, progress_hook)

    if quality == "audio":
        options["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320"
        }]

    last_error = None

    # لایه دوم retry: اگر کل استخراج/دانلود با خطای شبکه fail شد،
    # کل عملیات را دوباره اجرا می‌کنیم. yt-dlp خودش داخل هر تلاش نیز retry دارد.
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            set_job(
                job_id,
                retry_count=attempt - 1,
                message=(
                    "در حال دانلود..."
                    if attempt == 1
                    else f"اتصال مجدد؛ تلاش {attempt} از {MAX_DOWNLOAD_RETRIES}..."
                ),
                retrying=attempt > 1,
                connection_state="retrying" if attempt > 1 else "connecting"
            )

            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "video")

            files = glob.glob(os.path.join(DOWNLOAD_FOLDER, file_id + ".*"))
            if not files:
                raise RuntimeError("فایل دانلود نشد.")

            file_path = max(files, key=os.path.getmtime)
            extension = os.path.splitext(file_path)[1]

            safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
            if not safe_title:
                safe_title = "video"

            new_path = os.path.join(DOWNLOAD_FOLDER, safe_title + extension)
            counter = 1
            while os.path.exists(new_path):
                new_path = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}_{counter}{extension}")
                counter += 1

            os.rename(file_path, new_path)

            set_job(
                job_id,
                status="ready",
                percent=100,
                speed="—",
                eta="—",
                downloaded="کامل",
                total="کامل",
                message="دانلود با موفقیت انجام شد.",
                retrying=False,
                connection_state="completed",
                download_url=f"/file/{file_id}",
                filename=os.path.basename(new_path),
                file_path=new_path,
                last_progress_at=time.time()
            )
            cleanup_job_later(job_id)
            return

        except Exception as e:
            last_error = e
            error_text = human_error(e)

            # Retry فقط برای خطاهای شبکه/DNS/timeout انجام می‌شود.
            retryable = any(key in error_text.lower() for key in [
                "dns", "اتصال", "ارتباط", "سرور", "network", "timeout", "timed out"
            ])

            if attempt < MAX_DOWNLOAD_RETRIES and retryable:
                wait_seconds = min(10, 2 ** (attempt - 1))
                set_job(
                    job_id,
                    status="retrying",
                    percent=get_job(job_id).get("percent", 0),
                    message=f"اتصال قطع شد؛ تلاش مجدد در {wait_seconds} ثانیه...",
                    error=error_text,
                    retry_count=attempt,
                    retrying=True,
                    connection_state="retrying"
                )
                time.sleep(wait_seconds)
                continue

            break

    error_message = human_error(last_error or "دانلود ناموفق بود.")
    set_job(
        job_id,
        status="error",
        message="دانلود ناموفق بود.",
        error=error_message,
        retry_count=MAX_DOWNLOAD_RETRIES,
        retrying=False,
        connection_state="failed",
        last_progress_at=time.time()
    )
    cleanup_job_later(job_id, 600)


@app.route("/file/<job_id>", methods=["GET"])
def get_file(job_id):
    job = get_job(job_id)
    path = job.get("file_path")

    if not path or not os.path.isfile(path):
        return jsonify({"success": False, "error": "فایل پیدا نشد یا منقضی شده است."}), 404

    return send_file(path, as_attachment=True, download_name=job.get("filename", os.path.basename(path)))


# -------------------------------------------------
# Thumbnail
# -------------------------------------------------
@app.route("/thumbnail", methods=["POST"])
def download_thumbnail():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"success": False, "error": "URL وارد نشده است."}), 400

    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_FOLDER, file_id + ".%(ext)s")

    try:
        options = {
            "writethumbnail": True,
            "skip_download": True,
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": MAX_DOWNLOAD_RETRIES,
            "extractor_retries": 3,
            "socket_timeout": 20,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "thumbnail")

        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, file_id + ".*"))
        thumbnail_files = [
            f for f in files
            if os.path.splitext(f)[1].lower() in [".jpg", ".jpeg", ".png", ".webp"]
        ]

        if not thumbnail_files:
            raise RuntimeError("Thumbnail پیدا نشد.")

        file_path = thumbnail_files[0]
        extension = os.path.splitext(file_path)[1]
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip() or "thumbnail"
        new_path = os.path.join(DOWNLOAD_FOLDER, safe_title + "_thumbnail" + extension)
        counter = 1
        while os.path.exists(new_path):
            new_path = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}_thumbnail_{counter}{extension}")
            counter += 1
        os.rename(file_path, new_path)

        return send_file(new_path, as_attachment=True, download_name=os.path.basename(new_path))

    except Exception as e:
        for f in glob.glob(os.path.join(DOWNLOAD_FOLDER, file_id + ".*")):
            try:
                os.remove(f)
            except OSError:
                pass
        return jsonify({"success": False, "error": human_error(e)}), 500


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
