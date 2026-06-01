#!/usr/bin/env python3
"""
Agent Commerce Sandbox — CLI Entry Point

Usage:
    python run.py                          # Normal payment (simulation)
    python run.py normal                   # Normal payment (simulation)
    python run.py over_budget              # Over-budget scenario
    python run.py unknown_service          # Unknown service scenario
    python run.py all                      # Run all scenarios (simulation)
    python run.py --real normal            # Run with real testnet payment
    python run.py balance                  # Check testnet balance (if configured)
    python run.py check                    # Dry-run policy checks
    python run.py list                     # List available services
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_commerce_sandbox.engine import run_flow
from agent_commerce_sandbox.mock_services import discover_services, get_service, format_quote
from agent_commerce_sandbox.policy_checker import load_policy, check_policy
from agent_commerce_sandbox.proof_logger import ProofLogger
from agent_commerce_sandbox import chain as chain_module

BANNER = """
╔══════════════════════════════════════════╗
║       Agent Commerce Sandbox v0.2        ║
║  Real testnet payments via web3.py       ║
╚══════════════════════════════════════════╝
"""


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def run_normal_scenario(real_mode: bool = False):
    """Scenario 1: Normal payment — allowlisted service, within budget."""
    print_header("Scenario 1: Normal Payment (Allowlisted, Within Budget)")
    mode_label = "REAL (testnet)" if real_mode else "SIMULATION"
    print(f"  Mode: {mode_label}")
    print("Intent: '帮我研究 x402 和 agent wallet 是否适合作为 Hackathon 方向'")
    print("Service: research-agent-01 (Research Notes Generator) — 0.25 ETH" if real_mode else "Service: research-agent-01 (Research Notes Generator) — 0.25 USDC")
    print()

    proof = run_flow(
        user_intent="研究 x402 和 agent wallet 是否适合作为 Hackathon 方向",
        service_id="research-agent-01",
        scenario="normal",
        real_mode=real_mode,
    )

    if "error" in proof:
        print(f"  ERROR: {proof['error']}")
        return proof

    pd = proof["policy_decision"]
    print(f"  Policy Decision: {'ALLOWED' if pd['allowed'] else 'DENIED'}")
    print(f"  Reason: {pd['reason']}")

    pr = proof.get("payment_receipt")
    if pr:
        print(f"  Payment: {pr['receipt_id']}")
        print(f"  Mode: {pr.get('mode', 'simulation')}")
        if pr.get("mode") == "real":
            print(f"  Tx Hash: {pr.get('tx_hash', 'N/A')}")
            print(f"  Block: {pr.get('block_number', 'N/A')}")

    dr = proof.get("delivery_result", {})
    print(f"  Delivery: {dr.get('status', 'N/A')}")
    print()
    return proof


def run_over_budget_scenario(real_mode: bool = False):
    """Scenario 2: Over budget — service exceeds session limit."""
    print_header("Scenario 2: Over Budget (Exceeds Session Limit)")
    mode_label = "REAL (testnet)" if real_mode else "SIMULATION"
    print(f"  Mode: {mode_label}")
    print("Intent: '帮我做一次深度智能合约安全审计'")
    print("Service: smart-contract-auditor-05 (Smart Contract Auditor) — 5.00 ETH" if real_mode else "Service: smart-contract-auditor-05 (Smart Contract Auditor) — 5.00 USDC")
    print()

    proof = run_flow(
        user_intent="做一次深度智能合约安全审计",
        service_id="smart-contract-auditor-05",
        scenario="over_budget",
        real_mode=real_mode,
    )

    if "error" in proof:
        print(f"  ERROR: {proof['error']}")
        return proof

    pd = proof["policy_decision"]
    print(f"  Policy Decision: {'ALLOWED' if pd['allowed'] else 'DENIED'}")
    print(f"  Reason: {pd['reason']}")
    if "payment_receipt" not in proof or proof["payment_receipt"] is None:
        print(f"  Result: Transaction blocked by policy")
    return proof


def run_unknown_service_scenario(real_mode: bool = False):
    """Scenario 3: Unknown service — not in allowlist, triggers human confirmation."""
    print_header("Scenario 3: Unknown Service (Triggers Human Confirmation)")
    mode_label = "REAL (testnet)" if real_mode else "SIMULATION"
    print(f"  Mode: {mode_label}")
    print("Intent: '帮我获取 Premium 级别的跨链市场分析'")
    print("Service: premium-analyzer-04 (Premium Market Analyzer) — 3.00 ETH" if real_mode else "Service: premium-analyzer-04 (Premium Market Analyzer) — 3.00 USDC")
    print()

    proof = run_flow(
        user_intent="获取 Premium 级别的跨链市场分析",
        service_id="premium-analyzer-04",
        scenario="unknown_service",
        real_mode=real_mode,
    )

    if "error" in proof:
        print(f"  ERROR: {proof['error']}")
        return proof

    pd = proof["policy_decision"]
    print(f"  Policy Decision: {'ALLOWED' if pd['allowed'] else 'DENIED'}")
    print(f"  Reason: {pd['reason']}")
    hc = proof.get("human_confirmation")
    print(f"  Human Confirmation: {hc['result'] if hc else 'N/A'}")
    pr = proof.get("payment_receipt")
    if pr:
        print(f"  Payment: {pr['receipt_id']} ({pr.get('mode', 'simulation')})")
    print()


def run_balance():
    """Check testnet balance."""
    print_header("Testnet Balance Check")
    config = chain_module.load_config_from_env()
    if not config.is_real:
        print("  No .env configured. Copy .env.example to .env and set:")
        print("    RPC_URL=https://sepolia.base.org")
        print("    TEST_PRIVATE_KEY=<your testnet private key>")
        print()
        return

    w3 = chain_module.get_web3(config)
    if w3 is None:
        print("  Cannot connect to RPC. Check RPC_URL.")
        return

    acct = w3.eth.account.from_key(config.private_key)
    bal_wei = w3.eth.get_balance(acct.address)
    bal_eth = w3.from_wei(bal_wei, "ether")
    print(f"  Network:  Base Sepolia (chain_id={config.chain_id})")
    print(f"  Address:  {acct.address}")
    print(f"  Balance:  {bal_eth} ETH")
    print(f"  RPC:      {config.rpc_url}")
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

    # Parse --real flag
    args = [a for a in sys.argv[1:] if not a.startswith("--real")]
    real_mode = "--real" in sys.argv[1:]

    if real_mode:
        config = chain_module.load_config_from_env()
        if not config.is_real:
            print("  WARNING: --real flag set but no .env configured.")
            print("  Simulation mode will be used as fallback.")
            print("  Copy .env.example to .env to enable real testnet payments.\n")

    if not args:
        args = ["normal"]

    cmd = args[0]

    if cmd == "all":
        run_normal_scenario(real_mode)
        run_over_budget_scenario(real_mode)
        run_unknown_service_scenario(real_mode)
    elif cmd == "normal":
        run_normal_scenario(real_mode)
    elif cmd == "over_budget":
        run_over_budget_scenario(real_mode)
    elif cmd == "unknown_service":
        run_unknown_service_scenario(real_mode)
    elif cmd == "balance":
        run_balance()
    elif cmd == "check":
        print("Policy Dry-Run: Check what policy would decide for each service\n")
        for sid in ["research-agent-01", "data-fetcher-02", "model-inference-03",
                     "premium-analyzer-04", "smart-contract-auditor-05"]:
            s = get_service(sid)
            if s:
                run_dry_check(sid, float(s["price"]["amount"]))
    elif cmd == "list":
        print("Available Services:\n")
        for s in discover_services():
            print(f"  [{s['id']}] {s['name']} — {s['price']['amount']} {s['price']['token']}")
            print(f"        {s['description'][:60]}...")
            print()
    else:
        print(f"Unknown: {cmd}")
        print("Usage: python run.py [normal|over_budget|unknown_service|all|check|list|balance] [--real]")
        sys.exit(1)


if __name__ == "__main__":
    main()
