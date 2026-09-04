"""
app.py  —  FaceChain Flask API Server
Serves the UI and exposes pipeline endpoints via SSE (Server-Sent Events)
so the frontend gets live step-by-step progress.

Run locally:
    python app.py
Then open:  http://localhost:7860
"""

import os
import sys
import json
import time
import uuid
import threading
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory, stream_with_context
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

# ── pipeline imports ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from pipeline.face_encoder import encode_face
from pipeline.web_searcher import reverse_image_search, filter_social_media
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
        "step": step,
        "status": status,
        "message": message,
        "data": data or {},
        "ts": time.time(),
    }
    with jobs_lock:
        jobs[job_id]["events"].append(payload)


def run_pipeline_job(job_id: str, image_path: str):
    try:
        push_event(job_id, 1, "running", "Detecting face in image...")
        encoding = encode_face(image_path)
        push_event(job_id, 1, "done", f"Face detected — encoding shape {encoding.shape}", {
            "encoding_shape": list(encoding.shape),
        })

        push_event(job_id, 2, "running", "Uploading image and running reverse image search...")
        all_results = reverse_image_search(image_path)
        if not all_results:
            push_event(job_id, 2, "error", "No visual matches found on the web.")
            with jobs_lock:
                jobs[job_id]["done"] = True
            return

        social = filter_social_media(all_results)
        chosen = social[0] if social else all_results[0]
        push_event(job_id, 2, "done", f"Found {len(all_results)} matches — using top result", {
            "total_matches": len(all_results),
            "social_matches": len(social),
            "chosen": chosen,
            "all_results": all_results[:8],
        })

        push_event(job_id, 3, "running", f"Scraping post metadata from {chosen['link'][:60]}...")
        post_data = scrape_post(chosen["link"])
        post_data["search_title"] = chosen.get("title", "")
        post_data["source"] = chosen.get("source", "")
        push_event(job_id, 3, "done", "Post metadata extracted", {"post": post_data})

        push_event(job_id, 4, "running", "Computing SHA-256 fingerprint of post data...")
        data_hash = hash_post_data(post_data)
        metadata_label = f"FaceChain|{post_data.get('url', '')}"[:200]
        push_event(job_id, 4, "done", "SHA-256 hash computed", {"hash": data_hash})

        push_event(job_id, 5, "running", "Uploading hash to Ethereum Sepolia testnet...")
        tx_hash = upload_hash(data_hash, metadata_label)

        push_event(job_id, 5, "running", "Verifying hash on-chain...")
        verification = verify_hash(data_hash)

        import datetime
        ts = verification.get("timestamp", 0)
        ts_human = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC") if ts else ""

        push_event(job_id, 5, "done", "Hash registered and verified on-chain", {
            "tx_hash": tx_hash,
            "etherscan": f"https://sepolia.etherscan.io/tx/{tx_hash}",
            "verified": verification["exists"],
            "uploader": verification["uploader"],
            "timestamp": ts,
            "timestamp_human": ts_human,
            "data_hash": data_hash,
        })

    except Exception as exc:
        tb = traceback.format_exc()
        push_event(job_id, 0, "error", str(exc), {"traceback": tb})
    finally:
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

    filename = secure_filename(f.filename)
    save_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{filename}"
    f.save(str(save_path))

    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"events": [], "done": False}

    t = threading.Thread(target=run_pipeline_job, args=(job_id, str(save_path)), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/stream/<job_id>")
def stream(job_id: str):
    def generate():
        sent = 0
        while True:
            with jobs_lock:
                events = jobs.get(job_id, {}).get("events", [])
                done = jobs.get(job_id, {}).get("done", False)

            while sent < len(events):
                yield f"data: {json.dumps(events[sent])}\n\n"
                sent += 1

            if done and sent >= len(events):
                yield "data: {\"__done__\": true}\n\n"
                break

            time.sleep(0.3)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/verify", methods=["POST"])
def verify():
    body = request.get_json(silent=True) or {}
    data_hash = body.get("hash", "").strip()
    if len(data_hash) != 64:
        return jsonify({"error": "Provide a valid 64-char SHA-256 hex string"}), 400
    try:
        result = verify_hash(data_hash)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"\n  FaceChain UI  →  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
