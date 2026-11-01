"""Reference metadata tool; explicit arXiv revisions are preserved."""
import logging
from typing import Any
from urllib.error import URLError
from xml.etree.ElementTree import ParseError
from research_agent.arxiv_metadata import fetch_arxiv_metadata


def get_arxiv_paper_meta(arxiv_id: str) -> dict[str, Any] | None:
    """Keep the existing dictionary/None contract without heavy SDK imports."""
    try:
        return fetch_arxiv_metadata(arxiv_id)
    except (URLError, TimeoutError, ValueError, ParseError, OSError) as exc:
        logging.getLogger(__name__).warning("arXiv metadata lookup failed (%s)", type(exc).__name__)
        return None
