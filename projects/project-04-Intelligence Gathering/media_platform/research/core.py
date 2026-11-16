from __future__ import annotations

import asyncio
import html
import os
import re
from typing import Any, Dict, Optional

import httpx
from playwright.async_api import BrowserContext, BrowserType, Playwright

import config
from base.base_crawler import AbstractCrawler
from tools.async_file_writer import AsyncFileWriter
from tools import utils
from var import crawler_type_var, source_keyword_var


# Public research platforms are predominantly English.  The UI can remain
# Chinese-first while these adapters issue the corresponding research queries.
RESEARCH_KEYWORD_EXPANSIONS = {
    "人工智能安全": ["AI safety", "AI security", "trustworthy AI"],
    "可信人工智能": ["trustworthy AI", "responsible AI"],
    "大模型安全": ["LLM security", "large language model safety"],
    "AI 对齐": ["AI alignment", "alignment research"],
    "价值学习": ["value learning", "preference learning"],
    "模型鲁棒性": ["model robustness", "adversarial robustness"],
    "可解释性": ["AI interpretability", "explainable AI"],
    "对抗样本": ["adversarial examples", "adversarial attack"],
    "机器学习安全": ["machine learning security", "ML security"],
    "提示注入": ["prompt injection", "indirect prompt injection"],
    "越狱攻击": ["LLM jailbreak", "jailbreak attack"],
    "红队测试": ["AI red teaming", "LLM red teaming"],
    "隐私保护": ["privacy preserving machine learning", "AI privacy"],
    "联邦学习安全": ["federated learning security"],
    "数据投毒": ["data poisoning", "training data poisoning"],
    "数据治理": ["AI data governance", "data governance"],
    "机器遗忘": ["machine unlearning"],
    "生成式 AI 安全": ["generative AI safety", "generative AI security"],
    "LLM 安全": ["LLM security", "large language model security"],
    "RAG 安全": ["RAG security", "retrieval augmented generation security"],
    "AI Agent 安全": ["AI agent security", "agent security"],
    "MCP 安全": ["MCP security", "Model Context Protocol security", "MCP tool poisoning", "MCP prompt injection", "MCP server vulnerability"],
    "MCP": ["Model Context Protocol"],
    "模型上下文协议": ["Model Context Protocol"],
    "多模态安全": ["multimodal AI safety", "multimodal security"],
    "AI 风险评估": ["AI risk assessment", "AI risk management"],
    "模型评测": ["AI safety evaluation", "LLM benchmark"],
    "AI 治理": ["AI governance"],
    "算法审计": ["algorithmic audit", "AI audit"],
    "AI 伦理": ["AI ethics"],
}


MCP_SECURITY_QUERIES = [
    "Model Context Protocol security",
    "MCP security",
    "MCP attack",
    "MCP vulnerability",
    "MCP tool poisoning",
    "MCP prompt injection",
    "MCP tool injection",
    "MCP threat model",
    "MCP supply chain security",
    "MCP server security",
]

MCP_MARKERS = ("mcp", "model context protocol", "模型上下文协议")

SECURITY_MARKERS = (
    "security", "secure", "attack", "vulnerab", "poison", "injection", "exploit",
    "threat", "risk", "defense", "defence", "guardrail", "sandbox", "permission",
    "authorization", "supply chain", "red team", "malicious", "abuse", "privacy",
    "leak", "unsafe", "trust", "安全", "攻击", "漏洞", "投毒", "注入", "越狱",
    "防御", "防护", "风险", "权限", "授权", "供应链", "恶意", "滥用", "沙箱",
    "审计", "泄露", "可信",
)


def _contains_mcp(value: str) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in MCP_MARKERS)


def _has_security_term(value: str) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in SECURITY_MARKERS)


def is_mcp_security_query(value: str) -> bool:
    return _contains_mcp(value) and _has_security_term(value)


def _github_query(query: str) -> str:
    """Keep MCP searches on repositories whose name/description carry the topic."""
    if not is_mcp_security_query(query):
        return query
    text = str(query or "").casefold()
    if "tool poisoning" in text or "工具投毒" in text:
        return 'mcp in:name,description "tool poisoning"'
    if "prompt injection" in text or "提示注入" in text:
        return 'mcp in:name,description "prompt injection"'
    if "tool injection" in text:
        return 'mcp in:name,description "tool injection"'
    if "supply chain" in text or "供应链" in text:
        return 'mcp in:name,description "supply chain"'
    if "vulnerab" in text or "漏洞" in text:
        return "mcp in:name,description vulnerability"
    if "attack" in text or "攻击" in text:
        return "mcp in:name,description attack"
    return "mcp in:name security"


