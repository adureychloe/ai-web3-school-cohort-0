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
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent_commerce_sandbox.engine import discover_services, pay_for_service, show_proofs
from agent_commerce_sandbox.procurement_agent import match_and_rank, get_balance, format_price
from agent_commerce_sandbox.chain_client import ChainClient
from agent_commerce_sandbox.chain_client_v2 import ChainClientV2

try:
    from web3 import Web3
except Exception:
    Web3 = None


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


async def _list_v2_services() -> list[dict[str, Any]]:
    """List active user-facing services from the V2/x402 registry."""
    from agent_commerce_sandbox.x402_client import _normalize_public_endpoint

    chain = await to_thread(ChainClientV2)
    services = await to_thread(chain.list_services, 0, 100)

    visible: list[dict[str, Any]] = []
    fields = (
        "id", "name", "description", "paymentAddress", "priceWei",
        "tokenId", "chainId", "active", "provider", "endpointURI", "protocol",
    )
    for svc in services:
        if not svc.get("active", False):
            continue
        protocol = svc.get("protocol") or "x402"
        if str(protocol).lower() != "x402":
            continue
        item = {field: svc.get(field) for field in fields}
        item["protocol"] = protocol
        item["endpointURI"] = _normalize_public_endpoint(
            str(svc.get("endpointURI") or ""),
            int(svc.get("id") or 0),
        )
        visible.append(item)

    return json_safe(visible)


async def _list_legacy_v1_services() -> list[dict[str, Any]]:
    """List services from the legacy V1 registry for explicit legacy callers."""
    services = await to_thread(discover_services)
    return json_safe(services)


@app.get("/api/services")
async def api_services() -> list[dict[str, Any]]:
    """Default user-facing service discovery: ServiceRegistryV2/x402 only."""
    try:
        return await _list_v2_services()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/services/v2")
async def api_services_v2() -> list[dict[str, Any]]:
    """Explicit V2 alias for the default ServiceRegistryV2/x402 registry."""
    try:
        return await _list_v2_services()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/legacy/services")
async def api_legacy_services() -> list[dict[str, Any]]:
    """Legacy V1 service discovery (ServiceRegistry + CAW pact/payment/proof)."""
    try:
        return await _list_legacy_v1_services()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/services/all")
async def api_services_all(
    include_legacy: bool = Query(False, description="Include legacy V1 ServiceRegistry results"),
) -> list[dict[str, Any]]:
    """Return V2/x402 services by default; include V1 only when requested."""
    merged: list[dict[str, Any]] = []

    try:
        v2_services = await _list_v2_services()
        for s in v2_services:
            item = dict(s)
            item["source"] = "v2"
            merged.append(item)
    except Exception as exc:
        merged.append({"source": "v2", "error": str(exc)})

    if include_legacy:
        try:
            v1_chain = await to_thread(ChainClient)
            v1_services = await to_thread(v1_chain.list_services)
            for s in v1_services:
                item = dict(s)
                item["source"] = "legacy_v1"
                merged.append(item)
        except Exception as exc:
            # V1 is legacy and opt-in; do not block V2 results.
            merged.append({"source": "legacy_v1", "error": str(exc)})

    return json_safe(merged)


