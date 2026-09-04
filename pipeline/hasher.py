"""
hasher.py
Produces a deterministic SHA-256 hash of the discovered post's canonical fields.
The same post JSON will always produce the same hash — enabling on-chain verification.
"""

import json
import hashlib


def hash_post_data(post_data: dict) -> str:
    """
    Canonical SHA-256 of: url + title + description + og_image.
    Returns 64-char hex string (no 0x prefix).
    """
    canonical = {
        "url": post_data.get("url", ""),
        "title": post_data.get("title", ""),
        "description": post_data.get("description", ""),
        "og_image": post_data.get("og_image", ""),
    }
    serialized = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    print(f"[Hasher] SHA-256: {digest}")
    return digest


def hex_to_bytes32(hex_str: str) -> bytes:
    """Convert 64-char hex string to bytes32 for Solidity ABI."""
    return bytes.fromhex(hex_str)