def _arxiv_expression(query: str) -> str:
    """Translate an MCP query into a precise arXiv boolean expression."""
    text = str(query or "").casefold()
    if not _contains_mcp(text):
        return f"all:{query}"
    if "tool poisoning" in text or "工具投毒" in text:
        return 'all:MCP AND all:"tool poisoning"'
    if "prompt injection" in text or "提示注入" in text:
        return 'all:MCP AND all:"prompt injection"'
    if "tool injection" in text:
        return 'all:MCP AND all:"tool injection"'
    if "threat model" in text:
        return 'all:MCP AND all:"threat model"'
    if "supply chain" in text or "供应链" in text:
        return 'all:MCP AND all:"supply chain"'
    if "vulnerab" in text or "漏洞" in text:
        return "all:MCP AND all:vulnerability"
    if "attack" in text or "攻击" in text:
        return "all:MCP AND all:attack"
    return 'all:"Model Context Protocol" AND all:security'


def _mcp_text_relevant(value: str) -> bool:
    text = str(value or "").casefold()
    protocol = "model context protocol" in text
    mcp_context = "mcp" in text and any(
        token in text for token in ("agent", "tool", "llm", "server", "client", "协议")
    )
    return (protocol or mcp_context) and _has_security_term(text)


def _mcp_repo_text(repo: Dict[str, Any]) -> str:
    # Owner names such as "kontext-security" would otherwise make every repo
    # from that account look security-related.
    name = str(repo.get("name") or repo.get("full_name") or "").split("/")[-1]
    return " ".join([
        name,
        str(repo.get("description") or ""),
        " ".join(str(topic) for topic in repo.get("topics") or []),
        str(repo.get("language") or ""),
    ]).casefold()


REPO_SECURITY_MARKERS = (
    "security", "attack", "vulnerab", "poison", "injection", "exploit", "threat",
    "risk", "defense", "defence", "guardrail", "sandbox", "permission",
    "authorization", "supply chain", "red team", "malicious", "abuse", "privacy",
    "leak", "unsafe", "audit", "安全", "攻击", "漏洞", "投毒", "注入", "越狱",
    "防御", "防护", "风险", "权限", "授权", "供应链", "恶意", "滥用", "沙箱",
    "审计", "泄露",
)


def _mcp_repo_relevant(repo: Dict[str, Any]) -> bool:
    text = _mcp_repo_text(repo)
    return _contains_mcp(text) and any(marker in text for marker in REPO_SECURITY_MARKERS)


def _mcp_relevance(repo: Dict[str, Any]) -> tuple[int, int, int]:
    text = _mcp_repo_text(repo)
    return (
        sum(marker in text for marker in MCP_MARKERS),
        sum(marker in text for marker in REPO_SECURITY_MARKERS),
        int(repo.get("stargazers_count") or 0),
    )


REPO_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:github|gitlab)\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
    re.IGNORECASE,
)
RESERVED_GITHUB_OWNERS = {
    "about", "features", "login", "marketplace", "orgs", "pricing", "security",
    "settings", "sponsors", "topics",
}


def _extract_repository_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in REPO_URL_RE.finditer(str(text or "")):
        url = match.group(0).rstrip(".,;:)]}'\"")
        if url.casefold().endswith(".git"):
            url = url[:-4]
        owner = url.split("/")[3].casefold() if len(url.split("/")) > 3 else ""
        if owner in RESERVED_GITHUB_OWNERS:
            continue
        if url not in urls:
            urls.append(url)
    return urls


def _paper_id(url: str) -> str:
    value = re.sub(r"[^\w.-]+", "_", str(url or "").rstrip("/").split("/")[-1])
    return value[:80] or "paper"


async def _repository_metadata(url: str, client: httpx.AsyncClient, headers: Dict[str, str]) -> Dict[str, Any]:
    base = {"url": url, "platform": "gitlab" if "gitlab.com" in url else "github"}
    if "github.com" not in url:
        base["full_name"] = "/".join(url.split("/")[3:5])
        return base
    full_name = "/".join(url.split("/")[3:5])
    base["full_name"] = full_name
    try:
        response = await client.get(f"https://api.github.com/repos/{full_name}", headers=headers, timeout=15)
        if response.status_code != 200:
            return base
        repo = response.json()
        return {
            **base,
            "description": repo.get("description") or "",
            "stars": repo.get("stargazers_count") or 0,
            "forks": repo.get("forks_count") or 0,
            "language": repo.get("language") or "",
            "topics": repo.get("topics") or [],
            "license": (repo.get("license") or {}).get("spdx_id") or "",
            "updated_at": repo.get("updated_at") or "",
        }
    except httpx.HTTPError:
        return base


