#!/usr/bin/env python3
"""
Over-budget scenario: service cost exceeds session limit → policy blocks.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_commerce_sandbox.engine import run_flow
from agent_commerce_sandbox.proof_logger import ProofLogger


def run():
    proof = run_flow(
        user_intent="做一次深度智能合约安全审计",
        service_id="smart-contract-auditor-05",
        scenario="over_budget",
    )

    logger = ProofLogger()
    receipt_path = logger.save_receipt(proof, "over-budget")
    proof_path = logger.save_proof_md(proof, "over-budget")

    print(f"Scenario: OVER BUDGET")
    print(f"  Result: {'APPROVED' if proof['policy_decision']['allowed'] else 'DENIED'}")
    print(f"  Reason: {proof['policy_decision']['reason']}")
    print(f"  Receipt saved: {receipt_path}")
    print(f"  Proof saved: {proof_path}")
    return proof


if __name__ == "__main__":
    run()
