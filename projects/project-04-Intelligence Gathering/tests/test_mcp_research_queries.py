# -*- coding: utf-8 -*-
from media_platform.research.core import (
    _arxiv_expression,
    _github_query,
    _mcp_repo_relevant,
    _mcp_text_relevant,
    expanded_research_queries,
)
from pipeline.topic_taxonomy import canonical_topic


def test_mcp_security_keyword_expands_to_focused_queries():
    queries = [query for _, query in expanded_research_queries(["MCP 安全"])]

    assert queries[0] == "MCP 安全"
    assert "Model Context Protocol security" in queries
    assert "MCP tool poisoning" in queries
    assert "MCP prompt injection" in queries
    assert len(queries) == len(set(query.casefold() for query in queries))


def test_generic_mcp_keyword_stays_generic():
    queries = [query for _, query in expanded_research_queries(["MCP"])]

    assert "Model Context Protocol" in queries
    assert "MCP tool poisoning" not in queries


def test_github_mcp_query_uses_topic_specific_scopes():
    assert _github_query("MCP security") == "mcp in:name security"
    assert _github_query("MCP tool poisoning") == 'mcp in:name,description "tool poisoning"'
    assert _github_query("Model Context Protocol security") == "mcp in:name security"
    assert _github_query("prompt injection") == "prompt injection"


def test_arxiv_mcp_queries_are_topic_specific():
    assert _arxiv_expression("MCP tool poisoning") == 'all:MCP AND all:"tool poisoning"'
    assert _arxiv_expression("MCP prompt injection") == 'all:MCP AND all:"prompt injection"'
    assert _arxiv_expression("MCP 安全") == 'all:"Model Context Protocol" AND all:security'


def test_mcp_relevance_requires_security_context():
    assert _mcp_text_relevant("We attack an MCP server through tool poisoning.")
    assert not _mcp_text_relevant("A tutorial for building an MCP server with Python.")
    assert _mcp_repo_relevant({
        "full_name": "example/mcp-security-scanner",
        "description": "Detect MCP tool poisoning and prompt injection",
        "topics": ["mcp", "security"],
    })
    assert not _mcp_repo_relevant({
        "full_name": "example/mcp-demo",
        "description": "A demo MCP server for learning",
        "topics": ["mcp"],
    })
    assert not _mcp_repo_relevant({
        "full_name": "example/mssql_mcp_server",
        "description": "MCP server for secure database access",
        "topics": ["mcp"],
    })
    assert not _mcp_repo_relevant({
        "name": "browser-use-mcp-server",
        "full_name": "kontext-security/browser-use-mcp-server",
        "description": "Browse the web directly from Cursor",
        "topics": ["mcp"],
    })


def test_mcp_taxonomy_has_a_stable_topic():
    topic = canonical_topic("MCP 安全")

    assert topic["id"] == "ai-safety.mcp-tool-protocol"
    assert topic["label"] == "MCP 与工具协议安全"
