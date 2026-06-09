"""
x402 Server — Agent as Seller / Service Provider.

Runs an HTTP endpoint that uses HTTP 402 Payment Required to demand
payment before serving content. Integrated with CAW for payment verification.

Two modes:
  1. Standalone: python3 -m agent_commerce_sandbox.x402_server
  2. Mounted on existing Web UI: app.mount("/x402", x402_app)

Flow:
  Client → POST /x402/request  (no payment)
          ← 402 + X-Payment-Info header
  
  Client → CAW Pact → Transfer  (auto-pay)
  
  Client → POST /x402/request?tx_hash=0x...
          ← 200 + service result
"""

import json
import os
import sys
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

# ── Path setup for running standalone ───────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_commerce_sandbox.chain_client import ChainClient
from agent_commerce_sandbox.caw_client import CawClient, WALLET_SETH_ADDR

x402_app = FastAPI(
    title="Agent Commerce Hub — x402 Service",
    description="HTTP 402 Payment Required endpoint for Agent-to-Agent commerce",
    version="0.5.0",
)

# ── Data ────────────────────────────────────────────────────────

# Service catalog for what THIS agent sells
# In production, read from on-chain ServiceRegistry
SELLER_SERVICES = {
    4: {
        "id": 4,
        "name": "ETH Market Analysis",
        "description": "实时 ETH 市场深度分析，包括链上数据、资金流向和技术指标",
        "price_wei": 50000000000000,  # 0.00005 SETH
        "price_seth": "0.00005",
        "price_usd": "$0.15",
        "token_id": "SETH",
        "chain_id": "SETH",
        "payment_address": WALLET_SETH_ADDR,  # Hermes gets paid
    },
    5: {
        "id": 5,
        "name": "On-chain Research Report",
        "description": "基于链上数据的项目研究报告，含地址分析和交易模式",
        "price_wei": 30000000000000,  # 0.00003 SETH
        "price_seth": "0.00003",
        "price_usd": "$0.09",
        "token_id": "SETH",
        "chain_id": "SETH",
        "payment_address": WALLET_SETH_ADDR,
    },
}

# Track revenue in-memory (for demo; in production use contract events)
_revenue: dict[int, float] = {sid: 0.0 for sid in SELLER_SERVICES}
_revenue_log: list[dict] = []


# ── Helpers ─────────────────────────────────────────────────────

