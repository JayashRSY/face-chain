"""
web_searcher.py
Reverse image search pipeline with scoring, ranking and quality threshold.

Score thresholds (out of 10):
  >= 8  : GOOD  — confident match, social/quality page with thumbnail
  2–3.9 : WEAK  — some signal but low confidence
  < 2.0 : POOR  — likely not a real person match (random page, imgbb fallback)
"""

import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
IMGBB_API_KEY  = os.getenv("IMGBB_API_KEY")

# Minimum score to consider a result a genuine match
SCORE_THRESHOLD_GOOD = 4.0   # confident match
SCORE_THRESHOLD_WEAK = 2.0   # acceptable but low confidence

SOCIAL_TIERS = {
    "instagram.com": 10,
    "twitter.com":    9,
    "x.com":          9,
    "linkedin.com":   8,
    "facebook.com":   7,
    "threads.net":    7,
    "reddit.com":     6,
    "youtube.com":    5,
    "tiktok.com":     5,
    "pinterest.com":  4,
    "snapchat.com":   4,
}

QUALITY_DOMAINS = [
    "wikipedia.org", "imdb.com", "britannica.com",
    "forbes.com", "bbc.com", "ndtv.com", "hindustantimes.com",
    "timesofindia.com", "cricinfo.com", "espn.com",
]


def upload_image_to_imgbb(image_path: str) -> str:
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


def _score_result(result: dict, position: int) -> float:
    score = 0.0
    link  = result.get("link", "")
    title = result.get("title", "")
    thumb = result.get("thumbnail", "")

    for domain, tier_score in SOCIAL_TIERS.items():
        if domain in link:
            score += tier_score / 2   # max 5
            break

    score += max(0, 2.5 - position * 0.25)   # max 2.5

    if thumb and "imgbb" not in thumb:
        score += 1   # max 1

    for domain in QUALITY_DOMAINS:
        if domain in link:
            score += 1   # max 1
            break

    if len(title) > 15:
        score += 0.5   # max 0.5

    return round(min(score, 10.0), 1)   # cap at 10


def _score_label(score: float) -> str:
    if score >= SCORE_THRESHOLD_GOOD:
        return "good"
    if score >= SCORE_THRESHOLD_WEAK:
        return "weak"
    return "poor"


def rank_results(results: list) -> list:
    scored = []
    for i, r in enumerate(results):
        s = _score_result(r, position=i)
        scored.append({**r, "_score": s, "_quality": _score_label(s)})

    scored.sort(key=lambda x: x["_score"], reverse=True)

    print("[WebSearcher] Top 5 ranked results:")
    for r in scored[:5]:
        print(f"  score={r['_score']:.1f} [{r['_quality']}]  {r['link'][:65]}")

    top_score = scored[0]["_score"] if scored else 0
    print(f"[WebSearcher] Top score: {top_score} — quality: {_score_label(top_score)}")

    return scored


def get_match_quality(results: list) -> dict:
    """
    Evaluate the top result and return a quality assessment.
    Used by app.py to decide whether to proceed or show a warning.
    Returns:
      {
        "quality":  "good" | "weak" | "poor",
        "score":    float,
        "message":  str   — human-readable explanation
      }
    """
    if not results:
        return {
            "quality": "poor",
            "score":   0,
            "message": "No results found. The face may not be publicly indexed on the web.",
        }

    top = results[0]
    score = top.get("_score", 0)

    if score >= SCORE_THRESHOLD_GOOD:
        return {
            "quality": "good",
            "score":   score,
            "message": f"Strong match found on {_domain(top['link'])} (score {score:.1f}/10)",
        }
    if score >= SCORE_THRESHOLD_WEAK:
        return {
            "quality": "weak",
            "score":   score,
            "message": (
                f"Low-confidence match found (score {score:.1f}/10). "
                "The face may not be widely indexed. Results may not match the uploaded person."
            ),
        }
    return {
        "quality": "poor",
        "score":   score,
        "message": (
            f"No confident match found (score {score:.1f}). "
            "This face does not appear to be publicly indexed on the web. "
            "Try uploading a photo of a well-known public figure for best results."
        ),
    }


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


def reverse_image_search(image_path: str) -> list:
    """
    Multi-strategy reverse image search.
    Returns results ranked by match quality (best first).
    Always returns at least one result (imgbb fallback).
    """
    hosted_url = upload_image_to_imgbb(image_path)
    headers    = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    results    = []

    # Strategy 1: Serper Lens
    try:
        resp = requests.post(
            "https://google.serper.dev/lens",
            headers=headers, json={"url": hosted_url}, timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"[WebSearcher] Lens raw keys: {list(data.keys())}")
        for item in data.get("visual_matches", []):
            if item.get("link"):
                results.append({
                    "title":     item.get("title", ""),
                    "link":      item["link"],
                    "thumbnail": item.get("thumbnailUrl", item.get("imageUrl", "")),
                    "source":    item.get("source", ""),
                })
        for item in data.get("organic", []):
            if item.get("link"):
                results.append({
                    "title":     item.get("title", ""),
                    "link":      item["link"],
                    "thumbnail": item.get("imageUrl", ""),
                    "source":    item.get("displayedLink", ""),
                })
        print(f"[WebSearcher] Strategy 1 (Lens): {len(results)} results.")
    except Exception as e:
        print(f"[WebSearcher] Lens failed: {e}")

    if results:
        return rank_results(results)

    # Strategy 2: Web search
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers=headers, json={"q": hosted_url, "num": 10}, timeout=30,
        )
        resp.raise_for_status()
        for item in resp.json().get("organic", []):
            if item.get("link"):
                results.append({
                    "title": item.get("title", ""), "link": item["link"],
                    "thumbnail": "", "source": item.get("displayedLink", ""),
                })
        print(f"[WebSearcher] Strategy 2 (web search): {len(results)} results.")
    except Exception as e:
        print(f"[WebSearcher] Web search failed: {e}")

    if results:
        return rank_results(results)

    # Strategy 3: Image search
    try:
        resp = requests.post(
            "https://google.serper.dev/images",
            headers=headers, json={"q": hosted_url, "num": 10}, timeout=30,
        )
        resp.raise_for_status()
        for item in resp.json().get("images", []):
            link = item.get("link", item.get("imageUrl", ""))
            if link:
                results.append({
                    "title": item.get("title", ""), "link": link,
                    "thumbnail": item.get("imageUrl", ""), "source": item.get("source", ""),
                })
        print(f"[WebSearcher] Strategy 3 (image search): {len(results)} results.")
    except Exception as e:
        print(f"[WebSearcher] Image search failed: {e}")

    if results:
        return rank_results(results)

    # Strategy 4: Fallback
    print("[WebSearcher] All strategies exhausted — using imgbb fallback.")
    return [{
        "title": "Uploaded face image", "link": hosted_url,
        "thumbnail": hosted_url, "source": "imgbb.com",
        "_score": 0, "_quality": "poor",
    }]


def filter_social_media(results: list) -> list:
    filtered = [r for r in results if any(d in r.get("link", "") for d in SOCIAL_TIERS)]
    print(f"[WebSearcher] {len(filtered)} social media result(s) after filter.")
    return filtered
