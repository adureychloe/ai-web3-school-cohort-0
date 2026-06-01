"""Proof logger: generate receipt.json and proof.md outputs."""

import json
import os
import time
from typing import Optional


class ProofLogger:
    """Generates structured proof of work outputs."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def log_session(
        self,
        user_intent: str,
        budget: dict,
        quote: dict,
        policy_decision: dict,
        human_confirmation: Optional[dict],
        payment_receipt: Optional[dict],
        delivery_result: Optional[dict],
    ) -> dict:
        """Generate a complete proof log entry."""
        proof = {
            "project": "Agent Commerce Sandbox",
            "user_intent": user_intent,
            "budget": budget,
            "service_quote": quote,
            "policy_decision": policy_decision,
            "human_confirmation": human_confirmation,
            "payment_receipt": payment_receipt,
            "delivery_result": delivery_result,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sensitive_data_saved": False,
        }
        return proof

    def save_receipt(self, proof: dict, session_id: str) -> str:
        """Save machine-readable receipt JSON."""
        path = os.path.join(self.output_dir, f"receipt-{session_id}.json")
        with open(path, "w") as f:
            json.dump(proof, f, indent=2, ensure_ascii=False)
        return path

    def save_proof_md(self, proof: dict, session_id: str) -> str:
        """Save human-readable proof markdown."""
        path = os.path.join(self.output_dir, f"proof-{session_id}.md")
        lines = [
            f"# Agent Commerce Proof — {session_id}",
            "",
            f"**时间**: {proof['timestamp']}",
            f"**用户意图**: {proof['user_intent']}",
            "",
            "## 预算",
            f"- Session 限额: {proof['budget']['session_limit']} {proof['budget']['session_limit_token']}",
            f"- Session 已用: {proof['budget']['session_spent']}",
            "",
            "## 服务报价",
            f"- 服务: {proof['service_quote'].get('service_name', proof['service_quote']['service_id'])}",
            f"- 金额: {proof['service_quote']['amount']} {proof['service_quote']['token']}",
            f"- 网络: {proof['service_quote']['network']}",
            "",
            "## 策略决策",
            f"- 允许: {proof['policy_decision']['allowed']}",
            f"- 原因: {proof['policy_decision']['reason']}",
            f"- 需要人工确认: {proof['policy_decision']['human_confirmation_required']}",
        ]

        if proof.get("human_confirmation"):
            lines += [
                "",
                "## 人工确认",
                f"- 确认结果: {proof['human_confirmation'].get('result', 'N/A')}",
                f"- 确认者: {proof['human_confirmation'].get('confirmed_by', 'N/A')}",
            ]

        if proof.get("payment_receipt"):
            lines += [
                "",
                "## 支付收据",
                f"- Receipt ID: {proof['payment_receipt']['receipt_id']}",
                f"- 金额: {proof['payment_receipt']['amount']} {proof['payment_receipt']['token']}",
                f"- 方式: {proof['payment_receipt']['payment_method']}",
            ]

        if proof.get("delivery_result"):
            lines += [
                "",
                "## 交付结果",
                f"- 状态: {proof['delivery_result'].get('status', 'N/A')}",
                f"- 摘要: {proof['delivery_result'].get('summary', 'N/A')}",
            ]

        with open(path, "w") as f:
            f.write("\n".join(lines))
        return path