@app.post("/api/legacy/pay")
async def api_legacy_pay(payload: PayRequest) -> dict[str, Any]:
    """Legacy V1 payment flow using CAW pact/payment/proof helpers."""
    intent = payload.intent.strip() or f"Purchase service #{payload.service_id}"
    try:
        result = await to_thread(pay_for_service, payload.service_id, intent)
        return json_safe(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pay")
async def api_pay(payload: PayRequest) -> dict[str, Any]:
    """Compatibility wrapper for the default V2/x402 payment flow."""
    return await api_x402_buy(
        X402BuyRequest(service_id=payload.service_id, query=payload.intent)
    )


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
    """Default delivery proofs from ServiceRegistryV2/x402."""
    try:
        chain = await to_thread(ChainClientV2)
        count = await to_thread(chain.get_proof_count)
        proofs = await to_thread(chain.get_proofs, 0, count) if count else []
        return json_safe(proofs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/legacy/proofs")
async def api_legacy_proofs() -> list[dict[str, Any]]:
    """Legacy V1 delivery proofs from ServiceRegistry.

    Some historical V1 proof rows can contain malformed bytes; keep the explicit
    legacy endpoint non-blocking by returning a tagged error row instead of
    breaking the V2/x402 UI.
    """
    try:
        chain = await to_thread(ChainClient)
        count = await to_thread(chain.get_proof_count)
        proofs = await to_thread(chain.get_proofs, 0, count) if count else []
        return json_safe(proofs)
    except Exception as exc:
        return json_safe([{"source": "legacy_v1", "error": str(exc)}])


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


@app.post("/api/legacy/procure/match")
async def api_legacy_procure_match(payload: MatchRequest) -> dict[str, Any]:
    """Legacy V1 procurement matching against ServiceRegistry V1 services."""
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


@app.post("/api/procure/match")
async def api_procure_match(payload: MatchRequest) -> dict[str, Any]:
    """Default procurement matching against V2/x402 services only."""
    try:
        services = await _list_v2_services()
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


@app.post("/api/legacy/procure")
async def api_legacy_procure(payload: MatchRequest) -> dict[str, Any]:
    """Legacy V1 procurement: match service, create CAW pact, pay, record proof."""
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


@app.post("/api/procure")
async def api_procure(payload: MatchRequest) -> dict[str, Any]:
    """Default procurement uses V2/x402 auto-pay instead of legacy V1."""
    try:
        services = await _list_v2_services()
        active = [s for s in services if s.get("active", True)]
        if not active:
            raise HTTPException(status_code=404, detail="No active x402 services available")

        ranked, match_source = match_and_rank(payload.request, active)
        best = ranked[0][1]
        result = await api_x402_buy(X402BuyRequest(service_id=best["id"], query=payload.request))
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
    wallet_address: Optional[str] = None


class X402ClaimRequest(BaseModel):
    """Request body for claiming x402 content with a wallet tx."""
    service_id: int = Field(..., ge=0)
    wallet_address: str = Field(..., min_length=40, max_length=46)
    tx_hash: str = Field(..., min_length=10, max_length=200)
    query: str = Field(default="", max_length=1000)


class X402ConnectRequest(BaseModel):
    """Connect a visitor wallet with signature proof."""
    wallet_address: str = Field(..., min_length=40, max_length=46)


class X402ChallengeResponse(BaseModel):
    """Response to a signature challenge."""
    wallet_address: str = Field(..., min_length=40, max_length=46)
    signature: str = Field(..., min_length=10, max_length=500)


# In-memory pending challenges (wallet_address_lower → nonce)
_pending_challenges: dict[str, str] = {}


def _verify_address(addr: str) -> str:
    """Validate and normalize an Ethereum address."""
    addr = addr.strip().lower()
    if not addr.startswith("0x") or len(addr) < 40 or len(addr) > 42:
        raise ValueError()
    hex_part = addr[2:]
    if len(hex_part) < 38 or len(hex_part) > 40:
        raise ValueError()
    int(hex_part, 16)
    return addr


@app.post("/api/x402-challenge")
async def api_x402_challenge(payload: X402ConnectRequest) -> dict[str, Any]:
    """Step 1: Generate a challenge for the wallet to sign."""
    try:
        addr = _verify_address(payload.wallet_address)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")

    # Generate unique nonce
    nonce = os.urandom(16).hex()
    challenge_msg = f"Agent Commerce Hub - Login\nAddress: {addr}\nNonce: {nonce}"
    _pending_challenges[addr] = nonce

    return {
        "status": "challenge",
        "wallet_address": addr,
        "challenge": challenge_msg,
        "instructions": (
            f"Run this in your terminal:\n"
            f"  caw sign --message \"{challenge_msg}\"\n"
            f"Then paste the signature here."
        ),
    }


@app.post("/api/x402-connect")
async def api_x402_connect(payload: X402ChallengeResponse) -> dict[str, Any]:
    """Step 2: Verify signature and connect wallet."""
    try:
        addr = _verify_address(payload.wallet_address)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")

    # Check pending challenge
    expected_nonce = _pending_challenges.get(addr)
    if not expected_nonce:
        raise HTTPException(status_code=400, detail="No pending challenge. Call /api/x402-challenge first.")

    # Clean up challenge (one-time use)
    del _pending_challenges[addr]

    # Recover signer from signature
    expected_msg = f"Agent Commerce Hub - Login\nAddress: {addr}\nNonce: {expected_nonce}"
    try:
        if Web3 is not None:
            # Hash the message (EIP-191 personal_sign format)
            msg_hash = Web3.keccak(text=f"\x19Ethereum Signed Message:\n{len(expected_msg)}{expected_msg}")
            recovered = Web3.to_checksum_address(Web3.keccak(msg_hash))
            # Try eth_account for proper ecrecover
            from eth_account.messages import encode_defunct
            from eth_account.account import Account
            msg_obj = encode_defunct(text=expected_msg)
            recovered_addr = Account.recover_message(msg_obj, signature=payload.signature.strip())
            recovered_lower = recovered_addr.lower()
        else:
            raise RuntimeError("Web3 not available")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Signature verification failed: {exc}")

    if recovered_lower != addr:
        raise HTTPException(
            status_code=403,
            detail="Signature does not match wallet address. Make sure you signed the exact challenge message with your wallet.",
        )

    return {
        "status": "connected",
        "wallet_address": addr,
        "message": f"Wallet {addr[:10]}... successfully verified and connected.",
    }


@app.post("/api/x402-request")
async def api_x402_request(payload: X402BuyRequest) -> dict[str, Any]:
    """Step 1: Request a service — returns 402 payment info.

    Unlike /api/x402-buy, this does NOT create a Pact or transfer.
    It just returns the payment requirement so the visitor can pay
    from their own CAW wallet.
    """
    try:
        from agent_commerce_sandbox.x402_client import X402Client
        import urllib.request
        from urllib.error import HTTPError
        import json as _json

        x402 = _x402_client_for_marketplace()
        svc = next((s for s in x402.list_services() if s["id"] == payload.service_id), None)
        if not svc:
            raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found")
        request_url = x402._resolve_request_url(svc)

        # Fetch 402 payment info from the service's V2 endpointURI
        req = urllib.request.Request(
            request_url,
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

        return json_safe({
            "status": "payment_required",
            "service": svc,
            "payment": payment,
            "instructions": (
                f"Send {payment.get('amount')} {payment.get('token_id')} "
                f"to {payment.get('address')} on {payment.get('chain_id')} "
                f"from your wallet, then submit the tx_hash to claim."
            ),
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/x402-claim")
async def api_x402_claim(payload: X402ClaimRequest) -> dict[str, Any]:
    """Step 2: Verify visitor's payment and deliver content.

    The visitor paid from their own wallet. We verify the tx_hash
    went to the right address with the right amount, then deliver.
    """
    try:
        import urllib.request
        from urllib.error import HTTPError
        import json as _json

        wallet = payload.wallet_address.strip()
        tx_hash = payload.tx_hash.strip()

        # Check the selected service's V2/x402 endpointURI with the tx_hash as proof.
        x402 = _x402_client_for_marketplace()
        svc = next((s for s in x402.list_services() if s["id"] == payload.service_id), None)
        if not svc:
            raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found")
        request_url = x402._resolve_request_url(svc)

        retry_payload = _json.dumps({"service_id": payload.service_id, "query": payload.query}).encode()
        retry_req = urllib.request.Request(
            f"{request_url}?tx_hash={tx_hash}",
            data=retry_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(retry_req, timeout=30)
        result = _json.loads(resp.read())

        return json_safe({
            "status": "delivered",
            "service_id": payload.service_id,
            "wallet_address": wallet,
            "tx_hash": tx_hash,
            "content": result.get("content", ""),
            "amount_paid": result.get("amount_paid", ""),
        })
    except HTTPError as e:
        body = e.read().decode()
        raise HTTPException(status_code=e.code, detail=f"Payment verification failed: {body[:300]}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Reusable Pact for x402 auto-pay ────────────────────────
# Store one active Pact and reuse it for compatible x402 purchases.
_x402_pact_id: Optional[str] = None


def _pact_result(pact: dict) -> dict:
    """Normalize CAW pact responses that may be wrapped in a result object."""
    if isinstance(pact, dict) and isinstance(pact.get("result"), dict):
        return pact["result"]
    return pact if isinstance(pact, dict) else {}


def _pact_is_compatible(pact: dict, payment: dict) -> bool:
    """Return True when a Pact policy can pay this x402 payment request."""
    pact = _pact_result(pact)
    if not isinstance(pact, dict):
        return False

    expected_chain = str(payment.get("chain_id") or "SETH").lower()
    expected_token = str(payment.get("token_id") or "SETH").lower()
    expected_addr = str(payment.get("address") or "").lower()
    if not expected_addr:
        return False

    policies = pact.get("spec", {}).get("policies", [])
    for policy in policies:
        rules = policy.get("rules", {}) if isinstance(policy, dict) else {}
        when = rules.get("when", {}) if isinstance(rules, dict) else {}
        chains = [str(c).lower() for c in when.get("chain_in", [])]
        tokens = when.get("token_in", [])
        destinations = when.get("destination_address_in", [])

        chain_ok = not chains or expected_chain in chains
        token_ok = not tokens or any(
            str(t.get("chain_id", "")).lower() == expected_chain
            and str(t.get("token_id", "")).lower() == expected_token
            for t in tokens if isinstance(t, dict)
        )
        dest_ok = any(
            str(d.get("chain_id", "")).lower() == expected_chain
            and str(d.get("address", "")).lower() == expected_addr
            for d in destinations if isinstance(d, dict)
        )
        if chain_ok and token_ok and dest_ok:
            return True
    return False


def _pact_allows_payment(pact: dict, payment: dict) -> bool:
    """Return True when an active Pact can pay this x402 payment request."""
    pact = _pact_result(pact)
    return str(pact.get("status", "")).lower() == "active" and _pact_is_compatible(pact, payment)


def _pending_approval_response(pact_id: str, pact_status: str, error: str) -> dict[str, Any]:
    """Return the browser's canonical pending-approval response shape."""
    return {
        "status": "pending_approval",
        "pact": {"pact_id": pact_id, "status": pact_status},
        "pact_id": pact_id,
        "error": error,
    }


def _x402_client_for_marketplace():
    """Use V2 endpointURI by default; local override only when explicit env is set."""
    from agent_commerce_sandbox.x402_client import X402Client
    override = os.environ.get("X402_SERVER_OVERRIDE") or os.environ.get("X402_SERVER")
    return X402Client(server_url=override) if override else X402Client()


def _api_x402_buy_blocking(payload: X402BuyRequest) -> dict[str, Any]:
    """Full x402 auto-pay flow: reuse active pact → transfer → deliver.

    Creates ONE Pact on first purchase (approve once in CAW App).
    All subsequent purchases reuse the same Pact — zero approval.
    """
    global _x402_pact_id
    try:
        import urllib.request
        from urllib.error import HTTPError
        import json as _json
        from agent_commerce_sandbox.x402_client import X402Client
        from agent_commerce_sandbox.caw_client import CawClient

        if payload.wallet_address:
            try:
                payload_wallet = Web3.to_checksum_address(payload.wallet_address) if Web3 else payload.wallet_address
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid buyer wallet address")
        else:
            payload_wallet = None

        caw = CawClient()
        if payload_wallet:
            paired_wallet = Web3.to_checksum_address(caw.wallet_address) if Web3 else caw.wallet_address
            if payload_wallet.lower() != paired_wallet.lower():
                raise HTTPException(
                    status_code=400,
                    detail="Connected buyer wallet does not match this server's paired CAW wallet",
                )

        x402 = _x402_client_for_marketplace()
        svc = next((s for s in x402.list_services() if s["id"] == payload.service_id), None)
        if not svc:
            raise HTTPException(status_code=404, detail=f"x402 service {payload.service_id} not found")
        request_url = x402._resolve_request_url(svc)

        # Step 1: Get 402 payment info from the service's V2 endpointURI
        req = urllib.request.Request(
            request_url,
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

        # Step 2: Reuse or create Pact
        pact_id = None
        needs_approval = False

        # Check if stored Pact is still active
        if _x402_pact_id:
            try:
                pact_info = _pact_result(caw.get_pact(_x402_pact_id))
                pact_status = str(pact_info.get("status", ""))
                if pact_status.lower() == "pending_approval" and _pact_is_compatible(pact_info, payment):
                    return _pending_approval_response(
                        _x402_pact_id,
                        pact_status,
                        "Awaiting CAW App approval for Pact — after approval, retry this buy to auto-execute",
                    )
                if _pact_allows_payment(pact_info, payment):
                    pact_id = _x402_pact_id
                else:
                    # Stale or incompatible with this service's destination/token.
                    _x402_pact_id = None
            except Exception:
                _x402_pact_id = None

        # No active pact — create a reusable one
        if not pact_id:
            policies = _json.dumps([{
                "name": "x402-auto-pay",
                "type": "transfer",
                "rules": {
                    "effect": "allow",
                    "when": {
                        "chain_in": ["SETH"],
                        "token_in": [{"chain_id": "SETH", "token_id": "SETH"}],
                        "destination_address_in": [
                            {"chain_id": "SETH", "address": payment.get("address", "")}
                        ],
                    },
                    "deny_if": {"amount_usd_gt": "10.00"},
                },
            }])

            pact = caw.submit_pact(
                intent="x402 auto-pay — reusable pact for Agent Commerce Hub purchases",
                policies_json=policies,
                completion_conditions=_json.dumps([{"type": "tx_count", "threshold": "100"}]),
                name="x402-auto-pay",
                execution_plan="# Summary\\nReusable Pact for all x402 Auto-Pay purchases\\n\\n# Operations\\n- Transfer SETH for purchased services\\n\\n# Risk Controls\\n- Max $10 per transaction\\n- SETH chain only",
            )
            pact_id = pact.get("pact_id", "")
            pact_status = pact.get("status", "")
            if pact_id:
                _x402_pact_id = pact_id

            if str(pact_status).lower() == "pending_approval":
                needs_approval = True
                # Wait for user to approve in CAW App (first time only). Keep
                # _x402_pact_id available while waiting so concurrent/retry
                # requests reuse the pending compatible Pact instead of creating
                # another one.
                try:
                    caw.wait_for_pact_active(pact_id, timeout=300)
                except TimeoutError:
                    return _pending_approval_response(
                        pact_id,
                        pact_status,
                        "Awaiting CAW App approval for Pact — after approval, all future buys auto-execute",
                    )

            # Store for future reuse
            if pact_id:
                _x402_pact_id = pact_id

        # Step 3: Execute transfer under the (new or reused) Pact
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
        tx_hash = tx_complete.get("transaction_hash", "")
        if not tx_hash or not str(tx_hash).startswith("0x"):
            raise RuntimeError("CAW transfer completed without an on-chain transaction_hash; cannot prove x402 payment")

        # Step 4: Retry x402 with on-chain payment proof
        retry_payload = _json.dumps({"service_id": payload.service_id, "query": payload.query}).encode()
        retry_req = urllib.request.Request(
            f"{request_url}?tx_hash={tx_hash}",
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
            "tx_hash": tx_hash,
            "reused_pact": not needs_approval and _x402_pact_id is not None,
            "content": result.get("content", ""),
        })

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/x402-buy")
async def api_x402_buy(payload: X402BuyRequest) -> dict[str, Any]:
    """Full x402 auto-pay flow without blocking the FastAPI event loop."""
    return await asyncio.to_thread(_api_x402_buy_blocking, payload)


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "wallet_healthy": False,
        # Default fields describe the default V2/x402 registry.
        "contract_address": None,
        "service_count": 0,
        "proof_count": 0,
        # Explicit V2 aliases kept for compatibility.
        "v2_contract_address": None,
        "v2_service_count": 0,
        # Legacy V1 fields are opt-in/explicit.
        "legacy_contract_address": None,
        "legacy_service_count": 0,
        "legacy_proof_count": 0,
    }

    try:
        chain_v2 = await to_thread(ChainClientV2)
        if chain_v2 is None:
            raise RuntimeError("ChainClientV2() returned None")
        v2_service_count = await to_thread(chain_v2.get_service_count)
        v2_proof_count = await to_thread(chain_v2.get_proof_count)
        status["contract_address"] = chain_v2.contract_addr
        status["service_count"] = v2_service_count
        status["proof_count"] = v2_proof_count
        status["v2_contract_address"] = chain_v2.contract_addr
        status["v2_service_count"] = v2_service_count
        status["v2_proof_count"] = v2_proof_count
    except Exception as exc:
        status["v2_chain_error"] = str(exc)

    try:
        chain = await to_thread(ChainClient)
        if chain is None:
            raise RuntimeError("ChainClient() returned None")
        status["legacy_contract_address"] = chain.contract_addr
        status["legacy_service_count"] = await to_thread(chain.get_service_count)
        status["legacy_proof_count"] = await to_thread(chain.get_proof_count)
    except Exception as exc:
        status["legacy_chain_error"] = str(exc)

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