async def _linked_repositories(urls: list[str], client: httpx.AsyncClient, headers: Dict[str, str], limit: int = 2) -> list[Dict[str, Any]]:
    return [await _repository_metadata(url, client, headers) for url in urls[:limit]]


def _academic_max_results(limit: int) -> int:
    configured = int(os.getenv("ACADEMIC_MAX_RESULTS", "200"))
    return max(limit, min(limit * 4, configured))


def _inverted_abstract(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, values in index.items():
        for position in values or []:
            positions.append((int(position), str(word)))
    return " ".join(word for _, word in sorted(positions))


def expanded_research_queries(keywords: list[str]) -> list[tuple[str, str]]:
    """Return (original keyword, actual query), preserving user English terms."""
    queries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for keyword in keywords:
        candidates = [keyword, *RESEARCH_KEYWORD_EXPANSIONS.get(keyword, [])]
        if is_mcp_security_query(keyword):
            candidates.extend(MCP_SECURITY_QUERIES)
        for query in candidates:
            normalized = query.casefold().strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                queries.append((keyword, query))
    return queries


class _ResearchCrawler(AbstractCrawler):
    platform = "research"

    async def launch_browser(self, chromium: BrowserType, playwright_proxy: Optional[Dict], user_agent: Optional[str], headless: bool = True) -> BrowserContext:
        raise NotImplementedError("This public API crawler does not use a browser")

    async def launch_browser_with_cdp(self, playwright: Playwright, playwright_proxy: Optional[Dict], user_agent: Optional[str], headless: bool = True) -> BrowserContext:
        raise NotImplementedError("This public API crawler does not use a browser")

    async def _write(self, item: dict[str, Any], item_type: str = "contents") -> None:
        writer = AsyncFileWriter(platform=self.platform, crawler_type=crawler_type_var.get() or "search")
        await writer.write_to_jsonl(item, item_type)


class GithubCrawler(_ResearchCrawler):
    platform = "github"

    async def start(self) -> None:
        if config.CRAWLER_TYPE != "search":
            utils.logger.warning("GitHub adapter currently supports keyword search only")
            return
        await self.search()

    async def search(self) -> None:
        keywords = [item.strip() for item in config.KEYWORDS.split(",") if item.strip()]
        limit = max(1, min(config.CRAWLER_MAX_NOTES_COUNT, 100))
        token = getattr(config, "GITHUB_TOKEN", "") or ""
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "MediaCrawler"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            seen_repositories: set[str] = set()
            seen_queries: set[str] = set()
            for original_keyword, query in expanded_research_queries(keywords):
                github_query = _github_query(query)
                if github_query in seen_queries:
                    continue
                seen_queries.add(github_query)
                source_keyword_var.set(query)
                try:
                    response = await client.get("https://api.github.com/search/repositories", params={"q": github_query, "sort": "stars", "order": "desc", "per_page": min(limit, 100)})
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    utils.logger.warning(f"[github] query failed for {query!r}: {exc}")
                    await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
                    continue
                repos = response.json().get("items", [])
                if is_mcp_security_query(original_keyword) or is_mcp_security_query(query):
                    repos = [repo for repo in repos if _mcp_repo_relevant(repo)]
                    repos.sort(key=_mcp_relevance, reverse=True)
                for repo in repos[:limit]:
                    repo_id = str(repo.get("id") or repo.get("full_name") or "")
                    if not repo_id or repo_id in seen_repositories:
                        continue
                    seen_repositories.add(repo_id)
                    await self._write({
                        "record_type": "repository", "source_platform": "github",
                        "platform": "github", "title": repo.get("full_name", ""),
                        "content": repo.get("description") or "", "description": repo.get("description") or "",
                        "author": (repo.get("owner") or {}).get("login", ""), "url": repo.get("html_url", ""),
                        "stars": repo.get("stargazers_count", 0), "forks": repo.get("forks_count", 0),
                        "language": repo.get("language") or "", "topics": repo.get("topics") or [],
                        "published_at": repo.get("created_at") or "", "updated_at": repo.get("updated_at") or "",
                        "original_keyword": original_keyword, "actual_query": query,
                    }, "repositories")
                await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)


