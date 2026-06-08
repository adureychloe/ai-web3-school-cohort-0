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
        ranked = match_and_rank(payload.request, active)

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
        return {"matches": [m.model_dump() for m in matches], "balance": balance}
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

        ranked = match_and_rank(payload.request, active)
        best = ranked[0][1]

        result = await to_thread(pay_for_service, best["id"], payload.request)
        return json_safe({
            **result,
            "matched_service": {
                "id": best["id"],
                "name": best["name"],
                "match_score": ranked[0][0],
            }
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
