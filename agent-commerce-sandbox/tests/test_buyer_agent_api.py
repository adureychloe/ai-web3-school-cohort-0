"""Tests for the Buyer Agent API.

These tests describe the desired /api/agent/buyer/procure behavior.  All
external dependencies are monkeypatched so the endpoint can be exercised without
CAW, on-chain, or network calls.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import web.app as app_module


SETH = 10**18
BUYER_WALLET = "0x1234567890abcdef1234567890abcdef12345678"


@pytest.fixture()
def calls() -> SimpleNamespace:
    return SimpleNamespace(list_services=0, match_and_rank=[], get_balance=0, x402_buy=[])


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, calls: SimpleNamespace) -> TestClient:
    """Patch all Buyer Agent dependencies and return a TestClient."""
    services = [
        {
            "id": 101,
            "name": "Premium Market Analyst",
            "description": "Deep market analysis but over this buyer's budget",
            "priceWei": 8 * SETH,
            "active": True,
            "protocol": "x402",
            "paymentAddress": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "chainId": "SETH",
            "tokenId": "SETH",
            "endpointURI": "http://seller.test/premium",
        },
        {
            "id": 202,
            "name": "Budget Market Analyst",
            "description": "Affordable market research and analysis",
            "priceWei": 2 * SETH,
            "active": True,
            "protocol": "x402",
            "paymentAddress": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "chainId": "SETH",
            "tokenId": "SETH",
            "endpointURI": "http://seller.test/budget",
        },
        {
            "id": 303,
            "name": "Translation Helper",
            "description": "Affordable translation service with lower relevance",
            "priceWei": 1 * SETH,
            "active": True,
            "protocol": "x402",
            "paymentAddress": "0xcccccccccccccccccccccccccccccccccccccccc",
            "chainId": "SETH",
            "tokenId": "SETH",
            "endpointURI": "http://seller.test/translate",
        },
    ]

    async def fake_list_v2_services() -> list[dict]:
        calls.list_services += 1
        return services

    def fake_match_and_rank(request: str, service_list: list[dict]) -> tuple[list[tuple[int, dict]], str]:
        calls.match_and_rank.append(
            {
                "request": request,
                "service_ids": [service["id"] for service in service_list],
            }
        )
        scores = {101: 99, 202: 91, 303: 20}
        ranked = sorted(
            ((scores[service["id"]], service) for service in service_list),
            key=lambda item: (-item[0], item[1]["id"]),
        )
        return ranked, "test_matcher"

    def fake_get_balance() -> dict:
        calls.get_balance += 1
        return {"amount": "12.5", "address": BUYER_WALLET}

    async def fake_api_x402_buy(payload) -> dict:
        calls.x402_buy.append(payload)
        return {
            "status": "delivered",
            "purchase": {
                "service_id": payload.service_id,
                "query": payload.query,
                "wallet_address": payload.wallet_address,
                "tx_hash": "0xfeedface",
            },
            "timeline": [
                {"step": "matched", "status": "ok"},
                {"step": "x402_buy", "status": "ok"},
            ],
        }

    monkeypatch.setattr(app_module, "_list_v2_services", fake_list_v2_services)
    monkeypatch.setattr(app_module, "match_and_rank", fake_match_and_rank)
    monkeypatch.setattr(app_module, "get_balance", fake_get_balance)
    monkeypatch.setattr(app_module, "api_x402_buy", fake_api_x402_buy)

    return TestClient(app_module.app)


def _post_procure(client: TestClient, *, budget_seth: str = "3", auto_pay: bool = False):
    return client.post(
        "/api/agent/buyer/procure",
        json={
            "request": "Find market analysis for an AI commerce launch",
            "budget_seth": budget_seth,
            "wallet_address": BUYER_WALLET,
            "auto_pay": auto_pay,
        },
    )


def _price_seth(candidate: dict) -> Decimal:
    if "price_seth" in candidate:
        return Decimal(str(candidate["price_seth"]))
    if "price_eth" in candidate:
        return Decimal(str(candidate["price_eth"]))
    return Decimal(candidate["priceWei"]) / Decimal(SETH)


def test_buyer_agent_procure_matches_without_auto_pay(
    client: TestClient, calls: SimpleNamespace
) -> None:
    response = _post_procure(client, budget_seth="3", auto_pay=False)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "matched"
    assert body["agent"] == "buyer"

    assert body["decision"]["service_id"] == 202
    assert body["decision"]["service_name"] == "Budget Market Analyst"
    assert body["decision"]["score"] == 91
    assert isinstance(body["decision"]["reason"], str)
    assert "budget" in body["decision"]["reason"].lower()

    assert body["candidates"]
    assert body["candidates"][0]["id"] == 202
    assert body["candidates"][0]["name"] == "Budget Market Analyst"
    assert body["candidates"][0]["score"] == 91

    assert body["budget"]["requested_seth"] == "3"
    assert body["budget"]["wallet_address"] == BUYER_WALLET
    assert body["budget"]["balance"]["amount"] == "12.5"

    assert calls.list_services == 1
    assert calls.get_balance == 1
    assert calls.x402_buy == []


def test_buyer_agent_filters_over_budget_and_selects_best_affordable_service(
    client: TestClient, calls: SimpleNamespace
) -> None:
    response = _post_procure(client, budget_seth="3", auto_pay=False)

    assert response.status_code == 200
    body = response.json()

    # Service 101 has the highest match score, but costs 8 SETH and must be
    # excluded for a 3 SETH budget.  Service 202 is the best affordable x402 V2
    # candidate and should be selected.
    assert body["decision"]["service_id"] == 202
    assert body["decision"]["service_name"] == "Budget Market Analyst"
    assert body["decision"]["score"] == 91

    candidate_ids = [candidate["id"] for candidate in body["candidates"]]
    assert 101 not in candidate_ids
    assert candidate_ids == [202, 303]
    assert all(_price_seth(candidate) <= Decimal("3") for candidate in body["candidates"])

    # Matching should be performed only on services that survived budget
    # filtering, so the over-budget service is never offered to the ranker.
    assert calls.match_and_rank == [
        {
            "request": "Find market analysis for an AI commerce launch",
            "service_ids": [202, 303],
        }
    ]


def test_buyer_agent_auto_pay_delegates_to_x402_buy_and_returns_purchase_status(
    client: TestClient, calls: SimpleNamespace
) -> None:
    response = _post_procure(client, budget_seth="3", auto_pay=True)

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "delivered"
    assert body["agent"] == "buyer"
    assert body["decision"]["service_id"] == 202
    assert body["decision"]["service_name"] == "Budget Market Analyst"
    assert body["decision"]["score"] == 91
    assert body["timeline"] == [
        {"step": "matched", "status": "ok"},
        {"step": "x402_buy", "status": "ok"},
    ]
    assert body["purchase"]["service_id"] == 202
    assert body["purchase"]["query"] == "Find market analysis for an AI commerce launch"
    assert body["purchase"]["wallet_address"] == BUYER_WALLET

    assert len(calls.x402_buy) == 1
    buy_payload = calls.x402_buy[0]
    assert buy_payload.service_id == 202
    assert buy_payload.query == "Find market analysis for an AI commerce launch"
    assert buy_payload.wallet_address == BUYER_WALLET
    assert buy_payload.max_price_wei == 3 * SETH


def test_x402_buy_blocking_rejects_payment_above_max_price_before_caw_transfer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeHTTPError(Exception):
        def __init__(self, code: int, body: dict):
            super().__init__(code)
            self.code = code
            self._body = body

        def read(self) -> bytes:
            import json

            return json.dumps(self._body).encode()

    class FakeUrlLibRequestModule:
        @staticmethod
        def Request(url, data=None, headers=None, method=None):
            return SimpleNamespace(url=url, data=data, headers=headers, method=method)

        @staticmethod
        def urlopen(req, timeout=0):
            raise FakeHTTPError(
                402,
                {
                    "payment": {
                        "amount": "4",
                        "token_id": "SETH",
                        "chain_id": "SETH",
                        "address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    }
                },
            )

    class FakeUrlLibPackage:
        request = FakeUrlLibRequestModule

    class FakeHTTPErrorModule:
        HTTPError = FakeHTTPError

    caw_calls = SimpleNamespace(
        submit_pact=0,
        execute_transfer=0,
        find_active_x402_pact=0,
        get_pact=0,
    )

    class FakeCawClient:
        wallet_address = BUYER_WALLET

        def submit_pact(self, *args, **kwargs):
            caw_calls.submit_pact += 1
            return {"pact_id": "pact", "status": "active"}

        def execute_transfer(self, *args, **kwargs):
            caw_calls.execute_transfer += 1
            return {"id": "tx"}

        def find_active_x402_pact(self, *args, **kwargs):
            caw_calls.find_active_x402_pact += 1
            return None

        def get_pact(self, *args, **kwargs):
            caw_calls.get_pact += 1
            return {}

    class FakeX402Client:
        def list_services(self):
            return [
                {
                    "id": 202,
                    "name": "Budget Market Analyst",
                    "price": "2",
                    "token": "SETH",
                    "chain": "SETH",
                    "address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "endpoint": "http://seller.test",
                }
            ]

        def _resolve_request_url(self, service):
            return "http://seller.test/request"

    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "urllib.request":
            return FakeUrlLibPackage
        if name == "urllib.error":
            return FakeHTTPErrorModule
        if name == "urllib":
            return FakeUrlLibPackage
        if name == "agent_commerce_sandbox.x402_client":
            return SimpleNamespace(X402Client=FakeX402Client)
        if name == "agent_commerce_sandbox.caw_client":
            return SimpleNamespace(CawClient=FakeCawClient, PactTerminalStatusError=RuntimeError)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.setattr(app_module, "_x402_pact_id", None)

    with pytest.raises(app_module.HTTPException) as exc_info:
        app_module._api_x402_buy_blocking(
            app_module.X402BuyRequest(
                service_id=202,
                query="Find market analysis for an AI commerce launch",
                wallet_address=BUYER_WALLET,
                max_price_wei=3 * SETH,
            )
        )

    assert exc_info.value.status_code == 409
    assert "exceeds max_price_wei" in exc_info.value.detail
    assert "CAW transfer not submitted" in exc_info.value.detail
    assert caw_calls.find_active_x402_pact == 0
    assert caw_calls.submit_pact == 0
    assert caw_calls.execute_transfer == 0
