#!/usr/bin/env python3
"""
Agent Commerce Sandbox — CLI Entry Point

Usage:
    python run.py                     # Run normal payment scenario
    python run.py normal              # Run normal payment scenario
    python run.py over_budget         # Run over-budget scenario
    python run.py unknown_service     # Run unknown service scenario
    python run.py all                 # Run all scenarios
"""

import json
import sys
import os

# Ensure the package is importable from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_commerce_sandbox.engine import run_flow
from agent_commerce_sandbox.mock_services import discover_services, get_service, format_quote
from agent_commerce_sandbox.policy_checker import load_policy, check_policy
from agent_commerce_sandbox.payment_simulator import simulate_payment
from agent_commerce_sandbox.proof_logger import ProofLogger

BANNER = """
╔══════════════════════════════════════════╗
║       Agent Commerce Sandbox v0.1        ║
║  Simulate x402 + Policy + Receipt Flow   ║
╚══════════════════════════════════════════╝
"""


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def run_normal_scenario():
    """Scenario 1: Normal payment — allowlisted service, within budget."""
    print_header("Scenario 1: Normal Payment (Allowlisted, Within Budget)")
    print("Intent: '帮我研究 x402 和 agent wallet 是否适合作为 Hackathon 方向'")
    print("Service: research-agent-01 (Research Notes Generator) — 0.25 USDC")
    print()

    proof = run_flow(
        user_intent="研究 x402 和 agent wallet 是否适合作为 Hackathon 方向",
        service_id="research-agent-01",
        scenario="normal",
    )

    print(f"  Policy Decision: {'ALLOWED' if proof['policy_decision']['allowed'] else 'DENIED'}")
    print(f"  Reason: {proof['policy_decision']['reason']}")
    print(f"  Payment: {proof['payment_receipt']['receipt_id']}")
    print(f"  Delivery: {proof['delivery_result']['status']}")
    print()
    return proof


def run_over_budget_scenario():
    """Scenario 2: Over budget — service exceeds session limit."""
    print_header("Scenario 2: Over Budget (Exceeds Session Limit)")
    print("Intent: '帮我做一次深度智能合约安全审计'")
    print("Service: smart-contract-auditor-05 (Smart Contract Auditor) — 5.00 USDC")
    print("Session limit: 5.00 USDC, session already has some spending from scenario 1")
    print()

    proof = run_flow(
        user_intent="做一次深度智能合约安全审计",
        service_id="smart-contract-auditor-05",
        scenario="over_budget",
    )

    print(f"  Policy Decision: {'ALLOWED' if proof['policy_decision']['allowed'] else 'DENIED'}")
    print(f"  Reason: {proof['policy_decision']['reason']}")
    if "payment_receipt" not in proof or proof["payment_receipt"] is None:
        print(f"  Result: Transaction blocked by policy")
    return proof


def run_unknown_service_scenario():
    """Scenario 3: Unknown service — not in allowlist, triggers human confirmation."""
    print_header("Scenario 3: Unknown Service (Triggers Human Confirmation)")
    print("Intent: '帮我获取 Premium 级别的跨链市场分析'")
    print("Service: premium-analyzer-04 (Premium Market Analyzer) — 3.00 USDC")
    print("Not in allowlist — needs human confirmation")
    print()

    proof = run_flow(
        user_intent="获取 Premium 级别的跨链市场分析",
        service_id="premium-analyzer-04",
        scenario="unknown_service",
    )

    print(f"  Policy Decision: {'ALLOWED' if proof['policy_decision']['allowed'] else 'DENIED'}")
    print(f"  Reason: {proof['policy_decision']['reason']}")
    hc = proof.get("human_confirmation")
    print(f"  Human Confirmation: {hc['result'] if hc else 'N/A'}")
    if proof.get("payment_receipt"):
        print(f"  Payment: {proof['payment_receipt']['receipt_id']}")
    print()


def run_dry_check(service_id: str, amount: float):
    """Just show what policy would decide without running the full flow."""
    service = get_service(service_id)
    if not service:
        print(f"  Service '{service_id}' not found.")
        return
    quote = format_quote(service)
    print(f"\n  Service: {service['name']}")
    print(f"  Amount: {quote['amount']} {quote['token']} on {quote['network']}")
    print(f"  Allowlisted: {service['allowlisted']}")
    decision = check_policy(service_id, amount, quote["token"], quote["network"])
    print(f"  Policy Check: {'PASS' if decision.allowed else 'BLOCKED'}")
    if decision.human_confirmation_required:
        print(f"  Human Confirmation: REQUIRED ({', '.join(decision.confirmation_reasons)})")
    print(f"  Reason: {decision.reason}")


def main():
    print(BANNER)

    args = sys.argv[1:] if len(sys.argv) > 1 else ["normal"]

    if "all" in args:
        run_normal_scenario()
        run_over_budget_scenario()
        run_unknown_service_scenario()
    elif "normal" in args:
        run_normal_scenario()
    elif "over_budget" in args:
        run_over_budget_scenario()
    elif "unknown_service" in args:
        run_unknown_service_scenario()
    elif "check" in args:
        print("Policy Dry-Run: Check what policy would decide for each service\n")
        for sid in ["research-agent-01", "data-fetcher-02", "model-inference-03",
                     "premium-analyzer-04", "smart-contract-auditor-05"]:
            s = get_service(sid)
            if s:
                run_dry_check(sid, float(s["price"]["amount"]))
    elif "list" in args:
        print("Available Services:\n")
        for s in discover_services():
            print(f"  [{s['id']}] {s['name']} — {s['price']['amount']} {s['price']['token']}")
            print(f"        {s['description'][:60]}...")
            print()
    else:
        print(f"Unknown scenario: {args[0]}")
        print("Usage: python run.py [normal|over_budget|unknown_service|all|check|list]")
        sys.exit(1)


if __name__ == "__main__":
    main()
