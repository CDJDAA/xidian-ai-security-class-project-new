"""Content identity before display truncation; course extension under LICENSE."""

from __future__ import annotations

import hashlib
import json
import re

FINGERPRINT_VERSION = "v2:sha256"


def content_fingerprint(title: str, text: str, source_url: str) -> str:
    """Keep field boundaries and source identity, ignoring repeated whitespace only."""
    fields = [re.sub(r"\s+", " ", value).strip() for value in (title, text, source_url)]
    payload = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    return f"{FINGERPRINT_VERSION}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def stored_fingerprint(item: dict) -> str:
    """Use the full-content identity, retaining historical identity for old files."""
    value = item.get("content_fingerprint")
    if value is not None:
        if not isinstance(value, str) or not re.fullmatch(r"v2:sha256:[0-9a-f]{64}", value):
            raise ValueError("Unsupported or invalid content_fingerprint")
        return value
    title = str(item.get("title") or "").strip()[:500]
    text = str(item.get("text") or "").strip()[:4000]
    url = str(item.get("source_url") or "").strip()[:1000]
    return hashlib.sha1(f"{title}\n{text}\n{url}".encode("utf-8")).hexdigest()
