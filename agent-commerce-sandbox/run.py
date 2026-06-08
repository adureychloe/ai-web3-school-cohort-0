#!/usr/bin/env python3
"""
Agent Commerce Hub — CLI Entry Point

Usage:
    python run.py discover              List all services from the on-chain registry
    python run.py pay <service_id>      Pay for a service (prompts for intent)
    python run.py pay <service_id> "..." Pay for a service with intent text
    python run.py proof [service_id]    Show delivery proofs (optionally by service)
    python run.py status                Show wallet and contract status
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_commerce_sandbox.engine import discover_services, pay_for_service, show_proofs
from agent_commerce_sandbox.caw_client import CawClient
from agent_commerce_sandbox.procurement_agent import procure

BANNER = """
╔══════════════════════════════════════════╗
║      Agent Commerce Hub v0.4            ║
║  On-chain Discovery × CAW Payment       ║
╚══════════════════════════════════════════╝
"""


def print_usage():
    print("Commands:")
    print("  discover              List services from Sepolia contract")
    print('  pay <id> ["intent"]   Pay for a service (intent optional)')
    print("  proof [id]            Show delivery proofs")
    print("  status                Show wallet + contract info")
    print('  procure ["request"]   Natural language service procurement')
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

    elif cmd == "status":
        cmd_status()

    else:
        print(f"  Unknown command: {cmd}")
        print()
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