class ArxivCrawler(_ResearchCrawler):
    platform = "arxiv"

    async def start(self) -> None:
        if config.CRAWLER_TYPE != "search":
            utils.logger.warning("arXiv adapter currently supports keyword search only")
            return
        await self.search()

    async def search(self) -> None:
        keywords = [item.strip() for item in config.KEYWORDS.split(",") if item.strip()]
        limit = max(1, min(config.CRAWLER_MAX_NOTES_COUNT, 100))
        max_results = _academic_max_results(limit)
        writer = AsyncFileWriter(platform=self.platform, crawler_type=crawler_type_var.get() or "search")
        repo_headers = {"Accept": "application/vnd.github+json", "User-Agent": "MediaCrawler/1.0 linked-repository lookup"}
        token = getattr(config, "GITHUB_TOKEN", "") or ""
        if token:
            repo_headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=40, headers={"User-Agent": "MediaCrawler/1.0 research search"}) as client:
            seen_papers: set[str] = set()
            seen_expressions: set[str] = set()
            written = 0
            for original_keyword, query in expanded_research_queries(keywords):
                expression = _arxiv_expression(query)
                if expression in seen_expressions:
                    continue
                seen_expressions.add(expression)
                mcp_query = is_mcp_security_query(original_keyword) or is_mcp_security_query(query)
                page_size = min(limit * 3, 100) if mcp_query else limit
                max_pages = 2 if mcp_query else 1
                max_pages = max(1, min(max_pages, int(os.getenv("ARXIV_MAX_PAGES", "2"))))
                source_keyword_var.set(query)
                for page in range(max_pages):
                    try:
                        response = await client.get("https://export.arxiv.org/api/query", params={"search_query": expression, "start": page * page_size, "max_results": page_size, "sortBy": "relevance", "sortOrder": "descending"})
                        response.raise_for_status()
                    except httpx.HTTPError as exc:
                        utils.logger.warning(f"[arxiv] query failed for {query!r}: {exc}")
                        break
                    entries = re.findall(r"<entry>(.*?)</entry>", response.text, flags=re.DOTALL)
                    if not entries:
                        break
                    for entry in entries:
                        title = self._tag(entry, "title")
                        abstract = " ".join(self._tag(entry, "summary").split())
                        comment = self._tag(entry, "arxiv:comment")
                        if mcp_query and not _mcp_text_relevant(f"{title} {abstract}"):
                            continue
                        link = self._link(entry)
                        if not link or link in seen_papers:
                            continue
                        seen_papers.add(link)
                        authors = re.findall(r"<author>.*?<name>(.*?)</name>.*?</author>", entry, flags=re.DOTALL)
                        author_names = ", ".join(html.unescape(name.strip()) for name in authors)
                        published_at = self._tag(entry, "published")
                        paper_id = _paper_id(link)
                        linked = await _linked_repositories(_extract_repository_urls(f"{title} {abstract} {comment}"), client, repo_headers)
                        record = {
                            "record_type": "paper", "source_platform": "arxiv",
                            "platform": "arxiv", "paper_id": paper_id,
                            "title": title, "content": abstract, "abstract": abstract, "comment": comment,
                            "author": author_names, "url": link, "pdf_url": self._pdf_link(entry),
                            "categories": re.findall(r"<category term=\"([^\"]+)\"", entry),
                            "published_at": published_at, "updated_at": self._tag(entry, "updated"),
                            "linked_repositories": linked,
                            "original_keyword": original_keyword, "actual_query": query,
                        }
                        await writer.write_to_jsonl(record, "papers")
                        if linked:
                            await writer.write_linked_paper(paper_id, {
                                "paper": {"paper_id": paper_id, "platform": "arxiv", "title": title, "url": link, "published_at": published_at, "authors": author_names},
                                "repositories": linked,
                            })
                        written += 1
                        if written >= max_results:
                            return
                    await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)

    @staticmethod
    def _tag(entry: str, tag: str) -> str:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", entry, flags=re.DOTALL)
        return html.unescape(re.sub(r"\s+", " ", match.group(1)).strip()) if match else ""

    @staticmethod
    def _link(entry: str) -> str:
        match = re.search(r'<id>(.*?)</id>', entry, flags=re.DOTALL)
        return html.unescape(match.group(1).strip()) if match else ""

    @staticmethod
    def _pdf_link(entry: str) -> str:
        for tag in re.findall(r"<link\b[^>]*>", entry):
            if 'title="pdf"' not in tag:
                continue
            href = re.search(r'href="([^"]+)"', tag)
            if href:
                return html.unescape(href.group(1))
        return ""


