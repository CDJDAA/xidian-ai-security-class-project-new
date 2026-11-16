# -*- coding: utf-8 -*-
import os

import pytest
from fastapi.testclient import TestClient

import api.routers.data as data_router
import pipeline.analysis_service as analysis_service
from api.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(data_router, "_env_path", lambda: tmp_path / ".env")
    for key in ("AI_API_KEY", "AI_BASE_URL", "AI_MODEL", "AI_BATCH_SIZE", "AI_ENRICH_ITEMS"):
        monkeypatch.setenv(key, os.getenv(key, ""))
    return TestClient(app)


def test_config_masks_key_and_persists_to_env(client, tmp_path):
    response = client.put("/api/data/analysis-config", json={
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1/",
        "api_key": "sk-test-1234567890abcd",
        "batch_size": 25,
        "enrich_items": True,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key_set"] is True
    assert payload["api_key_masked"] == "sk-****abcd"
    assert "sk-test-1234567890abcd" not in response.text
    assert payload["base_url"] == "https://api.deepseek.com/v1"
    assert payload["batch_size"] == 25
    assert payload["enrich_items"] is True

    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "AI_API_KEY=sk-test-1234567890abcd" in env_text
    assert "AI_BATCH_SIZE=25" in env_text
    assert os.environ["AI_ENRICH_ITEMS"] == "1"

    again = client.get("/api/data/analysis-config").json()
    assert again["api_key_masked"] == "sk-****abcd"
    assert again["model"] == "deepseek-chat"


def test_config_keeps_key_when_omitted(client, tmp_path):
    client.put("/api/data/analysis-config", json={"api_key": "sk-keep-1234567890abcd"})
    response = client.put("/api/data/analysis-config", json={"model": "deepseek-reasoner"})
    assert response.status_code == 200
    assert response.json()["api_key_set"] is True
    assert "AI_API_KEY=sk-keep-1234567890abcd" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_config_rejects_invalid_base_url(client):
    response = client.put("/api/data/analysis-config", json={"base_url": "ftp://example.com"})
    assert response.status_code == 400


def test_config_rejects_out_of_range_batch_size(client):
    response = client.put("/api/data/analysis-config", json={"batch_size": 5})
    assert response.status_code == 422


def test_connection_test_without_key(client):
    response = client.post("/api/data/analysis-config/test", json={})
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_connection_test_success_with_stub(client, monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "pong"}}]}

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(data_router.httpx, "AsyncClient", FakeClient)
    response = client.post("/api/data/analysis-config/test", json={"api_key": "sk-test", "model": "deepseek-chat"})
    payload = response.json()
    assert payload["ok"] is True
    assert payload["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_batch_errors_are_reported(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "sk-test")

    async def failing_batch(items, number):
        return {"error": "HTTP 401"}

    monkeypatch.setattr(analysis_service, "_summarize_batch", failing_batch)
    entries = await analysis_service._summarize_batches([{"title": "t", "text": "x"}] * 12)
    assert entries and all(entry.get("error") for entry in entries)


@pytest.mark.asyncio
async def test_enrich_items_marks_successful_ai(monkeypatch):
    async def fake_enrich(item):
        return {**item, "analysis_method": "ai", "summary": "ai summary"}

    monkeypatch.setattr(analysis_service, "_ai_enrich", fake_enrich)
    items = [{"title": "a", "quality_score": 0.2}, {"title": "b", "quality_score": 0.9}]
    enriched, count = await analysis_service._enrich_items(items, 1)
    assert count == 1
    assert enriched[1]["analysis_method"] == "ai"
    assert enriched[0].get("analysis_method") != "ai"
