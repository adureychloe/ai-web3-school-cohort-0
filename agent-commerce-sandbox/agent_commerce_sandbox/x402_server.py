"""
x402 Server — Agent as Seller / Service Provider.

Runs an HTTP endpoint that uses HTTP 402 Payment Required to demand
payment before serving content. Services are discovered from the on-chain
ServiceRegistryV2 contract on Sepolia.

Flow:
  Client → POST /request  (no payment)
          ← 402 + X-Payment-Info header

  Client → CAW Pact → Transfer  (auto-pay)

  Client → POST /request?tx_hash=0x...
          ← 200 + service result

Provider self-registration (writes on-chain via the deployer EOA):
  Client → POST /register_v2 {name, description, price_seth, endpoint_uri}
"""

import json
import os
import sys
import time
from typing import Optional
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from web3 import Web3

# ── Path setup for running standalone ───────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_commerce_sandbox.chain_client_v2 import ChainClientV2
from agent_commerce_sandbox.caw_client import CawClient, WALLET_SETH_ADDR

x402_app = FastAPI(
    title="Agent Commerce Hub — x402 Service",
    description="HTTP 402 Payment Required endpoint for Agent-to-Agent commerce (on-chain V2 registry)",
    version="0.7.0",
)

# ── Constants ───────────────────────────────────────────────────

# x402 provider / contract owner (deployer EOA)
X402_PROVIDER = "0x88cbfBD095e9f813B38a5F6f75B1F531897391EE"

# Hosts this server considers "local" — a service whose endpointURI points
# elsewhere will NOT be served by this instance (returns 404).
_DEFAULT_SELF_HOSTS = {
    "127.0.0.1:8888", "localhost:8888", "0.0.0.0:8888",
    "127.0.0.1:8080", "localhost:8080", "0.0.0.0:8080",
}

# Hosts allowed for deriving a public endpoint from forwarded request headers
# when no configured public base URL is set. No defaults are trusted: public
# rewrites require an exact hostname listed in comma-separated
# X402_ALLOWED_PUBLIC_HOSTS.
_DEFAULT_ALLOWED_PUBLIC_HOSTS: set[str] = set()

# Last-resort compatibility for the stale demo registry entry whose endpointURI
# is still loopback. Do not use this fallback for newly registered services.
STALE_DEMO_SERVICE_ID = 1
LAST_RESORT_DEMO_PUBLIC_X402_SERVER = "https://gradually-clicker-tacking.ngrok-free.dev/api/x402"


def _self_hosts() -> set[str]:
    """Return loopback/local hosts this process serves directly."""
    return set(_DEFAULT_SELF_HOSTS)


def _endpoint_base(endpoint_uri: str) -> Optional[str]:
    """Return normalized scheme://host/path base, without a trailing /request."""
    try:
        parsed = urlparse(endpoint_uri)
    except Exception:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/request"):
        path = path[: -len("/request")].rstrip("/")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def _allowed_local_endpoint_bases() -> set[str]:
    """Return exact public x402 bases this server is allowed to serve.

    This intentionally accepts the current demo tunnel only at its mounted
    /api/x402 base, plus explicitly configured bases. It does not treat
    arbitrary external endpoints on the same internet as local.
    """
    bases = {LAST_RESORT_DEMO_PUBLIC_X402_SERVER}
    for env_name in ("X402_SELF_URL", "X402_PUBLIC_URL"):
        base = _endpoint_base(os.environ.get(env_name, "").strip())
        if base:
            bases.add(base)
    for raw in os.environ.get("X402_ALLOWED_LOCAL_BASES", "").split(","):
        base = _endpoint_base(raw.strip())
        if base:
            bases.add(base)
    return {_clean_base_url(base).lower() for base in bases if base}


def _clean_base_url(url: str) -> str:
    """Return a stable base URL without a trailing slash."""
    return (url or "").strip().rstrip("/")


def _first_header_value(value: Optional[str]) -> str:
    """Return the first comma-separated forwarded header value."""
    return (value or "").split(",", 1)[0].strip()