class OpenAlexCrawler(_ResearchCrawler):
    platform = "openalex"

    async def start(self) -> None:
        if config.CRAWLER_TYPE != "search":
            utils.logger.warning("OpenAlex adapter currently supports keyword search only")
            return
        await self.search()

    async def search(self) -> None:
        keywords = [item.strip() for item in config.KEYWORDS.split(",") if item.strip()]
        limit = max(1, min(config.CRAWLER_MAX_NOTES_COUNT, 100))
        max_results = _academic_max_results(limit)
        mailto = os.getenv("OPENALEX_MAILTO", "").strip()
        writer = AsyncFileWriter(platform=self.platform, crawler_type=crawler_type_var.get() or "search")
        repo_headers = {"Accept": "application/vnd.github+json", "User-Agent": "MediaCrawler/1.0 linked-repository lookup"}
        token = getattr(config, "GITHUB_TOKEN", "") or ""
        if token:
            repo_headers["Authorization"] = f"Bearer {token}"
        headers = {"User-Agent": "MediaCrawler/1.0 OpenAlex search"}
        async with httpx.AsyncClient(timeout=40, headers=headers) as client:
            seen_works: set[str] = set()
            written = 0
            for original_keyword, query in expanded_research_queries(keywords):
                mcp_query = is_mcp_security_query(original_keyword) or is_mcp_security_query(query)
                page_size = min(max(limit * 3, 25), 100) if mcp_query else limit
                max_pages = 2 if mcp_query else 1
                max_pages = max(1, min(max_pages, int(os.getenv("OPENALEX_MAX_PAGES", "2"))))
                source_keyword_var.set(query)
                for page in range(max_pages):
                    params = {"search": query, "per-page": page_size, "page": page + 1}
                    if mailto:
                        params["mailto"] = mailto
                    try:
                        response = await client.get("https://api.openalex.org/works", params=params)
                        response.raise_for_status()
                    except httpx.HTTPError as exc:
                        utils.logger.warning(f"[openalex] query failed for {query!r}: {exc}")
                        break
                    works = response.json().get("results", [])
                    if not works:
                        break
                    for work in works:
                        title = str(work.get("display_name") or "").strip()
                        abstract = _inverted_abstract(work.get("abstract_inverted_index"))
                        if not title or (mcp_query and not _mcp_text_relevant(f"{title} {abstract}")):
                            continue
                        primary = work.get("primary_location") or {}
                        best_oa = work.get("best_oa_location") or {}
                        url = str(work.get("doi") or primary.get("landing_page_url") or work.get("id") or "").strip()
                        if not url or url in seen_works:
                            continue
                        seen_works.add(url)
                        paper_id = _paper_id(work.get("id") or url)
                        authors = ", ".join(
                            str((authorship.get("author") or {}).get("display_name") or "").strip()
                            for authorship in (work.get("authorships") or [])[:12]
                            if (authorship.get("author") or {}).get("display_name")
                        )
                        published_at = str(work.get("publication_date") or work.get("publication_year") or "")
                        linked = await _linked_repositories(_extract_repository_urls(f"{title} {abstract}"), client, repo_headers)
                        record = {
                            "record_type": "paper", "source_platform": "openalex",
                            "platform": "openalex", "paper_id": paper_id,
                            "title": title, "content": abstract, "abstract": abstract,
                            "author": authors, "url": url, "doi": work.get("doi") or "",
                            "pdf_url": best_oa.get("pdf_url") or primary.get("pdf_url") or "",
                            "venue": ((primary.get("source") or {}).get("display_name") or ""),
                            "cited_by_count": work.get("cited_by_count") or 0,
                            "published_at": published_at,
                            "topics": [str(topic.get("display_name") or "") for topic in (work.get("topics") or []) if topic.get("display_name")],
                            "open_access": bool((work.get("open_access") or {}).get("is_oa")),
                            "linked_repositories": linked,
                            "original_keyword": original_keyword, "actual_query": query,
                        }
                        await writer.write_to_jsonl(record, "papers")
                        if linked:
                            await writer.write_linked_paper(paper_id, {
                                "paper": {"paper_id": paper_id, "platform": "openalex", "title": title, "url": url, "published_at": published_at, "authors": authors, "doi": work.get("doi") or ""},
                                "repositories": linked,
                            })
                        written += 1
                        if written >= max_results:
                            return
                    await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
