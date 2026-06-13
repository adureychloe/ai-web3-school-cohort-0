"""
x402 Client — Auto-pay HTTP 402 Payment Required via CAW.

Services are discovered from the on-chain ServiceRegistryV2 contract. The
client reads each service's endpointURI and sends the request there. When the
endpoint responds with 402, it:
  1. Parses the X-Payment-Info header for payment details
  2. Creates a CAW Pact (or reuses active pact)
  3. Executes a CAW Transfer
  4. Retries the request with the tx_hash as proof
  5. Returns the paid content

Usage:
  python3 -m agent_commerce_sandbox.x402_client request "ETH分析" --service-id 4 [--server http://...]
"""

import argparse
import json
import sys
import time
import os
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_commerce_sandbox.caw_client import CawClient, WALLET_SETH_ADDR
from agent_commerce_sandbox.chain_client_v2 import ChainClientV2

try:
    from web3 import Web3
except Exception:  # pragma: no cover
    Web3 = None


# ── Constants ───────────────────────────────────────────────────

DEFAULT_X402_SERVER = "http://127.0.0.1:8888"
STALE_DEMO_SERVICE_ID = 1
LAST_RESORT_DEMO_PUBLIC_X402_SERVER = "https://gradually-clicker-tacking.ngrok-free.dev/api/x402"


# ── Endpoint normalization ─────────────────────────────────────

def _clean_base_url(url: str) -> str:
    """Return a stable base URL without a trailing slash."""
    return (url or "").strip().rstrip("/")


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


def _configured_public_base_url() -> Optional[str]:
    """Return the configured public x402 base URL, if one is set.

    X402_SELF_URL is authoritative. X402_PUBLIC_URL is also accepted as an
    explicit public base. The demo fallback below is deliberately not included
    here so it can stay service-aware.
    """
    return (
        _clean_base_url(os.environ.get("X402_SELF_URL", ""))
        or _clean_base_url(os.environ.get("X402_PUBLIC_URL", ""))
        or None
    )


def _normalize_public_endpoint(endpoint_uri: str, service_id: int) -> str:
    """Return a buyer-usable endpoint for discovered services.

    For loopback endpointURI values, prefer configured X402_SELF_URL then
    X402_PUBLIC_URL. If neither env var is set, use the known current public
    demo base only as a last-resort compatibility fallback for stale demo
    service #1. Leave all other service ids untouched; explicit --server
    overrides are applied later by _resolve_request_url and still take
    precedence.
    """
    if not _endpoint_is_loopback(endpoint_uri):
        return endpoint_uri

    public_base_url = _configured_public_base_url()
    if public_base_url:
        return public_base_url
    if service_id == STALE_DEMO_SERVICE_ID:
        return LAST_RESORT_DEMO_PUBLIC_X402_SERVER
    return endpoint_uri


# ── x402 Client ────────────────────────────────────────────────

