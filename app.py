"""
app.py  —  FaceChain Flask API Server
All pipeline print() logs are captured and streamed to the UI in real time.
"""

import os
import sys
import io
import json
import time
import uuid
import datetime
import threading
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory, stream_with_context
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from pipeline.face_encoder import load_models, encode_face
load_models()

from pipeline.web_searcher import reverse_image_search, filter_social_media, get_match_quality
from pipeline.post_scraper import scrape_post
from pipeline.hasher import hash_post_data
from pipeline.blockchain import upload_hash, verify_hash

app = Flask(__name__, template_folder="ui/templates", static_folder="ui/static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}

jobs: dict = {}
jobs_lock = threading.Lock()


def allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


def push_event(job_id: str, step: int, status: str, message: str, data: dict = None):
    payload = {
        "step":    step,
        "status":  status,
        "message": message,
        "data":    data or {},
        "ts":      time.time(),
    }
    with jobs_lock:
        jobs[job_id]["events"].append(payload)


def push_log(job_id: str, text: str):
    """Push a raw log line to the UI log panel."""
    payload = {
        "type": "log",
        "text": text.rstrip(),
        "ts":   time.time(),
    }
    with jobs_lock:
        jobs[job_id]["events"].append(payload)


class JobLogger(io.StringIO):
    """
    Replaces sys.stdout for the duration of a pipeline job.
    Every print() call gets captured and pushed as a log event to the UI.
    Also writes to the real stdout so terminal still shows logs.
    """
    def __init__(self, job_id: str, real_stdout):
        super().__init__()
        self.job_id      = job_id
        self.real_stdout = real_stdout
        self._buf        = ""

    def write(self, text: str):
        self.real_stdout.write(text)
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                push_log(self.job_id, line)

    def flush(self):
        self.real_stdout.flush()


def run_pipeline_job(job_id: str, image_path: str):
    real_stdout  = sys.stdout
    sys.stdout   = JobLogger(job_id, real_stdout)

    try:
        # ── Step 1 ────────────────────────────────────────────
        push_event(job_id, 1, "running", "Detecting face in image...")
        encoding = encode_face(image_path)
        push_event(job_id, 1, "done", f"Face detected — encoding shape {encoding.shape}", {
            "encoding_shape": list(encoding.shape),
        })

        # ── Step 2 ────────────────────────────────────────────
        push_event(job_id, 2, "running", "Uploading image and running reverse image search...")
        all_results = reverse_image_search(image_path)
        if not all_results:
            push_event(job_id, 2, "error", "No visual matches found on the web.")
            with jobs_lock:
                jobs[job_id]["done"] = True
            return

        social  = filter_social_media(all_results)
        chosen  = social[0] if social else all_results[0]
        quality = get_match_quality(all_results)

        print(f"[Pipeline] Match quality: {quality['quality']} — {quality['message']}")

        push_event(job_id, 2, "done", f"Found {len(all_results)} matches — using top result", {
            "total_matches":  len(all_results),
            "social_matches": len(social),
            "chosen":         chosen,
            "all_results":    all_results[:8],
            "quality":        quality,
        })

        # ── Step 3 ────────────────────────────────────────────
        push_event(job_id, 3, "running", f"Scraping post metadata from {chosen['link'][:60]}...")
        post_data = scrape_post(chosen["link"])
        post_data["search_title"] = chosen.get("title", "")
        post_data["source"]       = chosen.get("source", "")
        push_event(job_id, 3, "done", "Post metadata extracted", {"post": post_data})

        # ── Step 4 ────────────────────────────────────────────
        push_event(job_id, 4, "running", "Computing SHA-256 fingerprint of post data...")
        data_hash      = hash_post_data(post_data)
        metadata_label = f"FaceChain|{post_data.get('url', '')}"[:200]
        push_event(job_id, 4, "done", "SHA-256 hash computed", {"hash": data_hash})

        # ── Step 5 ────────────────────────────────────────────
        push_event(job_id, 5, "running", "Checking blockchain and registering hash...")
        result   = upload_hash(data_hash, metadata_label)
        status   = result["status"]
        tx_hash  = result["tx_hash"]
        record   = result["record"]
        ts       = record.get("timestamp", 0)
        ts_human = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC") if ts else ""
        etherscan = f"https://sepolia.etherscan.io/tx/{tx_hash}" if tx_hash else f"https://sepolia.etherscan.io/search?f=4&q={data_hash}"

        step5_msg = (
            "Hash already registered on-chain — showing original record."
            if status == "already_registered"
            else "Hash registered and verified on-chain"
        )
        push_event(job_id, 5, "done", step5_msg, {
            "tx_hash":            tx_hash,
            "etherscan":          etherscan,
            "verified":           record["exists"],
            "uploader":           record["uploader"],
            "timestamp":          ts,
            "timestamp_human":    ts_human,
            "data_hash":          data_hash,
            "already_registered": status == "already_registered",
        })

    except Exception as exc:
        push_event(job_id, 0, "error", str(exc), {"traceback": traceback.format_exc()})
    finally:
        sys.stdout = real_stdout
        with jobs_lock:
            jobs[job_id]["done"] = True


@app.route("/")
def index():
    return send_from_directory("ui/templates", "index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    f = request.files["image"]
    if not f.filename or not allowed(f.filename):
        return jsonify({"error": "Invalid file type. Use JPG, PNG or WebP."}), 400

    filename  = secure_filename(f.filename)
    save_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{filename}"
    f.save(str(save_path))

    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"events": [], "done": False}

    threading.Thread(target=run_pipeline_job, args=(job_id, str(save_path)), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/stream/<job_id>")
def stream(job_id: str):
    def generate():
        sent = 0
        while True:
            with jobs_lock:
                events = jobs.get(job_id, {}).get("events", [])
                done   = jobs.get(job_id, {}).get("done", False)
            while sent < len(events):
                yield f"data: {json.dumps(events[sent])}\n\n"
                sent += 1
            if done and sent >= len(events):
                yield 'data: {"__done__": true}\n\n'
                break
            time.sleep(0.2)

    return Response(stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/verify", methods=["POST"])
def verify():
    body      = request.get_json(silent=True) or {}
    data_hash = body.get("hash", "").strip()
    if len(data_hash) != 64:
        return jsonify({"error": "Provide a valid 64-char SHA-256 hex string"}), 400
    try:
        return jsonify(verify_hash(data_hash))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"\n  FaceChain UI  →  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
