"""FastAPI web server for Agent Commerce Hub.

The web layer calls the existing sandbox engine functions and exposes them as
JSON APIs for the single-page interface in web/index.html.
"""

import asyncio
import io
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent_commerce_sandbox.engine import discover_services, pay_for_service, show_proofs
from agent_commerce_sandbox.procurement_agent import match_and_rank, get_balance, format_price
from agent_commerce_sandbox.chain_client import ChainClient


ROOT_DIR = Path(__file__).resolve().parent.parent
INDEX_PATH = Path(__file__).resolve().parent / "index.html"

app = FastAPI(title="Agent Commerce Hub", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount x402 service endpoints
from agent_commerce_sandbox.x402_server import x402_app
app.mount("/api/x402", x402_app, name="x402")


class PayRequest(BaseModel):
    service_id: int = Field(..., ge=0)
    intent: str = Field(default="", max_length=4000)


class MatchRequest(BaseModel):
    request: str = Field(..., min_length=1, max_length=1000)


def json_safe(value: Any) -> Any:
    """Convert web3 and CLI return values into JSON-serializable objects.
    Also strips sensitive fields (api_key) to prevent credential leaks.
    """
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()
                if k.lower() not in _SENSITIVE_PACT_FIELDS}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "hex") and not isinstance(value, (str, int, float, bool)):
        try:
            return value.hex()
        except Exception:
            pass
    return value


# Fields to strip from pact data before sending to browser (credential leak prevention)
_SENSITIVE_PACT_FIELDS = {"api_key"}


def _sanitize_pact(pact: dict) -> dict:
    """Strip sensitive fields from pact data before returning to browser."""
    if not isinstance(pact, dict):
        return pact
    return {k: v for k, v in pact.items() if k.lower() not in _SENSITIVE_PACT_FIELDS}


def run_caw_json(*args: str, timeout: int = 60) -> dict[str, Any]:
    """Run the caw CLI and parse JSON output."""
    cmd = ["caw", *args, "--timeout", str(timeout)]
    result = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=timeout + 10,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "caw command failed").strip()
        raise RuntimeError(detail[:1000])
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"caw returned invalid JSON: {result.stdout[:500]}") from exc
    return json_safe(data)


async def to_thread(func, *args, **kwargs):
    """Run blocking sandbox code in a worker thread with silenced stdout."""
    def _wrapped():
        old_out = sys.stdout
        sys.stdout = io.StringIO()
        try:
            return func(*args, **kwargs)
        finally:
            sys.stdout = old_out
    return await asyncio.to_thread(_wrapped)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(INDEX_PATH)


@app.get("/api/services")
async def api_services() -> list[dict[str, Any]]:
    try:
        services = await to_thread(discover_services)
        return json_safe(services)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pay")