class X402Client:
    """Client that auto-handles HTTP 402 Payment Required via CAW.

    Args:
        server_url: Optional override. If given, requests are sent to this URL
                    instead of the service's on-chain endpointURI.
    """

    def __init__(self, server_url: Optional[str] = None):
        # server_override is used as the request target when explicitly set.
        self.server_override = server_url.rstrip("/") if server_url else None
        # server_url kept for compatibility (revenue endpoint, web UI).
        self.server_url = self.server_override or DEFAULT_X402_SERVER
        self.caw = CawClient()
        self.chain = ChainClientV2()
        self._active_pact_id: Optional[str] = None

    # ── Discovery ──────────────────────────────────────────

    def discover_from_chain(self, active_only: bool = True) -> list[dict]:
        """Discover services from the on-chain ServiceRegistryV2.

        Returns a list of normalized dicts with keys:
            id, name, description, price, token, chain, address,
            endpoint, protocol, price_usd, active
        """
        try:
            raw = self.chain.list_services(0, 200)
        except Exception as e:
            print(f"  ❌ Failed to read services from chain: {e}")
            return []

        services = []
        for s in raw:
            if active_only and not s["active"]:
                continue
            if Web3 is not None:
                price_seth = str(Web3.from_wei(s["priceWei"], "ether"))
            else:
                price_seth = str(s["priceWei"] / 1e18)
            services.append({
                "id": s["id"],
                "name": s["name"],
                "description": s["description"],
                "price": price_seth,
                "token": s["tokenId"] or "SETH",
                "chain": s["chainId"] or "SETH",
                "address": s["paymentAddress"],
                "endpoint": _normalize_public_endpoint(s["endpointURI"], s["id"]),
                "protocol": s["protocol"] or "x402",
                "price_usd": f"${float(price_seth) * 3000:.2f}",
                "active": s["active"],
            })
        return services

    def list_services(self) -> list[dict]:
        """List available services (discovered from chain)."""
        return self.discover_from_chain()

    def _resolve_request_url(self, service: dict) -> str:
        """Resolve the /request URL for a service.

        --server override (if set) takes precedence; otherwise the service's
        on-chain endpointURI is used. The /request path is appended if missing.
        """
        if self.server_override:
            base = self.server_override
        else:
            base = (service.get("endpoint") or "").strip() or DEFAULT_X402_SERVER

        base = base.rstrip("/")
        parsed = urlparse(base)
        path = parsed.path or ""
        if path.endswith("/request"):
            return base
        return base + "/request"

    # ── Payment ────────────────────────────────────────────

    def _get_or_create_pact(self, service: dict) -> Optional[str]:
        """Get an active pact or create one for this payment."""
        import json as _json

        amount = service["price"]
        token = service["token"]
        chain = service["chain"]
        name = service["name"].lower().replace(" ", "-")[:30]
        dst_addr = service.get("address", WALLET_SETH_ADDR)  # seller's address

        # Reuse an active pact within this client instance when it still exists.
        if self._active_pact_id:
            try:
                pact = self.caw.get_pact(self._active_pact_id)
                if pact.get("status") == "active":
                    print(f"  ✅ Reusing active Pact ({self._active_pact_id[:16]}...)")
                    return self._active_pact_id
            except Exception:
                self._active_pact_id = None

        policies = _json.dumps([{
            "name": f"x402-pay-{name}",
            "type": "transfer",
            "rules": {
                "effect": "allow",
                "when": {
                    "chain_in": [chain],
                    "token_in": [{"chain_id": chain, "token_id": token}],
                    "destination_address_in": [
                        {"chain_id": chain, "address": dst_addr}
                    ],
                },
                "deny_if": {"amount_usd_gt": "5.00"},
            },
        }])

        completion = _json.dumps([{"type": "tx_count", "threshold": "100"}])

        execution_plan = (
            f"# Summary\\n"
            f"Auto-pay for {service['name']} via x402\\n\\n"
            f"# Operations\\n"
            f"- Transfer {amount} {token} to {dst_addr} on {chain}\\n\\n"
            f"# Risk Controls\\n"
            f"- Single transfer, capped at {amount} {token}\\n"
            f"- Service: {service['description'][:80]}"
        )

        pact = self.caw.submit_pact(
            intent=f"x402 auto-pay: {amount} {token} for {service['name']}",
            policies_json=policies,
            completion_conditions=completion,
            name=f"x402-{name}",
            execution_plan=execution_plan,
        )
        pact_id = pact.get("pact_id", "unknown")
        pact_status = pact.get("status", "unknown")
        print(f"  ⏳ Pact submitted ({pact_id[:16]}...) status={pact_status}")

        if pact_status in ("pending_approval", "PENDING_APPROVAL"):
            print()
            print("  ╔══════════════════════════════════════════════════╗")
            print("  ║   📱 Open CAW App and APPROVE the pact          ║")
            print("  ╚══════════════════════════════════════════════════╝")
            print()
            print("  [3/4] Waiting for pact approval...")
            try:
                self.caw.wait_for_pact_active(pact_id, timeout=300)
                print(f"  ✅ Pact approved!")
                self._active_pact_id = pact_id
            except TimeoutError:
                print(f"  ❌ Pact approval timed out. Please approve in CAW App.")
                return None
        elif pact_status in ("active", "ACTIVE"):
            print(f"  ✅ Pact already active.")
            self._active_pact_id = pact_id
        else:
            print(f"  ⚠️  Unexpected status: {pact_status}")
            self._active_pact_id = pact_id

        return pact_id

    def request(self, service_id: int = 4, query: str = "") -> dict:
        """Make an x402 request with auto-pay on 402.

        Flow:
          1. Discover service from chain → resolve endpoint URL
          2. POST /request → get 402 with payment info
          3. Parse payment info → create Pact → execute Transfer
          4. Retry with tx_hash → get paid content
        """
        # Discover service from chain
        services = self.discover_from_chain()
        service = next((s for s in services if s["id"] == service_id), None)
        if not service:
            print(f"  ❌ Service {service_id} not found on-chain (or inactive).")
            return {"status": "failed", "error": "service not found"}

        request_url = self._resolve_request_url(service)

        print(f"\n  🤖 x402 Client — Agent Commerce Hub")
        print(f"  ─────────────────────────────────────")
        print(f"  Service: [{service['id']}] {service['name']}")
        print(f"  Price:   {service['price']} {service['token']} ({service.get('price_usd', '?')})")
        print(f"  Endpoint:{request_url}")
        if self.server_override:
            print(f"  (override via --server)")
        print()

        # Step 1: Initial request (expect 402)
        print("  [1/4] Requesting service (expecting 402)...")
        payload = json.dumps({"service_id": service_id, "query": query}).encode()
        try:
            req = Request(
                request_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urlopen(req, timeout=30)
            result = json.loads(resp.read())
            print(f"  ⚠️  Service returned content without payment (unexpected for x402)")
            return result
        except HTTPError as e:
            if e.code != 402:
                body = e.read().decode()
                print(f"  ❌ Unexpected HTTP {e.code}: {body[:200]}")
                return {"status": "failed", "error": body}
            body = json.loads(e.read())
            payment = body.get("payment", {})
            print(f"  ✅ Received 402 Payment Required")
            print(f"     Amount: {payment.get('amount')} {payment.get('token_id')}")
            print(f"     Pay to: {payment.get('address', '')[:14]}...")
            print()

        # Step 2: Create Pact and pay
        print("  [2/4] Creating CAW Pact for payment...")
        pact_id = self._get_or_create_pact(service)
        if not pact_id:
            return {"status": "payment_cancelled", "error": "pact not approved"}

        print()
        print("  [3/4] Executing CAW Transfer...")
        dst_addr = payment.get("address", service.get("address", ""))

        try:
            tx_result = self.caw.execute_transfer(
                pact_id=pact_id,
                dst_address=dst_addr,
                amount=payment.get("amount", service["price"]),
                token_id=payment.get("token_id", service["token"]),
                chain_id=payment.get("chain_id", service["chain"]),
                description=f"x402 auto-pay for {service['name']}: {query[:80] or 'no query'}",
            )
            tx_id = tx_result.get("id", "")
            print(f"  ✅ Transfer submitted (tx_id={tx_id[:16]}...)")

            tx_complete = self.caw.wait_for_transaction_complete(tx_id, timeout=180)
            tx_hash = tx_complete.get("transaction_hash", "")
            if not tx_hash:
                tx_hash = tx_id  # fallback: use request-id as proof
            print(f"     On-chain: {tx_hash[:50]}...")
        except Exception as e:
            print(f"  ❌ Transfer failed: {e}")
            return {"status": "failed", "error": str(e)}

        print()

        # Step 4: Retry with payment proof
        print("  [4/4] Retrying with payment proof...")
        try:
            retry_payload = json.dumps({"service_id": service_id, "query": query}).encode()
            req = Request(
                f"{request_url}?tx_hash={tx_hash}",
                data=retry_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urlopen(req, timeout=30)
            result = json.loads(resp.read())

            content = result.get("content", "")
            print("  ✅ Service delivered!")
            print()
            print(content)

            print("  ── Payment Summary ──")
            print(f"     Paid:    {payment.get('amount')} {payment.get('token_id')}")
            print(f"     Tx Hash: {tx_hash[:50]}...")
            print(f"     Pact ID: {pact_id[:16]}...")
            print(f"     To:      {dst_addr[:14]}...")
            print()

            return result

        except HTTPError as e:
            body = e.read().decode()
            print(f"  ❌ Payment verification failed (HTTP {e.code}): {body[:200]}")
            return {"status": "failed", "error": body}
        except Exception as e:
            print(f"  ❌ Failed to retrieve service: {e}")
            return {"status": "failed", "error": str(e)}

    def show_revenue(self) -> dict:
        """Show revenue earned by the x402 server."""
        try:
            resp = urlopen(f"{self.server_url}/revenue", timeout=15)
            return json.loads(resp.read())
        except Exception as e:
            print(f"  ❌ Failed to fetch revenue: {e}")
            return {}


# ── CLI entry ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="x402 Client — Auto-pay via CAW")
    parser.add_argument("action", choices=["request", "list", "revenue"],
                        help="Action to perform")
    parser.add_argument("query", nargs="?", default="",
                        help="Service request text (for 'request' action)")
    parser.add_argument("--server", default=None,
                        help="Override endpoint URL (default: use on-chain endpointURI)")
    parser.add_argument("--service-id", type=int, default=4,
                        help="Service ID to request (default: 4)")

    args = parser.parse_args()
    client = X402Client(server_url=args.server)

    if args.action == "list":
        services = client.list_services()
        if not services:
            print("  No active services found on-chain.")
            return
        print(f"\n  Services discovered on-chain ({client.chain.contract_addr}):")
        print("  " + "─" * 50)
        for s in services:
            print(f"  [{s['id']}] {s['name']}")
            print(f"       {s['description'][:60]}")
            print(f"       {s['price']} {s['token']} ({s.get('price_usd', '?')})")
            print(f"       endpoint: {s['endpoint'] or '(default)'}")
        print()

    elif args.action == "request":
        client.request(service_id=args.service_id, query=args.query or f"request service {args.service_id}")

    elif args.action == "revenue":
        rev = client.show_revenue()
        if rev:
            print(f"\n  📊 x402 Server Revenue")
            print(f"  ─────────────────────────")
            print(f"  Total:    {rev.get('total_seth', 0)} SETH ({rev.get('total_usd', '$0')})")
            print(f"  Tx Count: {rev.get('tx_count', 0)}")
            for sid, data in rev.get("by_service", {}).items():
                print(f"  [{sid}] {data['name']}: {data['earned_seth']} SETH")
            print()


if __name__ == "__main__":
    main()
