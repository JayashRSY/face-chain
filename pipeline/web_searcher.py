"""
web_searcher.py
Uploads image to imgbb, then runs reverse image search via Serper.dev.
Returns a list of visual match results, filtered to social media where possible.
"""

import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

SOCIAL_DOMAINS = [
    "instagram.com", "twitter.com", "x.com",
    "facebook.com", "linkedin.com", "reddit.com",
    "tiktok.com", "youtube.com", "pinterest.com",
    "threads.net", "snapchat.com",
]


def upload_image_to_imgbb(image_path: str) -> str:
    """Upload image to imgbb and return public URL."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": b64},
        timeout=30,
    )
    resp.raise_for_status()
    url = resp.json()["data"]["url"]
    print(f"[WebSearcher] Image hosted at: {url}")
    return url


def reverse_image_search(image_path: str) -> list:
    """
    Runs Google Lens reverse image search via Serper.dev.
    Returns list of dicts: {title, link, thumbnail, source}
    """
    hosted_url = upload_image_to_imgbb(image_path)

    resp = requests.post(
        "https://google.serper.dev/lens",
        headers={
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json",
        },
        json={"url": hosted_url},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    # Serper Lens returns visual_matches or images key
    for item in data.get("visual_matches", data.get("images", [])):
        results.append({
            "title": item.get("title", ""),
            "link": item.get("link", item.get("imageUrl", "")),
            "thumbnail": item.get("thumbnailUrl", item.get("thumbnail", "")),
            "source": item.get("source", ""),
        })

    print(f"[WebSearcher] Found {len(results)} visual matches.")
    return results


def filter_social_media(results: list) -> list:
    """Filter results to known social media domains."""
    filtered = [
        r for r in results
        if any(domain in r.get("link", "") for domain in SOCIAL_DOMAINS)
    ]
    print(f"[WebSearcher] {len(filtered)} social media result(s) after filter.")
    return filtered
