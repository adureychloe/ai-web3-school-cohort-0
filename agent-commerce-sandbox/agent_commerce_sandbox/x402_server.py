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

import hashlib
import json
import os
import sys
import time
from decimal import Decimal
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


def json_safe(value):
    """Convert web3 return values into JSON-serializable objects."""
    if isinstance(value, dict) or hasattr(value, "items"):
        try:
            items = value.items()
        except Exception:
            items = []
        return {str(k): json_safe(v) for k, v in items}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "hex") and not isinstance(value, (str, int, float, bool)):
        try:
            hex_value = value.hex()
            return hex_value if str(hex_value).startswith("0x") else "0x" + str(hex_value)
        except Exception:
            pass
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


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

# Replay protection for seller self-service signatures.
_used_seller_remove_messages: set[str] = set()

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


def _require_admin_token(x_demo_admin_token: Optional[str], *, fail_closed: bool = False) -> None:
    """Require the demo admin token when configured.

    Admin-only lifecycle routes pass fail_closed=True so they are unavailable
    unless the operator has explicitly configured DEMO_ADMIN_TOKEN. Seller
    self-service routes use wallet signatures instead of this admin token.
    """
    admin_token = os.environ.get("DEMO_ADMIN_TOKEN", "").strip()
    if not admin_token:
        if fail_closed:
            raise HTTPException(status_code=403, detail="Admin lifecycle is disabled because DEMO_ADMIN_TOKEN is not configured")
        return
    if x_demo_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin token required for on-chain service changes")


def _list_services_including_inactive(chain: ChainClientV2, limit: int = 200) -> list[dict]:
    """List V2 services by id so admin views can include inactive rows."""
    count = min(int(chain.get_service_count()), limit)
    services = []
    for service_id in range(1, count + 1):
        try:
            svc = chain.get_service(service_id)
        except Exception:
            continue
        if svc and svc.get("id") == service_id and svc.get("name"):
            services.append(svc)
    return services


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


def _normalize_address(addr: str) -> str:
    """Validate and checksum-normalize an EVM address."""
    try:
        return Web3.to_checksum_address((addr or "").strip())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid seller address")


def _service_provider_is_server_owner(raw_service: dict) -> bool:
    """Return True when the service provider is this demo server owner key."""
    try:
        provider = _normalize_address(raw_service.get("provider", ""))
        owner = _normalize_address(X402_PROVIDER)
    except HTTPException:
        return False
    return provider == owner


def _seller_owns_raw_service(raw_service: dict, seller: str) -> bool:
    """Return True if seller is related to the service for dashboard listing.

    A service provider may see its own service in the seller dashboard. Payment
    address ownership is accepted only for services registered by the hosted
    server owner/deployer (X402_PROVIDER). Mutating self-service routes perform
    an additional server-owned-provider gate before submitting any transaction.
    """
    try:
        seller_norm = _normalize_address(seller).lower()
        provider = _normalize_address(raw_service.get("provider", "")).lower()
    except HTTPException:
        return False

    if seller_norm == provider:
        return True

    if not _service_provider_is_server_owner(raw_service):
        return False

    try:
        payment = _normalize_address(raw_service.get("paymentAddress", "")).lower()
    except HTTPException:
        return False
    return seller_norm == payment


def _require_self_service_seller(raw_service: dict, seller_address: str) -> str:
    """Require seller_address to be authorized for seller self-service removal."""
    seller = _normalize_address(seller_address)
    if not _seller_owns_raw_service(raw_service, seller):
        raise HTTPException(
            status_code=403,
            detail="Seller address is not authorized for this service (paymentAddress is allowed only for services whose provider is the server owner)",
        )
    return seller


def _normalize_origin_value(value: str) -> Optional[str]:
    """Return scheme://host[:port] for a browser origin-like value."""
    if not value:
        return None
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _request_origin_candidates(request: Request) -> set[str]:
    """Return acceptable origins for seller-signed browser messages."""
    candidates: set[str] = set()
    for value in (
        request.headers.get("origin", ""),
        request.headers.get("referer", ""),
        _public_base_url(request) or "",
        str(request.base_url).rstrip("/"),
    ):
        origin = _normalize_origin_value(value)
        if origin:
            candidates.add(origin)
    return candidates


def _chain_signature_chain_id(chain: ChainClientV2) -> str:
    """Return the registry EVM chain id used in seller remove signatures."""
    return str(getattr(chain, "chain_id", "") or "")