def _allowed_public_hosts() -> set[str]:
    """Return exact normalized hostnames allowed for public endpoint derivation."""
    hosts = set(_DEFAULT_ALLOWED_PUBLIC_HOSTS)
    for host in os.environ.get("X402_ALLOWED_PUBLIC_HOSTS", "").split(","):
        host = host.strip().lower()
        if not host:
            continue
        try:
            parsed = urlparse(host if "://" in host else f"//{host}")
            hostname = parsed.hostname or host
        except Exception:
            hostname = host
        hostname = hostname.strip("[]").lower()
        if hostname:
            hosts.add(hostname)
    return hosts


def _normalize_forwarded_public_host(host_value: str) -> Optional[str]:
    """Return normalized forwarded host[:port] if its hostname is explicitly allowed."""
    if not host_value:
        return None
    try:
        parsed = urlparse(host_value if "://" in host_value else f"//{host_value}")
        hostname = (parsed.hostname or "").strip("[]").lower()
        port = parsed.port
    except Exception:
        return None
    if (
        not hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.params
        or parsed.query
        or parsed.fragment
        or hostname not in _allowed_public_hosts()
    ):
        return None
    if ":" in hostname:
        hostname = f"[{hostname}]"
    return f"{hostname}:{port}" if port is not None else hostname


def _configured_public_base_url() -> Optional[str]:
    """Return the configured public x402 base URL, if one is set.

    X402_SELF_URL is the primary authoritative base for this seller.
    X402_PUBLIC_URL is also accepted as an explicitly configured public base.
    """
    return (
        _clean_base_url(os.environ.get("X402_SELF_URL", ""))
        or _clean_base_url(os.environ.get("X402_PUBLIC_URL", ""))
        or None
    )


def _forwarded_public_base_url(request: Request) -> Optional[str]:
    """Derive this x402 service's public base URL only from trusted headers.

    X-Forwarded-Host is considered only when its normalized hostname exactly
    matches comma-separated X402_ALLOWED_PUBLIC_HOSTS and X-Forwarded-Proto is
    exactly "http" or "https". Localhost/base_url and wildcard public tunnel
    hosts are not trusted for loopback endpoint rewrites.
    """
    root_path = (request.scope.get("root_path") or "").rstrip("/")
    forwarded_proto = _first_header_value(request.headers.get("x-forwarded-proto"))
    forwarded_host = _normalize_forwarded_public_host(
        _first_header_value(request.headers.get("x-forwarded-host"))
    )
    if forwarded_proto in {"http", "https"} and forwarded_host:
        return _clean_base_url(f"{forwarded_proto}://{forwarded_host}{root_path}")

    return None


def _public_base_url(request: Request) -> Optional[str]:
    """Return an authoritative/trusted public base URL for this server, if any."""
    return _configured_public_base_url() or _forwarded_public_base_url(request)


