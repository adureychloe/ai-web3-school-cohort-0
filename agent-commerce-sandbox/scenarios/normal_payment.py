#!/usr/bin/env python3
"""
Normal payment scenario: allowlisted service, within budget → auto-approved.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_commerce_sandbox.engine import run_flow
from agent_commerce_sandbox.proof_logger import ProofLogger


def run():
    proof = run_flow(
        user_intent="研究 x402 和 agent wallet 是否适合作为 Hackathon 方向",
        service_id="research-agent-01",
        scenario="normal",
    )

    # Save outputs
    logger = ProofLogger()
    receipt_path = logger.save_receipt(proof, "normal-payment")
    proof_path = logger.save_proof_md(proof, "normal-payment")

    print(f"Scenario: NORMAL PAYMENT")
    print(f"  Result: {'APPROVED' if proof['policy_decision']['allowed'] else 'DENIED'}")
    print(f"  Auto-approve: {not proof['policy_decision']['human_confirmation_required']}")
    print(f"  Payment ID: {proof['payment_receipt']['receipt_id']}")
    print(f"  Receipt saved: {receipt_path}")
    print(f"  Proof saved: {proof_path}")
    return proof


if __name__ == "__main__":
    run()