def _validate_seller_action_message(
    *,
    seller: str,
    service_id: int,
    message: str,
    raw_service: dict,
    chain: ChainClientV2,
    request: Request,
    action: str = "remove_v2",
    extra_fields: Optional[dict[str, object]] = None,
) -> dict:
    """Parse and validate the exact seller-signed self-service message fields."""
    action_label = "update" if action == "update_v2" else "remove"
    if not message:
        raise HTTPException(status_code=400, detail=f"Seller {action_label} message is required")
    message = message.strip()
    try:
        data = json.loads(message)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Seller {action_label} message must be JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail=f"Seller {action_label} message must be a JSON object")

    expected_fields = {
        "action",
        "service_id",
        "seller_address",
        "chain_id",
        "contract_address",
        "origin",
        "expires_at",
    } | set((extra_fields or {}).keys())
    if set(data.keys()) != expected_fields:
        raise HTTPException(status_code=400, detail=f"Seller {action_label} message fields do not match {action} schema")
    if data.get("action") != action:
        raise HTTPException(status_code=400, detail=f"Invalid seller {action_label} action")

    for field, expected in (extra_fields or {}).items():
        actual = data.get(field)
        if str(actual if actual is not None else "") != str(expected if expected is not None else ""):
            raise HTTPException(status_code=400, detail=f"Seller {action_label} {field} mismatch")

    try:
        msg_service_id = int(data.get("service_id"))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid seller {action_label} service_id")
    if msg_service_id != int(service_id):
        raise HTTPException(status_code=400, detail=f"Seller {action_label} service_id mismatch")

    msg_seller = _normalize_address(str(data.get("seller_address") or ""))
    if msg_seller.lower() != seller.lower():
        raise HTTPException(status_code=400, detail=f"Seller {action_label} seller_address mismatch")

    expected_chain_id = _chain_signature_chain_id(chain)
    if str(data.get("chain_id")) != expected_chain_id:
        raise HTTPException(status_code=400, detail=f"Seller {action_label} chain_id mismatch")

    try:
        msg_contract = _normalize_address(str(data.get("contract_address") or ""))
        expected_contract = _normalize_address(chain.contract_addr)
    except HTTPException:
        raise HTTPException(status_code=400, detail=f"Invalid seller {action_label} contract_address")
    if msg_contract.lower() != expected_contract.lower():
        raise HTTPException(status_code=400, detail=f"Seller {action_label} contract_address mismatch")

    msg_origin = _normalize_origin_value(str(data.get("origin") or ""))
    if not msg_origin:
        raise HTTPException(status_code=400, detail=f"Invalid seller {action_label} origin")
    origin_candidates = _request_origin_candidates(request)
    if origin_candidates and msg_origin not in origin_candidates:
        raise HTTPException(status_code=403, detail=f"Seller {action_label} origin mismatch")

    try:
        expires_at = int(data.get("expires_at"))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid seller {action_label} expires_at")
    now_ts = int(time.time())
    if expires_at <= now_ts:
        raise HTTPException(status_code=400, detail=f"Seller {action_label} signature has expired")
    if expires_at > now_ts + 3600:
        raise HTTPException(status_code=400, detail=f"Seller {action_label} expiry is too far in the future")

    return data


def _validate_seller_remove_message(
    *,
    seller: str,
    service_id: int,
    message: str,
    raw_service: dict,
    chain: ChainClientV2,
    request: Request,
) -> dict:
    """Parse and validate the exact seller remove_v2 signed message fields."""
    return _validate_seller_action_message(
        seller=seller,
        service_id=service_id,
        message=message,
        raw_service=raw_service,
        chain=chain,
        request=request,
        action="remove_v2",
    )