async def api_pay(payload: PayRequest) -> dict[str, Any]:
    intent = payload.intent.strip() or f"Purchase service #{payload.service_id}"
    try:
        result = await to_thread(pay_for_service, payload.service_id, intent)
        return json_safe(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/pact/{pact_id}/status")
async def api_pact_status(pact_id: str) -> dict[str, Any]:
    if not pact_id or len(pact_id) > 200:
        raise HTTPException(status_code=400, detail="Invalid pact id")
    try:
        data = await to_thread(run_caw_json, "pact", "show", "--pact-id", pact_id, timeout=60)
        pact = data.get("result", data) if isinstance(data, dict) else {"raw": data}
        status = pact.get("status", "unknown") if isinstance(pact, dict) else "unknown"
        return {"pact_id": pact_id, "status": status, "pact": json_safe(_sanitize_pact(pact))}
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Timed out while checking pact status") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/proofs")
async def api_proofs() -> list[dict[str, Any]]:
    try:
        proofs = await to_thread(show_proofs)
        return json_safe(proofs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class MatchResponseItem(BaseModel):
    id: int
    name: str
    description: str
    price_eth: str
    price_usd: str
    match_score: int
    paymentAddress: str
    chainId: str
    tokenId: str


@app.post("/api/procure/match")
async def api_procure_match(payload: MatchRequest) -> dict[str, Any]:
    try:
        chain = await to_thread(ChainClient)
        services = await to_thread(chain.list_services)
        active = [s for s in services if s.get("active", True)]
        ranked, match_source = match_and_rank(payload.request, active)

        matches = []
        for score, s in ranked[:5]:
            eth_s, usd_s = format_price(s["priceWei"])
            matches.append(MatchResponseItem(
                id=s["id"],
                name=s["name"],
                description=s["description"],
                price_eth=eth_s,
                price_usd=usd_s,
                match_score=score,
                paymentAddress=s["paymentAddress"],
                chainId=s["chainId"],
                tokenId=s["tokenId"],
            ))

        balance = await to_thread(get_balance)
        return {"matches": [m.model_dump() for m in matches], "balance": balance, "match_source": match_source}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/procure")
async def api_procure(payload: MatchRequest) -> dict[str, Any]:
    """Full procurement: match best service, create pact, execute transfer, record proof."""
    try:
        chain = await to_thread(ChainClient)
        services = await to_thread(chain.list_services)
        active = [s for s in services if s.get("active", True)]
        if not active:
            raise HTTPException(status_code=404, detail="No active services available")

        ranked, match_source = match_and_rank(payload.request, active)
        best = ranked[0][1]

        result = await to_thread(pay_for_service, best["id"], payload.request)
        return json_safe({
            **result,
            "matched_service": {
                "id": best["id"],
                "name": best["name"],
                "match_score": ranked[0][0],
            },
            "match_source": match_source,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class X402BuyRequest(BaseModel):
    service_id: int = 4
    query: str = ""


@app.post("/api/x402-buy")
async def api_x402_buy(payload: X402BuyRequest) -> dict[str, Any]:
    """Full x402 auto-pay flow: request → pact → transfer → deliver."""
    try:
        from agent_commerce_sandbox.x402_client import X402Client
        from agent_commerce_sandbox.caw_client import CawClient
        import json as _json

        caw = CawClient()
        x402 = X402Client(server_url="http://127.0.0.1:8888")
        svc = next((s for s in x402.list_services() if s["id"] == payload.service_id), None)
        if not svc:
            raise HTTPException(status_code=404, detail=f"x402 service {payload.service_id} not found")

        # Step 1: Get 402 payment info
        import urllib.request
        from urllib.error import HTTPError
        req = urllib.request.Request(
            f"{x402.server_url}/request",
            data=_json.dumps({"service_id": payload.service_id, "query": payload.query}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=15)
            raise RuntimeError("Expected 402 but got 200")
        except HTTPError as e:
            if e.code != 402:
                raise
            payment = _json.loads(e.read()).get("payment", {})

        # Step 2: Submit pact
        policies = _json.dumps([{
            "name": f"x402-pay-{svc['name'].lower().replace(' ','-')[:20]}",
            "type": "transfer",
            "rules": {
                "effect": "allow",
                "when": {
                    "chain_in": [payment.get("chain_id", "SETH")],
                    "token_in": [{"chain_id": payment.get("chain_id", "SETH"), "token_id": payment.get("token_id", "SETH")}],
                    "destination_address_in": [{"chain_id": payment.get("chain_id", "SETH"), "address": payment.get("address", "")}],
                },
                "deny_if": {"amount_usd_gt": "5.00"},
            },
        }])

        pact = caw.submit_pact(
            intent=f"x402 auto-pay: {payment['amount']} {payment['token_id']} for {svc['name']}",
            policies_json=policies,
            completion_conditions=_json.dumps([{"type": "tx_count", "threshold": "1"}]),
            name=f"x402-{svc['name'].lower().replace(' ','-')[:20]}",
            execution_plan=f"# Summary\\nAuto-pay for {svc['name']} via x402\\n\\n# Operations\\n- Transfer {payment['amount']} {payment['token_id']} to {payment.get('address','')}\\n\\n# Risk Controls\\n- Single transfer",
        )
        pact_id = pact.get("pact_id", "")
        pact_status = pact.get("status", "")

        if pact_status in ("pending_approval", "PENDING_APPROVAL"):
            # Wait for user to approve in CAW App
            try:
                caw.wait_for_pact_active(pact_id, timeout=300)
            except TimeoutError:
                return {"status": "pending_approval", "pact_id": pact_id, "error": "Awaiting CAW App approval"}

        # Step 3: Execute transfer
        tx_result = caw.execute_transfer(
            pact_id=pact_id,
            dst_address=payment.get("address", ""),
            amount=payment.get("amount", svc["price"]),
            token_id=payment.get("token_id", svc["token"]),
            chain_id=payment.get("chain_id", svc["chain"]),
            description=f"x402 auto-pay for {svc['name']}: {payload.query[:80]}",
        )
        tx_id = tx_result.get("id", "")

        # Wait for completion
        tx_complete = caw.wait_for_transaction_complete(tx_id, timeout=180)
        request_id = tx_result.get("request_id", tx_id)

        # Step 4: Retry x402 with payment proof
        retry_payload = _json.dumps({"service_id": payload.service_id, "query": payload.query}).encode()
        retry_req = urllib.request.Request(
            f"{x402.server_url}/request?tx_hash={request_id}",
            data=retry_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(retry_req, timeout=30)
        result = _json.loads(resp.read())

        return json_safe({
            "status": "completed",
            "service": svc["name"],
            "amount_paid": payment.get("amount", ""),
            "tx_hash": tx_complete.get("transaction_hash", ""),
            "content": result.get("content", ""),
        })

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "wallet_healthy": False,
        "contract_address": None,
        "service_count": 0,
        "proof_count": 0,
    }

    try:
        chain = await to_thread(ChainClient)
        if chain is None:
            raise RuntimeError("ChainClient() returned None")
        status["contract_address"] = chain.contract_addr
        status["service_count"] = await to_thread(chain.get_service_count)
        status["proof_count"] = await to_thread(chain.get_proof_count)
    except Exception as exc:
        status["chain_error"] = str(exc)

    try:
        caw_status = await to_thread(run_caw_json, "status", timeout=30)
        result = caw_status.get("result", caw_status) if isinstance(caw_status, dict) else {}
        status["wallet_healthy"] = bool(result.get("healthy", False))
        status["wallet_status"] = result.get("wallet_status")
        status["wallet_paired"] = result.get("wallet_paired")
    except Exception as exc:
        status["wallet_error"] = str(exc)

    return json_safe(status)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        timeout_keep_alive=600,
    )
