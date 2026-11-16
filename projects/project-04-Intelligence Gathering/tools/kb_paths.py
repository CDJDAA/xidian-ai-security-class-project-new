"""Isolated knowledge-base paths shared by crawlers and the analysis pipeline."""

from __future__ import annotations

import re
from pathlib import Path

import config

ACADEMIC_PLATFORMS = {"arxiv", "openalex", "semantic_scholar", "pubmed"}
REPOSITORY_PLATFORMS = {"github", "gitlab"}
LINKED_REPOSITORY_DIR = "linked_repositories"


def safe_segment(value: str, default: str = "default") -> str:
    text = re.sub(r"[^\w.-]+", "-", str(value or "").strip(), flags=re.UNICODE).strip("._-")
    return text[:80] or default


def kb_namespace() -> str:
    return safe_segment(getattr(config, "KB_NAMESPACE", "ai-security") or "ai-security")


def kb_root() -> Path:
    base = Path(config.SAVE_DATA_PATH).expanduser() if config.SAVE_DATA_PATH else Path("data")
    return base / "kb" / kb_namespace()


def source_category(platform: str) -> str:
    value = str(platform or "").casefold()
    if value in ACADEMIC_PLATFORMS:
        return "papers"
    if value in REPOSITORY_PLATFORMS:
        return "repositories"
    return "platforms"


def kb_source_dir(platform: str, file_type: str = "jsonl") -> Path:
    return kb_root() / source_category(platform) / safe_segment(platform) / file_type


def platform_from_relative_path(relative_path: str) -> str:
    """Read the platform from both the new kb layout and legacy data/<platform>/... files."""
    parts = [part for part in str(relative_path).replace("\\", "/").split("/") if part]
    if len(parts) >= 4 and parts[0] == "kb":
        return parts[3]
    return parts[0] if parts else "unknown"