def _verify_self_service_signature(
    *,
    seller: str,
    service_id: int,
    message: str,
    signature: str,
    raw_service: dict,
    chain: ChainClientV2,
    request: Request,
    action: str = "remove_v2",
    extra_fields: Optional[dict[str, object]] = None,
) -> dict[str, str]:
    """Verify an EIP-191 seller signature for self-service service management.

    Returns replay metadata for the caller to consume only after the on-chain
    transaction succeeds. This avoids burning a valid seller authorization when
    gas submission or execution fails.
    """
    action_label = "update" if action == "update_v2" else "remove"
    _validate_seller_action_message(
        seller=seller,
        service_id=service_id,
        message=message,
        raw_service=raw_service,
        chain=chain,
        request=request,
        action=action,
        extra_fields=extra_fields,
    )
    if not signature:
        raise HTTPException(status_code=400, detail=f"Seller signature is required for self-service {action_label}")

    replay_key = hashlib.sha256(message.encode("utf-8")).hexdigest()
    if replay_key in _used_seller_remove_messages:
        raise HTTPException(status_code=409, detail=f"Seller {action_label} signature has already been used")

    try:
        from eth_account.account import Account
        from eth_account.messages import encode_defunct
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Seller signature verification failed: {exc}")
    if recovered.lower() != seller.lower():
        raise HTTPException(status_code=403, detail="Seller signature does not match seller address")

    return {"replay_key": replay_key, "recovered": recovered}


def _mark_self_service_signature_used(verification: dict[str, str]) -> None:
    """Consume a verified seller self-service signature after tx success."""
    replay_key = verification.get("replay_key")
    if replay_key:
        _used_seller_remove_messages.add(replay_key)


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


class UpdateV2Request(BaseModel):
    """Request body for updating mutable ServiceRegistryV2 metadata."""
    service_id: int
    name: str
    description: str = ""
    price_seth: str = "0.00001"
    endpoint_uri: str = ""
    seller_address: Optional[str] = None
    payment_address: Optional[str] = None


class ServiceLifecycleRequest(BaseModel):
    """Request body for activating/deactivating a ServiceRegistryV2 service."""
    service_id: int


class SellerRemoveServiceRequest(BaseModel):
    """Seller self-service removal request for a ServiceRegistryV2 service."""
    service_id: int
    seller_address: str
    message: str = ""
    signature: str = ""


class SellerUpdateServiceRequest(UpdateV2Request):
    """Seller self-service update request for a ServiceRegistryV2 service."""
    seller_address: str
    message: str = ""
    signature: str = ""


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

    response = json_safe({
        "status": "delivered",
        "service": service["name"],
        "amount_paid": service["price_seth"],
        "tx_hash": tx_hash,
        "content": analysis,
        "proof": proof,
    })
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
        if str(svc.get("protocol") or "x402").lower() != "x402":
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
    _require_admin_token(x_demo_admin_token)

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
            name=payload.name.strip(),
            desc=payload.description,
            payment_addr=payment_addr,
            price_wei=price_wei,
            token_id=payload.token_id,
            chain_id=payload.chain_id,
            endpoint_uri=payload.endpoint_uri.strip(),
            protocol=payload.protocol.strip() or "x402",
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
        "name": payload.name.strip(),
        "price_seth": payload.price_seth,
        "payment_address": payment_addr.lower(),
        "provider": X402_PROVIDER,
        "endpoint_uri": payload.endpoint_uri.strip(),
    }


@x402_app.get("/admin/services")
async def x402_admin_services(
    request: Request,
    x_demo_admin_token: Optional[str] = Header(None),
):
    """List V2 services, including inactive ones, for seller/admin lifecycle controls."""
    _require_admin_token(x_demo_admin_token, fail_closed=True)
    chain = _get_chain()
    public_base = _public_base_url(request)
    try:
        raw_list = _list_services_including_inactive(chain)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list admin services: {exc}")

    services = []
    for svc in raw_list:
        item = _normalize_service(svc)
        item["endpoint"] = _normalize_public_endpoint(svc["endpointURI"], svc["id"], public_base)
        services.append(item)
    return {"services": services}




@x402_app.get("/seller/services_v2")
async def x402_seller_services_v2(
    request: Request,
    seller_address: str = Query(..., description="Seller/provider/payment EVM address"),
):
    """List services owned by a seller wallet without requiring admin token.

    Ownership mirrors seller self-service authorization: this server can submit
    provider-only update/deactivate transactions only for services whose
    provider is the hosted server owner (X402_PROVIDER). Within that subset,
    either the provider or current paymentAddress may manage the service.
    Inactive services are included so sellers can see lifecycle state after a
    soft delete.
    """
    seller = _normalize_address(seller_address)
    chain = _get_chain()
    public_base = _public_base_url(request)
    try:
        raw_list = _list_services_including_inactive(chain)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list seller services: {exc}")

    services = []
    for svc in raw_list:
        if str(svc.get("protocol") or "x402").lower() != "x402":
            continue
        if not _seller_owns_raw_service(svc, seller):
            continue
        item = _normalize_service(svc)
        item["endpoint"] = _normalize_public_endpoint(svc["endpointURI"], svc["id"], public_base)
        item["seller_remove_authorized"] = _service_provider_is_server_owner(svc)
        item["seller_update_authorized"] = item["seller_remove_authorized"]
        item["payment_address_authorized"] = (
            _service_provider_is_server_owner(svc)
            and (svc.get("paymentAddress") or "").lower() == seller.lower()
        )
        services.append(item)

    return {
        "seller_address": seller,
        "chain_id": _chain_signature_chain_id(chain),
        "contract_address": chain.contract_addr,
        "x402_provider": X402_PROVIDER,
        "services": services,
    }


