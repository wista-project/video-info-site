from flask import Flask, request, render_template, jsonify
import yt_dlp
import os
import re

app = Flask(__name__)

# -----------------------------
# yt-dlp 情報取得
# -----------------------------
def get_video_info(video_id: str):
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "concurrent_fragment_downloads": 1,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


# -----------------------------
# フォーマット整形
# -----------------------------
def simplify_format(f: dict):
    return {
        "format_id": f.get("format_id"),
        "ext": f.get("ext"),
        "filesize": f.get("filesize"),
        "filesize_approx": f.get("filesize_approx"),
        "resolution": f.get("resolution"),
        "fps": f.get("fps"),
        "vcodec": f.get("vcodec"),
        "acodec": f.get("acodec"),
        "vbr": f.get("vbr"),
        "abr": f.get("abr"),
        "tbr": f.get("tbr"),
    }


def serialize_info(info: dict, video_id: str):
    formats = info.get("formats", [])

    video_formats = [f for f in formats if f.get("vcodec") != "none"]
    audio_formats = [f for f in formats if f.get("vcodec") == "none"]

    best_video = max(
        video_formats,
        key=lambda f: (f.get("height") or 0, f.get("tbr") or 0),
        default=None,
    )

    best_audio = max(
        audio_formats,
        key=lambda f: f.get("abr") or 0,
        default=None,
    )

    return {
        "id": video_id,
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "view_count": info.get("view_count"),
        "upload_date": info.get("upload_date"),
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url"),
        "description": info.get("description"),

        "formats": [simplify_format(f) for f in video_formats],
        "audio_formats": [simplify_format(f) for f in audio_formats],

        "best_video": simplify_format(best_video) if best_video else None,
        "best_audio": simplify_format(best_audio) if best_audio else None,
    }


# -----------------------------
# yt-dlp コマンド生成
# -----------------------------
def is_safe_format_id(format_id: str):
    return bool(re.fullmatch(r"[0-9A-Za-z_+-]+", format_id))


def generate_command(video_id: str, type_: str, format_id: str | None):
    url = f"https://www.youtube.com/watch?v={video_id}"

    if format_id:
        if not is_safe_format_id(format_id):
            raise ValueError("invalid format_id")

        return {
            "command": f'yt-dlp -f "{format_id}" {url}',
            "note": "custom format_id",
        }

    if type_ == "audio":
        return {
            "command": (
                f'yt-dlp -f "bestaudio" '
                f'--extract-audio --audio-format mp3 {url}'
            ),
            "note": "audio only",
        }

    return {
        "command": f'yt-dlp -f "bestvideo+bestaudio/best" {url}',
        "note": "best quality (video+audio)",
    }


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    video_id = request.args.get("id")
    if not video_id:
        return "id parameter is required", 400

    info = get_video_info(video_id)
    return render_template("index.html", **serialize_info(info, video_id))


@app.route("/api")
def api():
    video_id = request.args.get("id")
    if not video_id:
        return jsonify({"error": "id parameter is required"}), 400

    try:
        info = get_video_info(video_id)
        return jsonify(serialize_info(info, video_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/command")
def api_command():
    video_id = request.args.get("id")
    type_ = request.args.get("type", "video")
    format_id = request.args.get("format_id")

    if not video_id:
        return jsonify({"error": "id parameter is required"}), 400

    try:
        return jsonify(generate_command(video_id, type_, format_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# -----------------------------
# Entry point (Render)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
