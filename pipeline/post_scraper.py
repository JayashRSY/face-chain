"""
post_scraper.py
Scrapes Open Graph metadata from a discovered social media post URL.
Returns a canonical dict used for hashing.
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_post(url: str) -> dict:
    """
    Scrapes Open Graph + meta tags from a URL.
    Returns: { url, title, description, og_image, site_name }
    Falls back gracefully if scraping is blocked.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        def og(prop: str) -> str:
            tag = soup.find("meta", property=f"og:{prop}")
            return (tag.get("content") or "").strip() if tag else ""

        def meta(name: str) -> str:
            tag = soup.find("meta", attrs={"name": name})
            return (tag.get("content") or "").strip() if tag else ""

        title = og("title") or (soup.title.string.strip() if soup.title else "")
        post_data = {
            "url": url,
            "title": title,
            "description": og("description") or meta("description"),
            "og_image": og("image"),
            "site_name": og("site_name") or meta("application-name"),
        }
        print(f"[PostScraper] Title: {post_data['title'][:80]}")
        return post_data

    except Exception as exc:
        print(f"[PostScraper] Warning — could not fully scrape {url}: {exc}")
        # Return minimal dict so the pipeline can still hash + register
        return {
            "url": url,
            "title": "",
            "description": "",
            "og_image": "",
            "site_name": "",
        }
