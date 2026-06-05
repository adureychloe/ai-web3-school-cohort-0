"""
Cobo Agentic Wallet API client.

Two modes:
  - REAL mode (COBO_API_KEY + COBO_WALLET_ID set): calls real Cobo API
  - SIM mode (no key): returns mock responses shaped like real Cobo API

Switching only requires setting .env variables.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError


# ── Data classes ──────────────────────────────────────────────

@dataclass
class CoboPactResult:
    success: bool
    pact_id: str
    status: str  # "ACTIVE" | "PENDING_APPROVAL" | "DENIED" | "COMPLETED"
    wallet_id: str
    created_at: str
    mode: str  # "cobo" | "simulated"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CoboTransferResult:
    success: bool
    transaction_id: str
    status: str  # "completed" | "pending_approval" | "failed"
    amount: str
    token_id: str
    to_address: str
    tx_hash: Optional[str]
    mode: str  # "cobo" | "simulated"
    request_id: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ── Client ────────────────────────────────────────────────────

class CoboClient:
    """Cobo Agentic Wallet API client with dual mode."""

    BASE_URL = "https://api.cobo.com"

    def __init__(self):
        self.api_key = os.environ.get("COBO_API_KEY", "").strip()
        self.wallet_id = os.environ.get("COBO_WALLET_ID", "").strip()
        self.base_url = os.environ.get("COBO_API_BASE", self.BASE_URL).rstrip("/")
        self.is_real = bool(self.api_key and self.wallet_id)

    @property
    def mode(self) -> str:
        return "cobo" if self.is_real else "simulated"

    # ── Public API ──────────────────────────────────────────

    def submit_pact(
        self,
        intent: str,
        service_name: str,
        amount: str,
        token_id: str,
        chain_id: str,
        to_address: str,
        execution_plan: str = "",
    ) -> CoboPactResult:
        """Submit a pact to Cobo for execution authorization.

        REAL mode: POST /api/v1/pacts/submit
        SIM mode: return mock with same field structure.
        """
        if self.is_real:
            return self._real_submit_pact(intent, service_name, amount, token_id,
                                           chain_id, to_address, execution_plan)
        return self._sim_submit_pact(intent, service_name, amount, token_id,
                                     chain_id, to_address)

    def execute_transfer(
        self,
        pact_id: str,
        to_address: str,
        amount: str,
        token_id: str,
        chain_id: str,
        request_id: Optional[str] = None,
    ) -> CoboTransferResult:
        """Execute a token transfer through Cobo under an active pact.

        REAL mode: POST /api/v1/wallets/{wallet_uuid}/transfer
        SIM mode: return mock with same field structure.
        """
        if self.is_real:
            return self._real_execute_transfer(pact_id, to_address, amount,
                                                token_id, chain_id, request_id)
        return self._sim_execute_transfer(pact_id, to_address, amount,
                                          token_id, chain_id, request_id)

    def get_wallet_balance(self, token_id: Optional[str] = None) -> dict:
        """Query wallet balance. SIM mode returns mock."""
        if self.is_real:
            return self._real_get_balance(token_id)
        return self._sim_get_balance(token_id)

    def list_audit_logs(self, limit: int = 20) -> list:
        """List audit logs. SIM mode returns mock."""
        if self.is_real:
            return self._real_list_audit_logs(limit)
        return self._sim_list_audit_logs(limit)

    def get_pact_status(self, pact_id: str) -> dict:
        """Query pact status. SIM mode returns mock."""
        if self.is_real:
            return self._real_get_pact(pact_id)
        return self._sim_get_pact(pact_id)

    # ── Real mode implementations ────────────────────────────

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _api_post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode()
        req = Request(url, data=data, headers=self._headers(), method="POST")
        try:
            resp = urlopen(req, timeout=30)
            return json.loads(resp.read().decode())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            return {"success": False, "error": error_body, "status_code": e.code}

    def _api_get(self, path: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            url = f"{url}?{qs}"
        req = Request(url, headers=self._headers(), method="GET")
        try:
            resp = urlopen(req, timeout=30)
            return json.loads(resp.read().decode())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            return {"success": False, "error": error_body, "status_code": e.code}

    def _real_submit_pact(self, intent, service_name, amount, token_id,
                          chain_id, to_address, execution_plan):
        body = {
            "wallet_id": self.wallet_id,
            "intent": intent,
            "spec": {
                "policies": [
                    {
                        "name": f"pay-{service_name.lower().replace(' ', '-')}",
                        "type": "transfer",
                        "rules": {
                            "effect": "allow",
                            "when": {
                                "chain_in": [chain_id],
                                "token_in": [
                                    {"chain_id": chain_id, "token_id": token_id}
                                ],
                                "destination_address_in": [
                                    {"chain_id": chain_id, "address": to_address}
                                ],
                            },
                            "deny_if": {"amount_usd_gt": str(amount)},
                        },
                    }
                ],
                "completion_conditions": [
                    {"type": "tx_count", "threshold": "1"},
                    {"type": "time_elapsed", "threshold": "3600"},
                ],
                "execution_plan": execution_plan or (
                    f"1. Call {service_name}\n"
                    f"2. Verify delivery\n"
                    f"3. Release payment via Cobo transfer"
                ),
            },
        }
        resp = self._api_post("/api/v1/pacts/submit", body)
        if resp.get("success"):
            r = resp["result"]
            return CoboPactResult(
                success=True,
                pact_id=r.get("pact_id", ""),
                status=r.get("status", "PENDING_APPROVAL"),
                wallet_id=self.wallet_id,
                created_at=r.get("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                mode="cobo",
            )
        return CoboPactResult(
            success=False,
            pact_id="",
            status="FAILED",
            wallet_id=self.wallet_id,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            mode="cobo",
            error=resp.get("error", "Unknown Cobo API error"),
        )

    def _real_execute_transfer(self, pact_id, to_address, amount,
                               token_id, chain_id, request_id):
        body = {
            "to_address": to_address,
            "amount": str(amount),
            "token_id": token_id,
            "chain_id": chain_id,
        }
        if request_id:
            body["request_id"] = request_id

        resp = self._api_post(f"/api/v1/wallets/{self.wallet_id}/transfer", body)
        if resp.get("success"):
            r = resp["result"]
            return CoboTransferResult(
                success=True,
                transaction_id=r.get("transaction_id", ""),
                status=r.get("status", "completed"),
                amount=str(amount),
                token_id=token_id,
                to_address=to_address,
                tx_hash=r.get("tx_hash"),
                mode="cobo",
                request_id=request_id or "",
            )
        return CoboTransferResult(
            success=False,
            transaction_id="",
            status="failed",
            amount=str(amount),
            token_id=token_id,
            to_address=to_address,
            tx_hash=None,
            mode="cobo",
            request_id=request_id or "",
            error=resp.get("error", "Transfer failed"),
        )

    def _real_get_balance(self, token_id):
        params = {}
        if token_id:
            params["token_id"] = token_id
        return self._api_get(f"/api/v1/wallets/{self.wallet_id}/balance", params)

    def _real_list_audit_logs(self, limit):
        return self._api_get("/api/v1/audit_logs", {"limit": str(limit)})

    def _real_get_pact(self, pact_id):
        return self._api_get(f"/api/v1/pacts/{pact_id}")

    # ── Sim mode implementations ─────────────────────────────

    def _ts(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _sim_submit_pact(self, intent, service_name, amount, token_id,
                         chain_id, to_address):
        pact_id = f"pact_sim_{uuid.uuid4().hex[:8]}"
        return CoboPactResult(
            success=True,
            pact_id=pact_id,
            status="ACTIVE",  # unpaired agent auto-approved
            wallet_id="wallet_sim_0000",
            created_at=self._ts(),
            mode="simulated",
        )

    def _sim_execute_transfer(self, pact_id, to_address, amount,
                              token_id, chain_id, request_id):
        request_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        tx_id = f"tx_sim_{uuid.uuid4().hex[:12]}"
        return CoboTransferResult(
            success=True,
            transaction_id=tx_id,
            status="completed",
            amount=str(amount),
            token_id=token_id,
            to_address=to_address,
            tx_hash=f"0x{'0' * 40}",
            mode="simulated",
            request_id=request_id,
        )

    def _sim_get_balance(self, token_id):
        return {
            "success": True,
            "result": {
                "wallet_id": "wallet_sim_0000",
                "balances": [
                    {"token_id": "BASE_USDC", "amount": "100.00", "mode": "simulated"},
                    {"token_id": "BASE_ETH", "amount": "0.50", "mode": "simulated"},
                ],
            },
            "mode": "simulated",
        }

    def _sim_list_audit_logs(self, limit):
        return {
            "success": True,
            "result": [
                {
                    "id": f"log_{uuid.uuid4().hex[:8]}",
                    "action": "pact.submitted",
                    "timestamp": self._ts(),
                    "detail": "Guard PASS → Pact submitted for Research Notes Generator",
                    "mode": "simulated",
                },
                {
                    "id": f"log_{uuid.uuid4().hex[:8]}",
                    "action": "transfer.completed",
                    "timestamp": self._ts(),
                    "detail": "0.25 USDC transferred to service address",
                    "mode": "simulated",
                },
            ],
            "mode": "simulated",
        }

    def _sim_get_pact(self, pact_id):
        return {
            "success": True,
            "result": {
                "pact_id": pact_id,
                "status": "ACTIVE",
                "wallet_id": "wallet_sim_0000",
                "created_at": self._ts(),
                "policies": [{"type": "transfer", "name": "pay-research-agent"}],
                "completion_conditions": [
                    {"type": "tx_count", "threshold": "1"},
                    {"type": "time_elapsed", "threshold": "3600"},
                ],
            },
            "mode": "simulated",
        }
