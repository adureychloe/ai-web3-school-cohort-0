#!/usr/bin/env python3
"""
Unknown service scenario: service not in allowlist → human confirmation triggered.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_commerce_sandbox.engine import run_flow
from agent_commerce_sandbox.proof_logger import ProofLogger


def run():
    proof = run_flow(
        user_intent="获取 Premium 级别的跨链市场分析",
        service_id="premium-analyzer-04",
        scenario="unknown_service",
    )

    logger = ProofLogger()
    receipt_path = logger.save_receipt(proof, "unknown-service")
    proof_path = logger.save_proof_md(proof, "unknown-service")

    print(f"Scenario: UNKNOWN SERVICE")
    print(f"  Policy Decision: {'ALLOWED' if proof['policy_decision']['allowed'] else 'DENIED'}")
    print(f"  Reason: {proof['policy_decision']['reason']}")
    print(f"  Human Confirmation: {proof.get('human_confirmation', {}).get('result', 'N/A')}")
    print(f"  Payment ID: {proof.get('payment_receipt', {}).get('receipt_id', 'N/A')}")
    print(f"  Receipt saved: {receipt_path}")
    print(f"  Proof saved: {proof_path}")
    return proof


if __name__ == "__main__":
    run()
