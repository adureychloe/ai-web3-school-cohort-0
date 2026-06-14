"""FastAPI web server for Agent Commerce Hub.

The web layer calls the existing sandbox engine functions and exposes them as
JSON APIs for the single-page interface in web/index.html.
"""

import asyncio
import inspect
import io
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent_commerce_sandbox.engine import discover_services, pay_for_service, show_proofs
from agent_commerce_sandbox.procurement_agent import match_and_rank, get_balance, format_price
from agent_commerce_sandbox.chain_client import ChainClient
from agent_commerce_sandbox.chain_client_v2 import ChainClientV2
from agent_commerce_sandbox.caw_client import WALLET_SETH_ADDR

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
    wallet_address: Optional[str] = None


class SellerAgentRegisterRequest(BaseModel):
    service_brief: str = Field(..., min_length=1, max_length=4000)
    seller_address: str = Field(..., min_length=1, max_length=100)
    price_seth: str = Field(..., min_length=1, max_length=64)
    endpoint_uri: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = Field(default=None, max_length=120)


def json_safe(value: Any) -> Any:
    """Convert web3 and CLI return values into JSON-serializable objects.
    Also strips sensitive fields (api_key) to prevent credential leaks.
    """
    if isinstance(value, dict) or hasattr(value, "items"):
        try:
            items = value.items()
        except Exception:
            items = []
        return {str(k): json_safe(v) for k, v in items
                if str(k).lower() not in _SENSITIVE_PACT_FIELDS}
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


# Fields to strip from pact data before sending to browser (credential leak prevention)
_SENSITIVE_PACT_FIELDS = {"api_key"}


def _sanitize_pact(pact: dict) -> dict:
    """Strip sensitive fields from pact data before returning to browser."""
    if not isinstance(pact, dict):
        return pact
    return {k: v for k, v in pact.items() if k.lower() not in _SENSITIVE_PACT_FIELDS}


def _is_valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _build_seller_agent_metadata(service_brief: str, category: Optional[str] = None) -> dict[str, str]:
    brief = " ".join((service_brief or "").strip().split())
    category_text = " ".join((category or "").strip().split())
    words = re.findall(r"[A-Za-z0-9]+", brief)
    if category_text:
        name_root = f"{category_text.title()} Agent"
    else:
        name_root = "Seller Agent"
    if words:
        headline = " ".join(words[: min(8, len(words))])
        name = f"{headline[:72].strip()}".strip()
        if category_text and category_text.lower() not in name.lower():
            name = f"{category_text.title()} {name}"
        description = f"{brief}"
        if category_text:
            description = f"{category_text.title()}: {brief}"
    else:
        name = name_root
        description = category_text or "Seller-facing service registration from a brief."
    name = name.strip(" -:;,") or name_root
    if not name:
        name = name_root
    description = description.strip()
    if not description:
        description = f"{name} service derived from the seller brief."
    return {"name": name, "description": description}


async def _register_v2_service_from_agent(service: Optional[dict[str, Any]] = None, **kwargs: Any) -> dict[str, Any]:
    from agent_commerce_sandbox.x402_server import RegisterV2Request, register_v2_service

    payload = dict(service or {})
    payload.update(kwargs)
    allowed = {"name", "description", "price_seth", "endpoint_uri", "token_id", "chain_id", "protocol", "seller_address", "payment_address"}
    request = RegisterV2Request(**{k: v for k, v in payload.items() if k in allowed})
    return await to_thread(register_v2_service, request)


async def register_v2_service_from_agent(service: Optional[dict[str, Any]] = None, **kwargs: Any) -> dict[str, Any]:
    return await _register_v2_service_from_agent(service=service, **kwargs)


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


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


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
        item["sellerPaymentAddress"] = svc.get("paymentAddress")
        item["sellerProvider"] = svc.get("provider")
        item["buyerPairedCawAddress"] = WALLET_SETH_ADDR
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
        terminal = str(status).lower() in {"rejected", "revoked", "expired", "completed", "cancelled", "failed"}
        return {"pact_id": pact_id, "status": status, "terminal": terminal, "pact": json_safe(_sanitize_pact(pact))}
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
        result = await api_x402_buy(X402BuyRequest(service_id=best["id"], query=payload.request, wallet_address=payload.wallet_address))
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
    max_price_wei: Optional[int] = Field(default=None, ge=0)


class BuyerAgentProcureRequest(BaseModel):
    request: str = Field(..., min_length=1, max_length=1000)
    budget_seth: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    wallet_address: Optional[str] = None
    auto_pay: bool = False
    max_candidates: int = Field(default=5, ge=1, le=50)


_WEI_PER_SETH = Decimal(10) ** 18


