"""
main.py  —  FaceChain Pipeline
Face scan  →  Reverse image search  →  Social post found  →  Blockchain verification

Usage:
    python main.py <path_to_face_image>
Example:
    python main.py sample_images/test_face.jpg
"""

import sys
import json
from pipeline.face_encoder import encode_face
from pipeline.web_searcher import reverse_image_search, filter_social_media
from pipeline.post_scraper import scrape_post
from pipeline.hasher import hash_post_data
from pipeline.blockchain import upload_hash, verify_hash

SEPARATOR = "=" * 62


def run_pipeline(image_path: str):
    print(f"\n{SEPARATOR}")
    print("  FACECHAIN  |  Face  →  Web  →  Blockchain")
    print(SEPARATOR)

    # ── STEP 1: Face Detection ─────────────────────────────────
    print("\n[1/5] Detecting face ...")
    encoding = encode_face(image_path)
    print(f"      Encoding shape : {encoding.shape}  ✓")

    # ── STEP 2: Reverse Image Search ──────────────────────────
    print("\n[2/5] Running reverse image search (Google Lens via Serper) ...")
    all_results = reverse_image_search(image_path)

    if not all_results:
        print("      No visual matches found. Exiting.")
        sys.exit(1)

    social = filter_social_media(all_results)
    chosen = social[0] if social else all_results[0]
    print(f"      Chosen URL : {chosen['link']}")

    # ── STEP 3: Scrape Post Metadata ──────────────────────────
    print("\n[3/5] Scraping post metadata ...")
    post_data = scrape_post(chosen["link"])
    post_data["search_title"] = chosen.get("title", "")
    post_data["source"]       = chosen.get("source", "")
    print(json.dumps(post_data, indent=4))

    # ── STEP 4: Hash the Data ─────────────────────────────────
    print("\n[4/5] Hashing post data (SHA-256) ...")
    data_hash = hash_post_data(post_data)
    metadata_label = f"FaceChain|{post_data.get('url', '')}"[:200]

    # ── STEP 5: Upload + Verify on Blockchain ─────────────────
    print("\n[5/5] Uploading hash to Ethereum Sepolia testnet ...")
    tx_hash = upload_hash(data_hash, metadata_label)

    print("\n      Verifying hash on-chain ...")
    verification = verify_hash(data_hash)

    # ── FINAL REPORT ──────────────────────────────────────────
    print(f"\n{SEPARATOR}")
    print("  PIPELINE COMPLETE")
    print(SEPARATOR)
    print(f"  Input image      : {image_path}")
    print(f"  Post found       : {post_data.get('url')}")
    print(f"  Post title       : {post_data.get('title', '')[:55]}")
    print(f"  SHA-256 hash     : {data_hash}")
    print(f"  Tx hash          : {tx_hash}")
    print(f"  On-chain verified: {verification['exists']}")
    print(f"  Registered by    : {verification['uploader']}")
    print(f"  Timestamp (unix) : {verification['timestamp']}")
    print(f"  Etherscan        : https://sepolia.etherscan.io/tx/{tx_hash}")
    print(SEPARATOR + "\n")

    return {
        "post": post_data,
        "hash": data_hash,
        "tx_hash": tx_hash,
        "verified": verification,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_face_image>")
        sys.exit(1)
    run_pipeline(sys.argv[1])