@x402_app.post("/update_v2")
async def x402_update_v2(payload: UpdateV2Request, x_demo_admin_token: Optional[str] = Header(None)):
    """Update mutable metadata for a ServiceRegistryV2 service."""
    _require_admin_token(x_demo_admin_token, fail_closed=True)
    if payload.service_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid service_id")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not payload.endpoint_uri.strip():
        raise HTTPException(status_code=400, detail="endpoint_uri is required")

    try:
        price_wei = Web3.to_wei(float(payload.price_seth), "ether")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid price_seth")

    chain = _get_chain()
    payment_addr_raw = (payload.payment_address or payload.seller_address or "").strip()
    if not payment_addr_raw:
        try:
            current = chain.get_service(payload.service_id)
            payment_addr_raw = current.get("paymentAddress", "")
        except Exception:
            payment_addr_raw = ""
    try:
        payment_addr = Web3.to_checksum_address(payment_addr_raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid seller/payment address")

    try:
        result = chain.update_service(
            service_id=payload.service_id,
            name=payload.name.strip(),
            desc=payload.description,
            price_wei=price_wei,
            payment_addr=payment_addr,
            endpoint_uri=payload.endpoint_uri.strip(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"On-chain update failed: {exc}")

    if result.get("status") != 1:
        raise HTTPException(status_code=500, detail=f"Update tx failed: {result.get('tx_hash')}")

    return {
        "status": "updated",
        "service_id": payload.service_id,
        "tx_hash": result.get("tx_hash"),
        "block": result.get("block"),
    }


@x402_app.post("/deactivate_v2")
async def x402_deactivate_v2(payload: ServiceLifecycleRequest, x_demo_admin_token: Optional[str] = Header(None)):
    """Admin/demo deactivate for a ServiceRegistryV2 service."""
    _require_admin_token(x_demo_admin_token, fail_closed=True)
    if payload.service_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid service_id")
    try:
        result = _get_chain().deactivate_service(payload.service_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"On-chain deactivate failed: {exc}")
    if result.get("status") != 1:
        raise HTTPException(status_code=500, detail=f"Deactivate tx failed: {result.get('tx_hash')}")
    return {"status": "deactivated", "service_id": payload.service_id, "tx_hash": result.get("tx_hash"), "block": result.get("block")}


@x402_app.post("/seller/update_v2")
async def x402_seller_update_v2(payload: SellerUpdateServiceRequest, request: Request):
    """Seller self-service metadata update for a ServiceRegistryV2 service.

    The seller signs the exact metadata fields before this demo server spends its
    configured gas key to submit updateService(). No admin/product token is used.
    """
    if payload.service_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid service_id")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not payload.endpoint_uri.strip():
        raise HTTPException(status_code=400, detail="endpoint_uri is required")

    try:
        price_wei = Web3.to_wei(float(payload.price_seth), "ether")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid price_seth")

    chain = _get_chain()
    try:
        raw = chain.get_service(payload.service_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found")
    if not raw or raw.get("id") != payload.service_id or not raw.get("name"):
        raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found")
    if not raw.get("active"):
        raise HTTPException(status_code=409, detail=f"Service {payload.service_id} is inactive")

    if not _service_provider_is_server_owner(raw):
        raise HTTPException(
            status_code=403,
            detail="Seller self-service update is available only for services whose on-chain provider is the server owner",
        )

    seller = _require_self_service_seller(raw, payload.seller_address)
    payment_addr_raw = (payload.payment_address or "").strip()
    if not payment_addr_raw:
        raise HTTPException(status_code=400, detail="payment_address is required for seller update")
    try:
        payment_addr = Web3.to_checksum_address(payment_addr_raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid seller/payment address")

    signed_fields = {
        "name": payload.name.strip(),
        "description": payload.description,
        "price_seth": payload.price_seth,
        "payment_address": payment_addr.lower(),
        "endpoint_uri": payload.endpoint_uri.strip(),
    }
    verification = _verify_self_service_signature(
        seller=seller,
        service_id=payload.service_id,
        message=payload.message,
        signature=payload.signature,
        raw_service=raw,
        chain=chain,
        request=request,
        action="update_v2",
        extra_fields=signed_fields,
    )

    try:
        result = chain.update_service(
            service_id=payload.service_id,
            name=payload.name.strip(),
            desc=payload.description,
            price_wei=price_wei,
            payment_addr=payment_addr,
            endpoint_uri=payload.endpoint_uri.strip(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"On-chain seller update failed: {exc}")
    if result.get("status") != 1:
        raise HTTPException(status_code=500, detail=f"Seller update tx failed: {result.get('tx_hash')}")
    _mark_self_service_signature_used(verification)

    return {
        "status": "updated",
        "service_id": payload.service_id,
        "seller_address": seller,
        "tx_hash": result.get("tx_hash"),
        "block": result.get("block"),
    }


@x402_app.post("/seller/remove_v2")
async def x402_seller_remove_v2(payload: SellerRemoveServiceRequest, request: Request):
    """Seller self-service soft delete for a ServiceRegistryV2 service.

    Uses the contract's existing deactivate() primitive, so removed services are
    hidden from buyer discovery but retained on-chain for history/proofs. The
    deployed demo server still pays gas with TEST_PRIVATE_KEY; before doing so
    it verifies the connected seller address owns the service and signed the
    exact removal message.
    """
    if payload.service_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid service_id")

    chain = _get_chain()
    try:
        raw = chain.get_service(payload.service_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found")
    if not raw or raw.get("id") != payload.service_id or not raw.get("name"):
        raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found")
    if not raw.get("active"):
        raise HTTPException(status_code=409, detail=f"Service {payload.service_id} is already inactive")

    if not _service_provider_is_server_owner(raw):
        raise HTTPException(
            status_code=403,
            detail="Seller self-service remove is available only for services whose on-chain provider is the server owner",
        )

    seller = _require_self_service_seller(raw, payload.seller_address)
    verification = _verify_self_service_signature(
        seller=seller,
        service_id=payload.service_id,
        message=payload.message,
        signature=payload.signature,
        raw_service=raw,
        chain=chain,
        request=request,
    )

    try:
        result = chain.remove_service(payload.service_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"On-chain seller remove failed: {exc}")
    if result.get("status") != 1:
        raise HTTPException(status_code=500, detail=f"Seller remove tx failed: {result.get('tx_hash')}")
    _mark_self_service_signature_used(verification)
    return {
        "status": "removed",
        "action": "soft_deactivated",
        "service_id": payload.service_id,
        "seller_address": seller,
        "tx_hash": result.get("tx_hash"),
        "block": result.get("block"),
        "message": "Service removed from buyer discovery via ServiceRegistryV2.deactivate().",
    }


@x402_app.post("/reactivate_v2")
async def x402_reactivate_v2(payload: ServiceLifecycleRequest, x_demo_admin_token: Optional[str] = Header(None)):
    """Reactivate a ServiceRegistryV2 service."""
    _require_admin_token(x_demo_admin_token, fail_closed=True)
    if payload.service_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid service_id")
    try:
        result = _get_chain().reactivate_service(payload.service_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"On-chain reactivate failed: {exc}")
    if result.get("status") != 1:
        raise HTTPException(status_code=500, detail=f"Reactivate tx failed: {result.get('tx_hash')}")
    return {"status": "reactivated", "service_id": payload.service_id, "tx_hash": result.get("tx_hash"), "block": result.get("block")}


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

        chain_id = None
        contract_addr = None
        try:
            chain = _get_chain()
            chain_id = _chain_signature_chain_id(chain)
            contract_addr = chain.contract_addr
        except Exception:
            pass

        return {
            "healthy": status.get("healthy", False),
            "wallet_paired": status.get("wallet_paired", False),
            "wallet_status": status.get("wallet_status", ""),
            "buyer_caw_address": WALLET_SETH_ADDR,
            "provider": X402_PROVIDER,
            "x402_provider": X402_PROVIDER,
            "chain_id": chain_id,
            "contract_address": contract_addr,
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