def _format_decimal_plain(value: Decimal) -> str:
    """Return a deterministic, non-scientific decimal string."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _service_price_wei(service: dict[str, Any]) -> Optional[Decimal]:
    """Read a service priceWei value as Decimal for exact budget filtering."""
    try:
        price = service.get("priceWei")
        if price is None:
            return None
        return Decimal(str(price))
    except Exception:
        return None


def _wei_value_to_int(value: Any, field_name: str) -> int:
    """Parse an integer wei value from API/chain data without losing precision."""
    try:
        wei = Decimal(str(value).strip())
    except Exception as exc:
        raise ValueError(f"Invalid {field_name}: expected an integer wei amount") from exc
    if not wei.is_finite() or wei < 0:
        raise ValueError(f"Invalid {field_name}: expected a non-negative wei amount")
    integral = wei.to_integral_value()
    if wei != integral:
        raise ValueError(f"Invalid {field_name}: wei amount must be an integer")
    return int(integral)


def _seth_amount_to_wei(value: Any, field_name: str) -> int:
    """Convert a SETH decimal amount string to integer wei exactly."""
    try:
        amount = Decimal(str(value).strip())
    except Exception as exc:
        raise ValueError(f"Invalid {field_name}: expected a SETH decimal amount") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"Invalid {field_name}: expected a non-negative SETH amount")
    wei = amount * _WEI_PER_SETH
    integral = wei.to_integral_value()
    if wei != integral:
        raise ValueError(f"Invalid {field_name}: SETH amount has more than 18 decimal places")
    return int(integral)


def _x402_service_price_wei(service: dict[str, Any]) -> Optional[int]:
    """Resolve a service price as wei, accepting V2 wei or X402 SETH fields."""
    for key in ("priceWei", "price_wei"):
        if service.get(key) not in (None, ""):
            return _wei_value_to_int(service.get(key), f"service.{key}")
    if service.get("price") not in (None, ""):
        return _seth_amount_to_wei(service.get("price"), "service.price")
    return None


def _resolve_x402_payment(payment: dict[str, Any], service: dict[str, Any]) -> dict[str, Any]:
    """Normalize current x402 payment details for transfer and budget checks.

    The x402 seller endpoint returns ``payment.amount`` as a SETH decimal string,
    while the registry stores prices as wei. Normalize both representations to
    integer wei for comparison, then format a canonical SETH decimal for CAW.
    """
    payment = payment if isinstance(payment, dict) else {}
    if payment.get("amount") not in (None, ""):
        amount_wei = _seth_amount_to_wei(payment.get("amount"), "payment.amount")
    else:
        amount_wei = _x402_service_price_wei(service)
        if amount_wei is None:
            raise ValueError("Invalid x402 payment: missing payment.amount and service price")

    amount_seth = _format_decimal_plain(Decimal(amount_wei) / _WEI_PER_SETH)
    return {
        "amount_wei": amount_wei,
        "amount_seth": amount_seth,
        "token_id": payment.get("token_id") or service.get("token") or "SETH",
        "chain_id": payment.get("chain_id") or service.get("chain") or "SETH",
        "address": payment.get("address") or service.get("address") or "",
    }


def _is_active_x402_service(service: dict[str, Any]) -> bool:
    """Return True for active V2/x402 services."""
    active = service.get("active", True)
    if isinstance(active, str):
        active_ok = active.strip().lower() not in {"0", "false", "no", "off"}
    else:
        active_ok = bool(active)
    protocol = str(service.get("protocol") or "x402").lower()
    return active_ok and protocol == "x402"


def _buyer_agent_candidate(service: dict[str, Any], score: int) -> dict[str, Any]:
    """Build the deterministic candidate object returned by the Buyer Agent."""
    price_wei = _service_price_wei(service)
    candidate = {
        "id": service.get("id"),
        "name": service.get("name"),
        "description": service.get("description", ""),
        "priceWei": service.get("priceWei"),
        "price_seth": _format_decimal_plain(price_wei / _WEI_PER_SETH) if price_wei is not None else None,
        "price_eth": _format_decimal_plain(price_wei / _WEI_PER_SETH) if price_wei is not None else None,
        "score": score,
        "match_score": score,
        "protocol": service.get("protocol", "x402"),
        "paymentAddress": service.get("paymentAddress"),
        "chainId": service.get("chainId"),
        "tokenId": service.get("tokenId"),
        "endpointURI": service.get("endpointURI"),
    }
    # Preserve common V2 seller metadata when present without exposing secrets.
    for key in ("sellerPaymentAddress", "sellerProvider", "provider", "buyerPairedCawAddress"):
        if key in service:
            candidate[key] = service.get(key)
    return json_safe(candidate)


def _buyer_agent_decision_reason(payload: BuyerAgentProcureRequest, candidate_count: int) -> str:
    """Explain the deterministic Buyer Agent decision in one sentence."""
    if payload.budget_seth is None:
        return (
            f"Selected the highest-ranked active x402 service from {candidate_count} "
            "candidate(s); no budget limit was provided."
        )
    return (
        f"Selected the highest-ranked active x402 service within the "
        f"{_format_decimal_plain(payload.budget_seth)} SETH budget from {candidate_count} candidate(s)."
    )


@app.post("/api/agent/seller/register")
async def api_agent_seller_register(
    payload: SellerAgentRegisterRequest,
    x_demo_admin_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Seller Agent: turn a service brief into V2/x402 metadata and register it."""
    try:
        from agent_commerce_sandbox.x402_server import _require_admin_token

        _require_admin_token(x_demo_admin_token)
        brief = " ".join(payload.service_brief.strip().split())
        if not brief:
            raise HTTPException(status_code=400, detail="service_brief is required")

        try:
            price = Decimal(str(payload.price_seth).strip())
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid price_seth") from exc
        if not price.is_finite() or price <= 0:
            raise HTTPException(status_code=400, detail="price_seth must be greater than zero")

        endpoint = payload.endpoint_uri.strip()
        if not _is_valid_http_url(endpoint):
            raise HTTPException(status_code=400, detail="endpoint_uri must be an http(s) URL")

        try:
            seller_address = _verify_address(payload.seller_address)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid seller_address")

        metadata = _build_seller_agent_metadata(brief, payload.category)
        service = {
            **metadata,
            "price_seth": _format_decimal_plain(price),
            "payment_address": seller_address,
            "seller_address": seller_address,
            "endpoint_uri": endpoint,
        }
        if payload.category:
            service["category"] = payload.category.strip()

        timeline = [
            {"step": "parsed_brief", "status": "ok"},
            {"step": "built_metadata", "status": "ok", "name": service["name"]},
        ]

        registration = await _maybe_await(register_v2_service_from_agent(service=service))
        timeline.append({"step": "registered_v2", "status": "ok", "service_id": registration.get("service_id") if isinstance(registration, dict) else None})

        registered_service = dict(service)
        if isinstance(registration, dict) and isinstance(registration.get("service"), dict):
            registered_service.update(registration["service"])
        registered_service["payment_address"] = str(registered_service.get("payment_address") or seller_address).lower()
        registered_service["endpoint_uri"] = str(registered_service.get("endpoint_uri") or endpoint)
        registered_service["price_seth"] = str(registered_service.get("price_seth") or service["price_seth"])

        return json_safe({
            "status": (registration.get("status") if isinstance(registration, dict) else None) or "registered",
            "agent": "seller",
            "service": registered_service,
            "registration": registration,
            "timeline": timeline,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/agent/buyer/procure")
async def api_agent_buyer_procure(payload: BuyerAgentProcureRequest) -> dict[str, Any]:
    """Buyer Agent: discover, budget-filter, rank, and optionally auto-pay."""
    try:
        services = await _list_v2_services()
        active_x402 = [s for s in services if _is_active_x402_service(s)]

        budget_wei: Optional[Decimal] = None
        if payload.budget_seth is not None:
            budget_wei = payload.budget_seth * _WEI_PER_SETH
            eligible = [
                s for s in active_x402
                if (price_wei := _service_price_wei(s)) is not None and price_wei <= budget_wei
            ]
        else:
            eligible = active_x402

        if not eligible:
            raise HTTPException(status_code=404, detail="No active x402 services match the requested budget")

        ranked, match_source = match_and_rank(payload.request, eligible)
        if not ranked:
            raise HTTPException(status_code=404, detail="No active x402 services matched the request")

        selected_score, selected_service = ranked[0]
        candidates = [
            _buyer_agent_candidate(service, int(score))
            for score, service in ranked[:payload.max_candidates]
        ]
        selected_candidate = _buyer_agent_candidate(selected_service, int(selected_score))
        balance = await to_thread(get_balance)

        requested_seth = (
            _format_decimal_plain(payload.budget_seth)
            if payload.budget_seth is not None
            else None
        )
        decision = {
            "service_id": selected_service.get("id"),
            "service_name": selected_service.get("name"),
            "score": int(selected_score),
            "reason": _buyer_agent_decision_reason(payload, len(candidates)),
            "selected_service": selected_candidate,
        }
        budget = {
            "requested_seth": requested_seth,
            "requested_wei": _format_decimal_plain(budget_wei) if budget_wei is not None else None,
            "wallet_address": payload.wallet_address,
            "balance": json_safe(balance),
        }
        timeline = [
            {"step": "list_services", "status": "ok", "count": len(services)},
            {"step": "filter", "status": "ok", "count": len(eligible), "budget_seth": requested_seth},
            {"step": "match", "status": "ok", "source": match_source},
            {"step": "select", "status": "ok", "service_id": selected_service.get("id")},
        ]

        matched_response = {
            "agent": "buyer",
            "status": "matched",
            "decision": decision,
            "candidates": candidates,
            "budget": budget,
            "balance": json_safe(balance),
            "match_source": match_source,
            "timeline": timeline,
        }

        if not payload.auto_pay:
            return json_safe(matched_response)

        purchase_result = await api_x402_buy(X402BuyRequest(
            service_id=int(selected_service.get("id")),
            query=payload.request,
            wallet_address=payload.wallet_address,
            max_price_wei=int(budget_wei) if budget_wei is not None else None,
        ))
        merged = {
            **matched_response,
            **json_safe(purchase_result),
            "agent": "buyer",
            "decision": decision,
            "candidates": candidates,
            "budget": budget,
            "balance": json_safe(balance),
            "match_source": match_source,
        }
        if isinstance(purchase_result, dict) and "timeline" in purchase_result:
            merged["timeline"] = json_safe(purchase_result["timeline"])
        else:
            merged["timeline"] = [*timeline, {"step": "x402_buy", "status": merged.get("status", "ok")}]
        return json_safe(merged)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
        result = json_safe(_json.loads(resp.read()))

        return json_safe({
            "status": "delivered",
            "service_id": payload.service_id,
            "wallet_address": wallet,
            "tx_hash": tx_hash,
            "content": result.get("content", ""),
            "amount_paid": result.get("amount_paid", ""),
            "proof": result.get("proof"),
            "proof_error": result.get("proof_error"),
        })
    except HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise HTTPException(
            status_code=exc.code,
            detail=f"Payment verification failed: {body[:500]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"x402 claim failed: {exc}") from exc


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
        from agent_commerce_sandbox.caw_client import CawClient, PactTerminalStatusError

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

        try:
            resolved_payment = _resolve_x402_payment(payment, svc)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payment = {
            **payment,
            "amount": resolved_payment["amount_seth"],
            "token_id": resolved_payment["token_id"],
            "chain_id": resolved_payment["chain_id"],
            "address": resolved_payment["address"],
        }
        if payload.max_price_wei is not None and resolved_payment["amount_wei"] > payload.max_price_wei:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"x402 payment amount {resolved_payment['amount_wei']} wei exceeds "
                    f"max_price_wei {payload.max_price_wei}; CAW transfer not submitted"
                ),
            )

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

        # No in-memory active pact after restart? Recover a compatible reusable
        # x402-auto-pay Pact from CAW before creating another approval request.
        if not pact_id:
            recovered_pact = caw.find_active_x402_pact(payment)
            if recovered_pact:
                pact_id = recovered_pact.get("id") or recovered_pact.get("pact_id")
                if pact_id:
                    _x402_pact_id = pact_id

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
                except PactTerminalStatusError as exc:
                    if _x402_pact_id == pact_id:
                        _x402_pact_id = None
                    return {
                        "status": "failed",
                        "pact_id": pact_id,
                        "pact": {"pact_id": pact_id, "status": exc.status},
                        "error": f"Pact was {exc.status} in CAW App — purchase cancelled.",
                    }
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
            amount=resolved_payment["amount_seth"],
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
        result = json_safe(_json.loads(resp.read()))
        proof = json_safe(result.get("proof"))

        return json_safe({
            "status": "completed",
            "service": svc["name"],
            "amount_paid": resolved_payment["amount_seth"],
            "tx_hash": tx_hash,
            "reused_pact": not needs_approval and _x402_pact_id is not None,
            "content": result.get("content", ""),
            "proof": proof,
            "proof_error": result.get("proof_error"),
        })

    except HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise HTTPException(
            status_code=exc.code,
            detail=f"x402 seller endpoint rejected the completed payment: {body[:500]}",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"x402 buy failed after CAW step: {exc}") from exc


@app.post("/api/x402-buy")
async def api_x402_buy(payload: X402BuyRequest) -> dict[str, Any]:
    """Full x402 auto-pay flow without blocking the FastAPI event loop."""
    return await asyncio.to_thread(_api_x402_buy_blocking, payload)


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "wallet_healthy": False,
        "demo_mode": "single_paired_caw",
        "paired_caw_address": WALLET_SETH_ADDR,
        "buyer_wallet_note": "Demo mode: purchases use the server-paired CAW for Pact auto-pay. Approve once in CAW App; later x402 buys reuse the Pact.",
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