def _endpoint_is_loopback(endpoint_uri: str) -> bool:
    """Return True when endpointURI points at a loopback host."""
    if not endpoint_uri:
        return False
    try:
        parsed = urlparse(endpoint_uri)
    except Exception:
        return False
    hostname = (parsed.hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _normalize_public_endpoint(
    endpoint_uri: str,
    service_id: int,
    public_base_url: Optional[str],
) -> str:
    """Return the buyer-visible endpoint for a registry service.

    Loopback endpointURI values are rewritten to a configured/trusted public
    base URL when one is available. If no public base is configured or safely
    derived, only stale demo service #1 receives the known current demo public
    fallback; all other loopback endpoints remain raw to avoid misrouting newly
    registered services.
    """
    if not _endpoint_is_loopback(endpoint_uri):
        return endpoint_uri
    if public_base_url:
        return public_base_url
    if service_id == STALE_DEMO_SERVICE_ID:
        return LAST_RESORT_DEMO_PUBLIC_X402_SERVER
    return endpoint_uri


def _endpoint_is_local(endpoint_uri: str) -> bool:
    """Return True if the service's endpointURI is served by this server.

    Empty endpoint → treated as local (legacy/registry-default). Public tunnel
    URLs are accepted only when their exact scheme://host/base path is on the
    local allowlist (for this demo, /api/x402), never by hostname alone.
    """
    if not endpoint_uri:
        return True
    try:
        parsed = urlparse(endpoint_uri)
    except Exception:
        return False
    if not parsed.netloc:
        # endpointURI may be a bare path like "/api/x402" or "/x402/request"
        return True

    netloc = parsed.netloc.lower()
    if netloc in _self_hosts():
        return True

    base = _endpoint_base(endpoint_uri)
    return bool(base and _clean_base_url(base).lower() in _allowed_local_endpoint_bases())


# ── Data ────────────────────────────────────────────────────────

# Replay protection: track used proof IDs to prevent double-spend
_used_proofs: set[str] = set()

# Track revenue in-memory (for demo; in production use contract events)
_revenue: dict[int, float] = {}
_revenue_log: list[dict] = []

# Lazy chain client (V2)
_chain: Optional[ChainClientV2] = None


def _get_chain() -> ChainClientV2:
    global _chain
    if _chain is None:
        _chain = ChainClientV2()
    return _chain


def _normalize_service(svc: dict) -> dict:
    """Convert an on-chain V2 service dict into the format used by routes."""
    price_seth = str(Web3.from_wei(svc["priceWei"], "ether"))
    return {
        "id": svc["id"],
        "name": svc["name"],
        "description": svc["description"],
        "price_wei": svc["priceWei"],
        "price_seth": price_seth,
        "token_id": svc["tokenId"] or "SETH",
        "chain_id": svc["chainId"] or "SETH",
        "payment_address": svc["paymentAddress"],
        "endpoint_uri": svc["endpointURI"],
        "protocol": svc["protocol"] or "x402",
        "active": svc["active"],
        "provider": svc["provider"],
    }


# ── Helpers ─────────────────────────────────────────────────────

def _verify_payment(tx_hash: str, expected_amount: str, expected_address: str) -> bool:
    """Verify a CAW transfer by checking the tx on-chain.

    Supports:
    - On-chain tx hash (0x...) → web3.py RPC query

    Also checks replay protection: already-used proofs are rejected.
    """
    # x402 only accepts on-chain transaction hashes as payment proof. CAW
    # request IDs are not transferable proof and must be resolved by the caller
    # before retrying /request.
    if not tx_hash or not tx_hash.startswith("0x"):
        return False

    # Replay protection
    if tx_hash in _used_proofs:
        return False

    try:
        # On-chain tx hash: verify via web3.py RPC
        rpc_url = "https://ethereum-sepolia-rpc.publicnode.com"
        w3_check = Web3(Web3.HTTPProvider(
            rpc_url,
            request_kwargs={"timeout": 60}
        ))
        try:
            tx = w3_check.eth.get_transaction(tx_hash)
            receipt = w3_check.eth.get_transaction_receipt(tx_hash)
            if receipt is None or receipt.get("status") != 1:
                return False
            if tx.get("to", "").lower() != expected_address.lower():
                return False
            actual_value_wei = tx.get("value", 0)
            expected_value_wei = Web3.to_wei(float(expected_amount), "ether")
            if actual_value_wei < expected_value_wei:
                return False
        except Exception:
            return False

        # Mark as used to prevent replay
        _used_proofs.add(tx_hash)
        return True
    except Exception:
        return False


def _generate_analysis(service: dict, query: str = "") -> str:
    """Generate the paid-service result for a delivered service."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    sid = service["id"]
    analyses = {
        4: f"""╔══════════════════════════════════════════╗
║     ETH Market Analysis Report          ║
║     Generated: {ts}        ║
╚══════════════════════════════════════════╝

Market Overview:
Price:        $3,482.50 (24h: +2.3%)
Volume:       $18.2B (24h)
Dominance:    18.4%

On-chain Metrics:
Active Addresses (24h): 485,320
Transaction Count:      1,203,847
Avg Gas Price:          18.5 Gwei
Total Value Staked:     34.2M ETH

Top Flow Analysis:
Exchange Inflow:   124,500 ETH (selling pressure)
Exchange Outflow:  89,200 ETH (accumulation)
L2 Settlement:     256,800 ETH to Arbitrum

Technical Indicators:
RSI (14):      62.4 (neutral-bullish)
MACD:          Bullish crossover detected
Support:       $3,350 (strong), $3,180 (critical)
Resistance:    $3,550, $3,720

Sentiment:
Funding Rate:  0.008% (slightly long-biased)
Open Interest: $8.4B (+5.2%)
Long/Short:    1.24x

Summary:    Bullish short-term with resistance at $3,550.
Outlook:    Watch for break above $3,550 for continuation to $3,720.

---
Delivered by Agent Commerce Hub. Payment verified on-chain via x402.
""",
        5: f"""╔══════════════════════════════════════════╗
║     On-chain Research Report            ║
║     Generated: {ts}        ║
╚══════════════════════════════════════════╝

Project:  Agent Commerce Hub Ecosystem Analysis

Address Activity (last 7 days):
Total Unique Active: 1,247
New Addresses:       342
Returning:           905

Token Flow Analysis:
Inflow:      0.05 SETH
Outflow:     0.03 SETH
Net Flow:    +0.02 SETH (accumulation)

Smart Contract Interactions:
ServiceRegistry:   12 calls
CAW Wallet:        8 transactions
Total Contracts:   3

Key Findings:
Finding 1:  Growing agent-to-agent payment volume
Finding 2:  Service discovery via on-chain registry
Finding 3:  x402 payment pattern emerging

Recommendation:
Monitor cross-agent payment patterns for fee optimization opportunities.

---
Delivered by Agent Commerce Hub. Payment verified on-chain via x402.
""",
    }
    if sid in analyses:
        return analyses[sid]

    # Generic delivery for any other on-chain service
    endpoint = service.get("endpointURI", "") or "(local server)"
    payment_addr = service.get("payment_address") or service.get("paymentAddress", "")
    token = service.get("tokenId", "SETH")
    chain = service.get("chainId", "SETH")
    desc = service["description"]
    return f"""╔══════════════════════════════════════════╗
║  {service['name'][:38]:<38s}║
║  Generated: {ts}      ║
╚══════════════════════════════════════════╝

Service:        {service['name']}
Description:    {desc}
Protocol:       {service.get('protocol', 'x402')}
Service ID:     {sid}
Token:          {token}
Chain:          {chain}
Seller Payment: {payment_addr[:14]}...
Endpoint:       {endpoint}

Payment:
Amount Paid:    0.00005 {token}
Status:         Paid & Verified
Proof Type:     On-chain transaction

Request Query:  {query or "(no specific query)"}

---
Delivered by Agent Commerce Hub. Payment verified on-chain via x402.
"""


# ── Models ──────────────────────────────────────────────────────

class PaymentInfo(BaseModel):
    chain_id: str
    token_id: str
    amount: str
    address: str
    service_id: int


class ServiceRequest(BaseModel):
    service_id: int = 4
    query: str = ""


class PaymentVerification(BaseModel):
    tx_hash: str
    service_id: int


class RegisterV2Request(BaseModel):
    """Request body for on-chain provider registration."""
    name: str
    description: str = ""
    price_seth: str = "0.00001"
    endpoint_uri: str = ""
    token_id: str = "SETH"
    chain_id: str = "SETH"
    protocol: str = "x402"
    seller_address: Optional[str] = None
    payment_address: Optional[str] = None


# ── Error Response Helper ────────────────────────────────────────

X402_HEADER = "X-Payment-Info"


def _payment_required(service: dict) -> JSONResponse:
    """Return 402 Payment Required with payment info."""
    payment_info = json.dumps({
        "chain_id": service["chain_id"],
        "token_id": service["token_id"],
        "amount": service["price_seth"],
        "address": service["payment_address"],
        "service_id": service["id"],
    })
    content = {
        "error": "payment_required",
        "message": f"Payment of {service['price_seth']} {service['token_id']} required",
        "payment": json.loads(payment_info),
    }
    return JSONResponse(
        status_code=402,
        content=content,
        headers={X402_HEADER: payment_info},
    )


# ── Routes ──────────────────────────────────────────────────────

@x402_app.post("/request")
async def x402_request(
    payload: ServiceRequest,
    tx_hash: Optional[str] = Query(None),
):
    """Request a paid service. Returns 402 if unpaid, 200 if paid.

    Reads the service from the on-chain ServiceRegistryV2. Returns 404 if the
    service does not exist, is inactive, or its endpointURI points to a
    different server.

    Query params:
        tx_hash: On-chain transaction hash proving payment (optional)
    """
    chain = _get_chain()
    try:
        raw = chain.get_service(payload.service_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found")

    # A non-existent service comes back with id=0 / empty fields
    if not raw or raw["id"] != payload.service_id or not raw["name"]:
        raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found")

    if not raw["active"]:
        raise HTTPException(status_code=404, detail=f"Service {payload.service_id} is inactive")

    # Reject services hosted on a different server
    if not _endpoint_is_local(raw["endpointURI"]):
        raise HTTPException(
            status_code=404,
            detail=f"Service {payload.service_id} is served by another endpoint: {raw['endpointURI']}",
        )

    service = _normalize_service(raw)

    # No payment provided → 402 Payment Required
    if not tx_hash:
        return _payment_required(service)

    # Payment provided → verify it
    is_valid = _verify_payment(
        tx_hash=tx_hash,
        expected_amount=service["price_seth"],
        expected_address=service["payment_address"],
    )
    if not is_valid:
        return JSONResponse(
            status_code=402,
            content={
                "error": "payment_invalid",
                "message": "Payment verification failed — please send exact amount to the service address",
                "payment": {
                    "chain_id": service["chain_id"],
                    "token_id": service["token_id"],
                    "amount": service["price_seth"],
                    "address": service["payment_address"],
                },
            },
            headers={X402_HEADER: json.dumps({
                "chain_id": service["chain_id"],
                "token_id": service["token_id"],
                "amount": service["price_seth"],
                "address": service["payment_address"],
                "service_id": service["id"],
            })},
        )

    # Payment verified → serve content
    analysis = _generate_analysis(service, payload.query)

    proof = None
    proof_error = None
    try:
        summary = f"Delivered {service['name']} via x402"
        if payload.query:
            summary = f"{summary}: {payload.query[:120]}"
        proof = chain.record_delivery(service["id"], tx_hash, summary[:240])
    except Exception as exc:
        # Delivery must still succeed after verified payment; surface proof errors
        # so the web UI/API can show why /api/proofs may not include this row yet.
        proof_error = str(exc)[:500]

    # Record revenue
    _revenue[service["id"]] = _revenue.get(service["id"], 0.0) + float(service["price_seth"])
    _revenue_log.append({
        "service_id": service["id"],
        "service_name": service["name"],
        "amount": float(service["price_seth"]),
        "tx_hash": tx_hash,
        "timestamp": time.time(),
    })

    response = {
        "status": "delivered",
        "service": service["name"],
        "amount_paid": service["price_seth"],
        "tx_hash": tx_hash,
        "content": analysis,
        "proof": proof,
    }
    if proof_error:
        response["proof_error"] = proof_error
    return response


@x402_app.get("/services")
async def x402_services(request: Request):
    """List all active services available for purchase.

    Returns a flat list of service dicts with id, name, description,
    price (SETH), token, chain, address, protocol, etc.
    """
    chain = _get_chain()
    try:
        raw_list = chain.list_services(0, 200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list services: {e}")

    public_base = _public_base_url(request)

    services = []
    for svc in raw_list:
        if not svc["active"]:
            continue
        if Web3 is not None:
            price_seth = str(Web3.from_wei(svc["priceWei"], "ether"))
        else:
            price_seth = str(svc["priceWei"] / 1e18)
        services.append({
            "id": svc["id"],
            "name": svc["name"],
            "description": svc["description"],
            "price": price_seth,
            "token": svc["tokenId"] or "SETH",
            "chain": svc["chainId"] or "SETH",
            "address": svc["paymentAddress"],
            "payment_address": svc["paymentAddress"],
            "provider": svc["provider"],
            "endpoint": _normalize_public_endpoint(svc["endpointURI"], svc["id"], public_base),
            "protocol": svc["protocol"] or "x402",
            "price_usd": f"${float(price_seth) * 3000:.2f}",
            "active": svc["active"],
        })
    return {"services": services}


@x402_app.post("/register_v2")
async def x402_register_v2(payload: RegisterV2Request, x_demo_admin_token: Optional[str] = Header(None)):
    """Register a new service on-chain via ServiceRegistryV2.

    Demo-safety gate: this endpoint spends the server deployer key for gas, so
    non-local callers must provide X-Demo-Admin-Token when DEMO_ADMIN_TOKEN is
    configured. Local/dev calls continue to work for the hackathon demo.
    """
    admin_token = os.environ.get("DEMO_ADMIN_TOKEN", "").strip()
    if admin_token and x_demo_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin token required for on-chain registration")

    try:
        price_wei = Web3.to_wei(float(payload.price_seth), "ether")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid price_seth")

    if not payload.endpoint_uri.strip():
        raise HTTPException(status_code=400, detail="endpoint_uri is required")

    payment_addr_raw = (payload.payment_address or payload.seller_address or WALLET_SETH_ADDR).strip()
    try:
        payment_addr = Web3.to_checksum_address(payment_addr_raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid seller/payment address")

    chain = _get_chain()
    try:
        result = chain.register_service(
            name=payload.name,
            desc=payload.description,
            payment_addr=payment_addr,
            price_wei=price_wei,
            token_id=payload.token_id,
            chain_id=payload.chain_id,
            endpoint_uri=payload.endpoint_uri.strip(),
            protocol=payload.protocol,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"On-chain registration failed: {exc}")

    if result.get("status") != 1:
        raise HTTPException(status_code=500, detail=f"Registration tx failed: {result.get('tx_hash')}")

    return {
        "status": "registered",
        "service_id": result.get("service_id"),
        "tx_hash": result.get("tx_hash"),
        "block": result.get("block"),
        "name": payload.name,
        "price_seth": payload.price_seth,
        "payment_address": payment_addr,
        "provider": X402_PROVIDER,
        "endpoint_uri": payload.endpoint_uri.strip(),
    }


@x402_app.get("/revenue")
async def x402_revenue():
    """Show total revenue earned by this agent."""
    total = sum(_revenue.values())

    by_service = {}
    chain = _get_chain()
    for sid, amt in _revenue.items():
        if amt <= 0:
            continue
        name = f"Service #{sid}"
        try:
            svc = chain.get_service(sid)
            if svc and svc.get("name"):
                name = svc["name"]
        except Exception:
            pass
        by_service[str(sid)] = {"name": name, "earned_seth": amt}

    return {
        "total_seth": total,
        "total_usd": f"${total * 3000:.2f}",
        "tx_count": len(_revenue_log),
        "by_service": by_service,
        "recent_txs": _revenue_log[-5:],
    }


@x402_app.get("/health")
async def x402_health():
    """Health check with wallet status."""
    try:
        import subprocess
        result = subprocess.run(["caw", "status"], capture_output=True, text=True, timeout=15)
        status = json.loads(result.stdout)
        balance = subprocess.run(
            ["caw", "wallet", "balance"],
            capture_output=True, text=True, timeout=15,
        )
        balance_data = json.loads(balance.stdout)
        seth_balance = "0"
        for b in balance_data.get("result", []):
            if b.get("token_id") == "SETH":
                seth_balance = b.get("amount", "0")
                break

        active_count = None
        try:
            active_count = _get_chain().get_active_service_count()
        except Exception:
            pass

        return {
            "healthy": status.get("healthy", False),
            "wallet_paired": status.get("wallet_paired", False),
            "wallet_status": status.get("wallet_status", ""),
            "buyer_caw_address": WALLET_SETH_ADDR,
            "provider": X402_PROVIDER,
            "balance_seth": seth_balance,
            "active_services_onchain": active_count,
            "total_revenue_seth": sum(_revenue.values()),
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}


# ── Standalone entry ────────────────────────────────────────────

def serve(host: str = "0.0.0.0", port: int = 8888):
    """Start the x402 service server."""
    print(f"\n  🤖 Agent Commerce Hub — x402 Service Provider (V2 on-chain)")
    print(f"  ─────────────────────────────────────────────")
    try:
        chain = _get_chain()
        print(f"  Registry: {chain.contract_addr}")
        print(f"  Active services: {chain.get_active_service_count()}")
    except Exception as e:
        print(f"  ⚠️  Could not reach V2 registry: {e}")
    print(f"  Provider: {X402_PROVIDER}")
    print(f"  Buyer CAW: {WALLET_SETH_ADDR[:14]}...")
    print(f"  Listen:   http://{host}:{port}")
    print(f"  Endpoint: POST /request?tx_hash=0x...")
    print(f"  Register: POST /register_v2")
    print(f"  Revenue:  GET  /revenue")
    print()
    uvicorn.run(x402_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    serve()
