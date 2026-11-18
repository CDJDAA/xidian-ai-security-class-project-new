"""Version-preserving arXiv metadata lookup without the agent runtime."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

IDENTIFIER = re.compile(r"(?:\d{4}\.\d{4,5}|[a-z][a-z.-]+/\d{7})(?:v[1-9]\d*)?\Z")
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ENDPOINT = "https://export.arxiv.org/api/query"


def normalize_arxiv_id(value: str) -> str:
    """Keep explicit revisions, including legacy category/number identifiers."""
    value = value.strip()
    if "://" in value:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or parsed.hostname not in
                {"arxiv.org", "www.arxiv.org", "export.arxiv.org"} or parsed.username or
                parsed.password or parsed.port not in {None, 80, 443} or parsed.query or parsed.fragment):
            raise ValueError("Expected an arXiv ID or an arxiv.org abs/pdf URL")
        if not parsed.path.startswith(("/abs/", "/pdf/")):
            raise ValueError("Expected an arXiv abs/pdf URL")
        value = parsed.path[5:]
        if parsed.path.startswith("/pdf/") and value.endswith(".pdf"):
            value = value[:-4]
    if not IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid arXiv identifier")
    return value


def parse_metadata(payload: bytes, requested_id: str) -> dict:
    """Reject missing papers and a response for a different revision."""
    requested_id = normalize_arxiv_id(requested_id)
    entries = ET.fromstring(payload).findall("atom:entry", NS)
    if len(entries) != 1:
        raise ValueError("Expected exactly one arXiv result")
    entry = entries[0]

    def text(tag: str) -> str:
        return (entry.findtext(tag, default="", namespaces=NS) or "").strip()

    returned_id = normalize_arxiv_id(text("atom:id"))
    explicit_version = re.search(r"v[1-9]\d*$", requested_id)
    expected = returned_id if explicit_version else re.sub(r"v\d+$", "", returned_id)
    if expected != requested_id:
        raise ValueError("arXiv returned a different paper or version")
    title, abstract = text("atom:title"), text("atom:summary")
    if not title or not abstract:
        raise ValueError("arXiv result lacks a title or abstract")
    primary = entry.find("arxiv:primary_category", NS)
    return {
        "title": " ".join(title.split()),
        "authors": [item.findtext("atom:name", default="", namespaces=NS) for item in entry.findall("atom:author", NS)],
        "abstract": abstract,
        "categories": [item.attrib["term"] for item in entry.findall("atom:category", NS)],
        "published": datetime.fromisoformat(text("atom:published").replace("Z", "+00:00")),
        "updated": datetime.fromisoformat(text("atom:updated").replace("Z", "+00:00")),
        "doi": text("arxiv:doi") or None, "pdf_url": "https://arxiv.org/pdf/" + returned_id,
        "primary_category": primary.attrib.get("term", "") if primary is not None else "",
        "comment": text("arxiv:comment") or None, "journal_ref": text("arxiv:journal_ref") or None,
        "version": returned_id.rsplit("v", 1)[1] if re.search(r"v\d+$", returned_id) else "1",
        "arxiv_id": returned_id,
        "provenance": {"requested_id": requested_id, "response_sha256": hashlib.sha256(payload).hexdigest(),
                       "retrieved_at_utc": datetime.now(timezone.utc).isoformat()},
    }


def fetch_arxiv_metadata(value: str, *, timeout: float = 20) -> dict:
    identifier = normalize_arxiv_id(value)
    url = ENDPOINT + "?" + urlencode({"id_list": identifier, "max_results": 1})
    request = Request(url, headers={"User-Agent": "xidian-course01-metadata/1.0"})
    with urlopen(request, timeout=timeout) as response:
        payload = response.read(2 * 1024 * 1024 + 1)
    if len(payload) > 2 * 1024 * 1024:
        raise ValueError("arXiv response exceeds the metadata size limit")
    result = parse_metadata(payload, identifier)
    result["provenance"]["query_url"] = url
    return result