def _verify_payment(tx_hash: str, expected_amount: str, expected_address: str) -> bool:
    """Verify a CAW transfer by checking the tx on-chain.

    Uses etherscan-style verification: checks tx details match expectations.
    """
    try:
        # Use caw to get tx details
        import subprocess
        result = subprocess.run(
            ["caw", "tx", "get", "--request-id", tx_hash],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return False
        data = json.loads(result.stdout)

        # Check it's a completed transfer to our address
        if data.get("status") != "Success":
            return False
        if data.get("sub_status") != "completed":
            return False
        if data.get("dst_address", "").lower() != expected_address.lower():
            return False

        # Amount check (from wei)
        from web3 import Web3
        actual_wei = Web3.to_wei(float(data.get("amount", "0")), "ether")
        expected_wei = Web3.to_wei(float(expected_amount), "ether")
        if actual_wei < expected_wei:
            return False

        return True
    except Exception:
        return False


def _generate_analysis(service_id: int) -> str:
    """Generate a mock analysis result for the paid service."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    analyses = {
        4: f"""╔══════════════════════════════════════════╗
║     ETH Market Analysis Report          ║
║     Generated: {ts}        ║
╚══════════════════════════════════════════╝

Market Overview:
  ETH Price: $3,482.50 (24h: +2.3%)
  Volume:    $18.2B (24h)
  Dominance: 18.4%

On-chain Metrics:
  Active Addresses (24h): 485,320
  Transaction Count: 1,203,847
  Avg Gas Price: 18.5 Gwei
  Total Value Staked: 34.2M ETH

Top Flow Analysis:
  🔴 Exchange Inflow:  124,500 ETH (selling pressure)
  🟢 Exchange Outflow: 89,200 ETH (accumulation)
  🟢 L2 Settlement:    256,800 ETH to Arbitrum

Technical Indicators:
  ─ RSI (14):    62.4 (neutral-bullish)
  ─ MACD:        Bullish crossover detected
  ─ Support:     $3,350 (strong), $3,180 (critical)
  ─ Resistance:  $3,550, $3,720

Sentiment:
  Funding Rate:  0.008% (slightly long-biased)
  Open Interest: $8.4B (+5.2%)
  Long/Short:    1.24x

Summary: Bullish short-term with resistance at $3,550.
Watch for break above $3,550 for continuation to $3,720.
""",
        5: f"""╔══════════════════════════════════════════╗
║     On-chain Research Report            ║
║     Generated: {ts}        ║
╚══════════════════════════════════════════╝

Project: Agent Commerce Hub Ecosystem Analysis

Address Activity (last 7 days):
  ─ Total unique active addresses: 1,247
  ─ New addresses: 342
  ─ Returning addresses: 905

Token Flow Analysis:
  ─ Inflow:    0.05 SETH
  ─ Outflow:   0.03 SETH
  ─ Net Flow:  +0.02 SETH (accumulation)

Smart Contract Interactions:
  ─ ServiceRegistry: 12 calls
  ─ CAW Wallet:      8 transactions
  ─ Total unique contracts: 3

Key Findings:
  1. Growing agent-to-agent payment volume
  2. Service discovery via on-chain registry
  3. x402 payment pattern emerging

Recommendation: Monitor cross-agent payment patterns for
fee optimization opportunities.
""",
    }
    return analyses.get(service_id, "Analysis not available for this service ID.")


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

@x402_app.get("/services")
async def x402_list_services():
    """List services this agent sells."""
    return {
        "services": [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s["description"],
                "price": s["price_seth"],
                "token": s["token_id"],
                "chain": s["chain_id"],
                "price_usd": s["price_usd"],
            }
            for s in SELLER_SERVICES.values()
        ]
    }


@x402_app.post("/request")
async def x402_request(
    payload: ServiceRequest,
    tx_hash: Optional[str] = Query(None),
):
    """Request a paid service. Returns 402 if unpaid, 200 if paid.

    Query params:
        tx_hash: On-chain transaction hash proving payment (optional)
    """
    service = SELLER_SERVICES.get(payload.service_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found")

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
    analysis = _generate_analysis(payload.service_id)

    # Record revenue
    _revenue[service["id"]] = _revenue.get(service["id"], 0.0) + float(service["price_seth"])
    _revenue_log.append({
        "service_id": service["id"],
        "service_name": service["name"],
        "amount": float(service["price_seth"]),
        "tx_hash": tx_hash,
        "timestamp": time.time(),
    })

    return {
        "status": "delivered",
        "service": service["name"],
        "amount_paid": service["price_seth"],
        "tx_hash": tx_hash,
        "content": analysis,
    }


@x402_app.get("/revenue")
async def x402_revenue():
    """Show total revenue earned by this agent."""
    total = sum(_revenue.values())
    return {
        "total_seth": total,
        "total_usd": f"${total * 3000:.2f}",
        "tx_count": len(_revenue_log),
        "by_service": {
            str(sid): {
                "name": SELLER_SERVICES[sid]["name"],
                "earned_seth": amt,
            }
            for sid, amt in _revenue.items()
            if amt > 0
        },
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
        return {
            "healthy": status.get("healthy", False),
            "wallet_paired": status.get("wallet_paired", False),
            "wallet_status": status.get("wallet_status", ""),
            "seller_address": WALLET_SETH_ADDR,
            "balance_seth": seth_balance,
            "services_count": len(SELLER_SERVICES),
            "total_revenue_seth": sum(_revenue.values()),
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}


# ── Standalone entry ────────────────────────────────────────────

def serve(host: str = "0.0.0.0", port: int = 8888):
    """Start the x402 service server."""
    print(f"\n  🤖 Agent Commerce Hub — x402 Service Provider")
    print(f"  ─────────────────────────────────────────────")
    print(f"  Selling: {len(SELLER_SERVICES)} services")
    for s in SELLER_SERVICES.values():
        print(f"    [{s['id']}] {s['name']} — {s['price_seth']} SETH")
    print(f"  Wallet:  {WALLET_SETH_ADDR[:14]}...")
    print(f"  Listen:  http://{host}:{port}")
    print(f"  Endpoint: POST /request?tx_hash=0x...")
    print(f"  Revenue:  GET  /revenue")
    print()
    uvicorn.run(x402_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    serve()
