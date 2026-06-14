"""Tests for the desired Seller Agent registration API.

These tests define the missing ``POST /api/agent/seller/register`` behavior.
All registration dependencies are monkeypatched so the API can be exercised
without CAW, on-chain, or network calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web.app as app_module


SELLER_ADDRESS = "0x1111111111111111111111111111111111111111"
VALID_REGISTER_REQUEST = {
    "service_brief": "Sell a concise weekly AI x Web3 market intelligence report for hackathon teams",
    "seller_address": SELLER_ADDRESS,
    "price_seth": "0.0025",
    "endpoint_uri": "https://seller.example.com",
    "category": "market intelligence",
}


def _as_mapping(value: Any) -> dict[str, Any]:
    """Best-effort conversion for dicts, Pydantic models, and namespaces."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump())
    if hasattr(value, "dict"):
        return dict(value.dict())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _extract_service_payload(call: dict[str, Any]) -> dict[str, Any]:
    """Find the generated service metadata passed to the registration wrapper."""
    kwargs = dict(call.get("kwargs") or {})
    for key in ("service", "metadata", "service_metadata", "payload", "request"):
        if key in kwargs:
            candidate = _as_mapping(kwargs[key])
            if candidate:
                return candidate

    service_keys = {"name", "description", "price_seth", "payment_address", "seller_address", "endpoint_uri"}
    if service_keys.intersection(kwargs):
        return kwargs

    for arg in call.get("args") or ():
        candidate = _as_mapping(arg)
        if candidate and service_keys.intersection(candidate):
            return candidate

    return kwargs


@pytest.fixture()
def registration_calls() -> list[dict[str, Any]]:
    return []


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, registration_calls: list[dict[str, Any]]) -> TestClient:
    """Patch the expected Seller Agent registration wrapper(s)."""

    async def fake_register_v2_service_from_agent(*args: Any, **kwargs: Any) -> dict[str, Any]:
        registration_calls.append({"args": args, "kwargs": kwargs})
        service = _extract_service_payload(registration_calls[-1])
        payment_address = (service.get("payment_address") or service.get("seller_address") or SELLER_ADDRESS).lower()
        return {
            "status": "registered",
            "tx_hash": "0xselleragent",
            "service_id": 4242,
            "service": {
                "name": service.get("name") or "AI Web3 Market Intelligence Report",
                "description": service.get("description") or VALID_REGISTER_REQUEST["service_brief"],
                "price_seth": str(service.get("price_seth") or VALID_REGISTER_REQUEST["price_seth"]),
                "payment_address": payment_address,
                "endpoint_uri": service.get("endpoint_uri") or VALID_REGISTER_REQUEST["endpoint_uri"],
                "category": service.get("category") or VALID_REGISTER_REQUEST["category"],
            },
        }

    # The endpoint does not exist yet.  These names document the expected seam
    # the implementation should call instead of touching x402/on-chain directly.
    monkeypatch.setattr(
        app_module,
        "register_v2_service_from_agent",
        fake_register_v2_service_from_agent,
        raising=False,
    )
    monkeypatch.setattr(
        app_module,
        "_register_v2_service_from_agent",
        fake_register_v2_service_from_agent,
        raising=False,
    )

    return TestClient(app_module.app)


def test_seller_agent_register_generates_metadata_and_registers_v2_service(
    client: TestClient,
    registration_calls: list[dict[str, Any]],
) -> None:
    response = client.post("/api/agent/seller/register", json=VALID_REGISTER_REQUEST)

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "registered"
    assert body["agent"] == "seller"

    service = body["service"]
    assert isinstance(service["name"], str)
    assert service["name"].strip()
    assert any(term in service["name"].lower() for term in ("market", "intelligence", "ai", "web3"))
    assert isinstance(service["description"], str)
    assert service["description"].strip()
    assert "weekly" in service["description"].lower() or "hackathon" in service["description"].lower()
    assert service["price_seth"] == "0.0025"
    assert service["payment_address"] == SELLER_ADDRESS.lower()
    assert service["endpoint_uri"] == "https://seller.example.com"

    assert body["registration"]["tx_hash"] == "0xselleragent"
    timeline_steps = [item["step"] for item in body["timeline"]]
    assert "parsed_brief" in timeline_steps
    assert "built_metadata" in timeline_steps
    assert "registered_v2" in timeline_steps

    assert len(registration_calls) == 1
    generated = _extract_service_payload(registration_calls[0])
    assert generated["price_seth"] == "0.0025"
    assert generated["endpoint_uri"] == "https://seller.example.com"
    assert (generated.get("payment_address") or generated.get("seller_address")) == SELLER_ADDRESS.lower()
    assert generated["description"].strip()
    assert any(term in generated["name"].lower() for term in ("market", "intelligence", "ai", "web3"))


def test_seller_agent_register_honors_demo_admin_token_gate(
    client: TestClient,
    registration_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_ADMIN_TOKEN", "seller-secret")

    blocked = client.post("/api/agent/seller/register", json=VALID_REGISTER_REQUEST)
    assert blocked.status_code == 403
    assert registration_calls == []

    allowed = client.post(
        "/api/agent/seller/register",
        json=VALID_REGISTER_REQUEST,
        headers={"X-Demo-Admin-Token": "seller-secret"},
    )
    assert allowed.status_code == 200
    assert len(registration_calls) == 1


@pytest.mark.parametrize(
    "payload_update",
    [
        pytest.param({"seller_address": None}, id="missing-seller-address"),
        pytest.param({"endpoint_uri": "not-a-url"}, id="invalid-endpoint-uri"),
        pytest.param({"price_seth": "0"}, id="zero-price"),
    ],
)
def test_seller_agent_register_validation_rejects_bad_requests_before_registration(
    client: TestClient,
    registration_calls: list[dict[str, Any]],
    payload_update: dict[str, Any],
) -> None:
    payload = dict(VALID_REGISTER_REQUEST)
    if payload_update.get("seller_address") is None:
        payload.pop("seller_address")
    else:
        payload.update(payload_update)

    response = client.post("/api/agent/seller/register", json=payload)

    assert response.status_code in {400, 422}
    assert registration_calls == []
