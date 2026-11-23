#!/usr/bin/env python3
"""
YTSnatch - a local YouTube downloader web app (Muse edition).

Backend: Flask + yt-dlp. Frontend: one self-contained HTML page.
Run:  python3 app.py   then open http://localhost:5001 in Chrome.
"""
import os
import threading
import uuid

from flask import Flask, jsonify, render_template, request, send_file

try:
    import yt_dlp
except ImportError:  # pragma: no cover
    yt_dlp = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "Downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Flask(__name__)

# In-memory download jobs: job_id -> dict(status, percent, speed, filename, error, cancel)
JOBS = {}
JOBS_LOCK = threading.Lock()


def human_size(num):
    if not num:
        return None
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def friendly_error(exc):
    msg = str(exc)
    low = msg.lower()
    if "private" in low:
        return "This video is private, so it can't be downloaded."
    if "failed to extract" in low or "player response" in low:
        return ("YouTube refused the request from this server's network - "
                "a common block on hosting-company IPs. The video itself is "
                "fine; the same link works in the Termux version on the phone.")
    if "sign in" in low or "bot" in low or "login" in low:
        return ("YouTube is asking for a sign-in check on this video. "
                "Try a different video, or update yt-dlp: pip install -U yt-dlp")
    if "unavailable" in low or "removed" in low or "not exist" in low:
        return "This video is unavailable or has been removed."
    if "urlopen" in low or "network" in low or "timed out" in low:
        return "Network problem - check the phone's internet connection and try again."
    if "unsupported url" in low:
        return "That doesn't look like a YouTube video link."
    return f"Something went wrong: {msg[:200]}"


def build_format_list(info):
    """Collapse yt-dlp formats into one card per resolution (best stream per height)."""
    best_by_height = {}
    for fmt in info.get("formats", []):
        height = fmt.get("height")
        if not height or fmt.get("vcodec") in (None, "none"):
            continue
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        current = best_by_height.get(height)
        # Prefer mp4, then the larger (higher quality) stream at the same height.
        score = (1 if fmt.get("ext") == "mp4" else 0, size or 0)
        if current is None or score > current[0]:
            best_by_height[height] = (score, fmt, size)
    options = []
    for height in sorted(best_by_height, reverse=True):
        _, fmt, size = best_by_height[height]
        options.append({
            "kind": "video",
            "height": height,
            "label": f"{height}p",
            "detail": (fmt.get("ext") or "").upper(),
            "size": human_size(size),
        })
    options.append({
        "kind": "audio",
        "height": None,
        "label": "Audio only",
        "detail": "MP3",
        "size": None,
    })
    return options


@app.route("/")
def index():
    # Flat layout (no templates/ folder) so the whole app uploads
    # file-by-file through the Hugging Face web interface.
    return send_file(os.path.join(BASE_DIR, "index.html"))


@app.route("/api/info", methods=["POST"])
def api_info():
    if yt_dlp is None:
        return jsonify(error="yt-dlp is not installed. Run: pip install -r requirements.txt"), 500
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        return jsonify(error="Please paste a valid YouTube link (youtube.com or youtu.be)."), 400
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True,
                               "extractor_args": {"youtube": {"player_client": ["android_vr", "tv", "web_safari"]}}}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp raises many types; turn them into a friendly message
        return jsonify(error=friendly_error(exc)), 422
    duration = info.get("duration") or 0
    return jsonify(
        title=info.get("title"),
        channel=info.get("uploader"),
        duration=f"{duration // 60}:{duration % 60:02d}",
        thumbnail=info.get("thumbnail"),
        formats=build_format_list(info),
    )


def run_download(job_id, url, kind, height):
    def set_job(**kw):
        with JOBS_LOCK:
            JOBS[job_id].update(kw)

    def hook(d):
        with JOBS_LOCK:
            cancelled = JOBS[job_id].get("cancel")
        if cancelled:
            raise Exception("Cancelled by user")
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            set_job(
                percent=round(done * 100 / total, 1) if total else None,
                speed=d.get("_speed_str"),
                eta=d.get("_eta_str"),
            )
        elif d["status"] == "finished":
            set_job(percent=100, filename=os.path.basename(d["filename"]))

    if kind == "audio":
        fmt = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        fmt = (f"bestvideo[height<={height}]+bestaudio/"
               f"best[height<={height}]/best")
        postprocessors = []

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android_vr", "tv", "web_safari"]}},
        "format": fmt,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title).80s [%(id)s].%(ext)s"),
        "progress_hooks": [hook],
        "postprocessors": postprocessors,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        # Point the "Saved" message at the final merged/converted file,
        # not the last intermediate stream the progress hook saw.
        filepath = None
        if info:
            filepath = info.get("filepath")
            if not filepath:
                for rd in info.get("requested_downloads") or []:
                    if rd.get("filepath"):
                        filepath = rd["filepath"]
        if filepath:
            set_job(filename=os.path.basename(filepath), filepath=filepath)
        with JOBS_LOCK:
            job = JOBS[job_id]
        if job.get("cancel"):
            set_job(status="cancelled")
        else:
            set_job(status="done", percent=100)
    except Exception as exc:
        if "Cancelled by user" in str(exc):
            set_job(status="cancelled")
        else:
            set_job(status="error", error=friendly_error(exc))


@app.route("/api/download", methods=["POST"])
def api_download():
    if yt_dlp is None:
        return jsonify(error="yt-dlp is not installed. Run: pip install -r requirements.txt"), 500
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    kind = data.get("kind") or "video"
    height = data.get("height")
    if not url:
        return jsonify(error="Missing video URL."), 400
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "downloading", "percent": 0,
                        "speed": None, "eta": None, "filename": None,
                        "filepath": None,
                        "error": None, "cancel": False}
    threading.Thread(target=run_download, args=(job_id, url, kind, height),
                     daemon=True).start()
    return jsonify(job_id=job_id)


@app.route("/api/progress/<job_id>")
def api_progress(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return jsonify(error="Unknown job"), 404
        return jsonify({k: job.get(k) for k in
                        ("status", "percent", "speed", "eta", "filename", "error")})


@app.route("/api/cancel/<job_id>", methods=["POST"])
def api_cancel(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return jsonify(error="Unknown job"), 404
        job["cancel"] = True
    return jsonify(ok=True)


@app.route("/api/file/<job_id>")
def api_file(job_id):
    """Send the finished file to the visitor's device (needed when hosted:
    the download happens on the server, so the file must travel back)."""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None or job.get("status") != "done" or not job.get("filepath"):
            return jsonify(error="File not ready"), 404
        path = job["filepath"]
    if not os.path.exists(path):
        return jsonify(error="File no longer available"), 410

    def cleanup():
        try:
            os.remove(path)
        except OSError:
            pass

    # Give the browser time to finish receiving it, then free the disk.
    threading.Timer(180, cleanup).start()
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    print(f"YTSnatch running - Downloads folder: {DOWNLOAD_DIR}")
    print(f"Open in Chrome: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
