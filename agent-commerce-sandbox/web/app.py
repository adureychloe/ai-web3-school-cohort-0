"""FastAPI web server for Agent Commerce Hub.

The web layer calls the existing sandbox engine functions and exposes them as
JSON APIs for the single-page interface in web/index.html.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent_commerce_sandbox.engine import discover_services, pay_for_service, show_proofs


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


def json_safe(value: Any) -> Any:
    """Convert web3 and CLI return values into JSON-serializable objects."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
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
    """Run blocking sandbox code in a worker thread."""
    return await asyncio.to_thread(func, *args, **kwargs)


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
        return {"pact_id": pact_id, "status": status, "pact": json_safe(pact)}
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


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "wallet_healthy": False,
        "contract_address": None,
        "service_count": 0,
        "proof_count": 0,
    }

    try:
        from agent_commerce_sandbox.chain_client import ChainClient

        chain = await to_thread(ChainClient)
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
