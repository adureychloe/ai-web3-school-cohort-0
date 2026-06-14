#!/usr/bin/env python3
"""
Agent Commerce Hub — CLI Entry Point

Usage:
    python run.py discover              List all services from the on-chain registry
    python run.py pay <service_id>      Pay for a service (prompts for intent)
    python run.py pay <service_id> "..." Pay for a service with intent text
    python run.py proof [service_id]    Show delivery proofs (optionally by service)
    python run.py buyer-agent "request" [budget_seth]
                                      Match services via local Buyer Agent API
    python run.py status                Show wallet and contract status
    python run.py serve [port]          Start x402 service (sell services)
    python run.py request [id] ["q"]    Buy via x402 (auto-pay with CAW)
    python run.py revenue               Show x402 server earnings
    python run.py list-services         List x402 services for sale
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_commerce_sandbox.engine import discover_services, pay_for_service, show_proofs
from agent_commerce_sandbox.caw_client import CawClient
from agent_commerce_sandbox.procurement_agent import procure

BANNER = """
╔══════════════════════════════════════════╗
║      Agent Commerce Hub v0.5            ║
║  On-chain Discovery × CAW Payment       ║
║  x402 Seller & Buyer                    ║
╚══════════════════════════════════════════╝
"""


def print_usage():
    print("Commands:")
    print("  discover              List services from Sepolia contract")
    print('  pay <id> ["intent"]   Pay for a service (intent optional)')
    print("  proof [id]            Show delivery proofs")
    print("  status                Show wallet + contract info")
    print('  procure ["request"]   Natural language service procurement')
    print('  buyer-agent "request" [budget_seth]  Match via local Buyer Agent API')
    print("  serve                 Start x402 service (sell services)")
    print('  request <id> ["q"]    Buy via x402 (auto-pay with CAW)')
    print("  revenue               Show x402 server earnings")
    print("  list-services         List x402 services for sale")
    print()


def cmd_discover():
    services = discover_services()
    if services:
        print(f"  Tip: python run.py pay <service_id> to pay for a service")
    print()


def cmd_pay(service_id: int, intent: str = ""):
    if not intent:
        print(f"  Enter your request (or press Enter for default):")
        try:
            intent = input(f"  > ").strip()
        except (EOFError, KeyboardInterrupt):
            intent = ""
    if not intent:
        intent = f"Purchase service #{service_id}"

    result = pay_for_service(service_id, intent)
    if result["status"] == "failed":
        print(f"\n  ❌ Payment flow failed: {result.get('error', 'unknown error')}")
        sys.exit(1)
    elif result["status"] == "pending_approval":
        print(f"\n  ⏳ Pact submitted, waiting for approval in CAW App...")
        print(f"     Run again after approving: python run.py pay {service_id}")
        sys.exit(0)


def cmd_proof(service_id: int = 0):
    show_proofs(service_id)


def cmd_status():
    from agent_commerce_sandbox.chain_client import ChainClient
    import json

    # Chain status
    try:
        chain = ChainClient()
        count = chain.get_service_count()
        active = len(chain.list_services())
        proof_count = chain.get_proof_count()
        print(f"\n  ServiceRegistry (Sepolia):")
        print(f"    Contract: {chain.contract_addr}")
        print(f"    Services: {active} active / {count} total")
        print(f"    Proofs:   {proof_count}")
    except Exception as e:
        print(f"  ❌ Chain: {e}")

    # CAW status
    try:
        caw = CawClient()
        from agent_commerce_sandbox.caw_client import _run_caw as caw_run
        result = caw_run("status")
        print(f"\n  CAW Wallet:")
        print(f"    Healthy: {result.get('healthy')}")
        print(f"    Paired:  {result.get('wallet_paired')}")
        print(f"    Status:  {result.get('wallet_status')}")
        from agent_commerce_sandbox.caw_client import WALLET_SETH_ADDR
        print(f"    SETH Address: {WALLET_SETH_ADDR}")
    except Exception as e:
        print(f"  ❌ CAW: {e}")

    print()


def cmd_procure(request_text: str = ""):
    if not request_text:
        try:
            request_text = input("  What do you need? > ").strip()
        except (EOFError, KeyboardInterrupt):
            request_text = ""
    if not request_text:
        print("  Cancelled.")
        return
    procure(request_text)


def cmd_buyer_agent(request_text: str = "", budget_seth: str = ""):
    if not request_text:
        try:
            request_text = input("  What do you need? > ").strip()
        except (EOFError, KeyboardInterrupt):
            request_text = ""
    if not request_text:
        print("  Cancelled.")
        return

    import json
    import urllib.error
    import urllib.request

    url = os.environ.get("AGENT_COMMERCE_API", "http://127.0.0.1:8080")
    payload = {"request": request_text, "auto_pay": False}
    if budget_seth:
        payload["budget_seth"] = budget_seth

    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/agent/buyer/procure",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        body = json.loads(resp.read())
    except urllib.error.URLError as exc:
        print("  Buyer Agent API is not reachable.")
        print("  Start it with: python3 -m uvicorn web.app:app --host 0.0.0.0 --port 8080")
        print(f"  Error: {exc}")
        return

    decision = body.get("decision", {})
    print(f"  Status: {body.get('status')}")
    print(f"  Selected: [{decision.get('service_id')}] {decision.get('service_name')}")
    print(f"  Score: {decision.get('score')}  Source: {body.get('match_source')}")


def main():
    print(BANNER)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        print_usage()
        return

    cmd = args[0]

    if cmd == "discover":
        cmd_discover()

    elif cmd == "pay":
        if len(args) < 2:
            print("  Usage: python run.py pay <service_id> [\"intent\"]")
            print()
            return
        try:
            service_id = int(args[1])
        except ValueError:
            print(f"  ❌ Invalid service_id: {args[1]}")
            sys.exit(1)
        intent = args[2] if len(args) >= 3 else ""
        cmd_pay(service_id, intent)

    elif cmd == "proof":
        service_id = int(args[1]) if len(args) >= 2 else 0
        cmd_proof(service_id)

    elif cmd == "procure":
        request = args[1] if len(args) >= 2 else ""
        cmd_procure(request)

    elif cmd == "buyer-agent":
        request = args[1] if len(args) >= 2 else ""
        budget_seth = args[2] if len(args) >= 3 else ""
        cmd_buyer_agent(request, budget_seth)

    elif cmd == "serve":
        from agent_commerce_sandbox.x402_server import serve as x402_serve
        port = int(args[1]) if len(args) >= 2 else 8888
        x402_serve(port=port)

    elif cmd == "request":
        from agent_commerce_sandbox.x402_client import X402Client
        service_id = int(args[1]) if len(args) >= 2 else 4
        query = args[2] if len(args) >= 3 else ""
        server = os.environ.get("X402_SERVER")
        client = X402Client(server_url=server) if server else X402Client()
        print(f"\n  🤖 Starting x402 auto-pay in background...")
        print(f"  Service: [{service_id}] — will auto-pay via CAW")
        print(f"\n  📱 Open CAW App when prompted to approve the pact")
        print(f"  ⏳ You'll be notified when complete!\n")
        client.request(service_id=service_id, query=query)

    elif cmd == "revenue":
        from agent_commerce_sandbox.x402_client import X402Client
        server = os.environ.get("X402_SERVER")
        client = X402Client(server_url=server) if server else X402Client()
        rev = client.show_revenue()
        if rev:
            print(f"\n  📊 x402 Server Revenue")
            print(f"  ─────────────────────────")
            print(f"  Total:    {rev.get('total_seth', 0)} SETH ({rev.get('total_usd', '$0')})")
            print(f"  Tx Count: {rev.get('tx_count', 0)}")
            for sid, data in rev.get("by_service", {}).items():
                print(f"  [{sid}] {data['name']}: {data['earned_seth']} SETH")
            print()

    elif cmd == "list-services":
        from agent_commerce_sandbox.x402_client import X402Client
        server = os.environ.get("X402_SERVER")
        client = X402Client(server_url=server) if server else X402Client()
        services = client.list_services()
        if not services:
            print("  No services available.")
        else:
            print(f"\n  x402 Services for sale:")
            print("  " + "─" * 50)
            for s in services:
                print(f"  [{s['id']}] {s['name']}")
                print(f"       {s['description'][:60]}")
                print(f"       {s['price']} {s['token']} ({s.get('price_usd', '?')})")
            print()

    elif cmd == "status":
        cmd_status()

    else:
        print(f"  Unknown command: {cmd}")
        print()
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
