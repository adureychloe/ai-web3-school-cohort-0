"""Proof logger: generate receipt.json and proof.md outputs."""

import json
import os
import re
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
        guard_evidence: Optional[dict] = None,
        cobo_result: Optional[dict] = None,
    ) -> dict:
        """Generate a complete proof log entry.

        Args:
            user_intent: Natural language intent
            budget: Policy budget state
            quote: Service quote
            policy_decision: Policy check result
            human_confirmation: Human confirmation result (if any)
            payment_receipt: Payment receipt (simulated or real)
            delivery_result: Service delivery result
            guard_evidence: Guard check results (NEW)
            cobo_result: Cobo API result (NEW)

        Returns:
            Proof dictionary
        """
        proof = {
            "schema_version": "1.0",
            "project": "Secure Agent Commerce",
            "user_intent": user_intent,
            "budget": budget,
            "service_quote": quote,
            "policy_decision": policy_decision,
            "human_confirmation": human_confirmation,
            "payment_receipt": payment_receipt,
            "delivery_result": delivery_result,
            "guard_evidence": guard_evidence,
            "cobo_result": cobo_result,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sensitive_data_saved": True,
        }
        return proof

    def save_receipt(self, proof: dict, session_id: str) -> str:
        """Save machine-readable receipt JSON."""
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', str(session_id))
        path = os.path.join(self.output_dir, f"receipt-{safe_id}.json")
        with open(path, "w") as f:
            json.dump(proof, f, indent=2, ensure_ascii=False)
        return path

    def save_proof_md(self, proof: dict, session_id: str) -> str:
        """Save human-readable proof markdown."""
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', str(session_id))
        path = os.path.join(self.output_dir, f"proof-{safe_id}.md")
        lines = [
            f"# Secure Agent Commerce Proof — {session_id}",
            "",
            f"**时间**: {proof['timestamp']}",
            f"**用户意图**: {proof['user_intent']}",
            "",
        ]

        # Guard evidence section
        ge = proof.get("guard_evidence")
        if ge:
            lines += [
                "## Guard 检测结果",
                f"- 风险评分: {ge.get('risk_score', 'N/A')}",
                f"- 判定: {ge.get('verdict', 'N/A')}",
                "",
                "| 检测项 | 结果 |",
                "|--------|------|",
            ]
            for c in ge.get("checks", []):
                name = c.get("name", "unknown")
                result = "✅ PASS" if c.get("passed") else "🚫 BLOCKED"
                lines.append(f"| {name} | {result} |")
            lines.append("")

        # Budget section
        if proof.get("budget"):
            lines += [
                "## 预算",
                f"- Session 限额: {proof['budget'].get('session_limit', 'N/A')}",
                f"- Session 已用: {proof['budget'].get('session_spent', 'N/A')}",
                "",
            ]

        # Quote section
        if proof.get("service_quote"):
            q = proof["service_quote"]
            lines += [
                "## 服务报价",
                f"- 服务: {q.get('service_name', q.get('service_id', 'N/A'))}",
                f"- 金额: {q.get('amount', 'N/A')} {q.get('token', '')}",
                f"- 网络: {q.get('network', 'N/A')}",
                "",
            ]

        # Cobo result section
        cr = proof.get("cobo_result")
        if cr:
            lines += [
                "## Cobo 执行结果",
                f"- 模式: {cr.get('mode', 'N/A')}",
                f"- Pact ID: {cr.get('pact_id', 'N/A')}",
                f"- 交易 ID: {cr.get('transaction_id', 'N/A')}",
                f"- 状态: {cr.get('status', 'N/A')}",
                f"- Tx Hash: {cr.get('tx_hash', 'N/A')}",
                "",
            ]

        # Policy section
        if proof.get("policy_decision"):
            pd = proof["policy_decision"]
            lines += [
                "## 策略决策",
                f"- 允许: {pd.get('allowed', 'N/A')}",
                f"- 原因: {pd.get('reason', 'N/A')}",
            ]
            if pd.get("human_confirmation_required"):
                lines.append(f"- 需要人工确认: {pd['human_confirmation_required']}")
            lines.append("")

        # Human confirmation
        hc = proof.get("human_confirmation")
        if hc:
            lines += [
                "## 人工确认",
                f"- 确认结果: {hc.get('result', 'N/A')}",
                f"- 确认者: {hc.get('confirmed_by', 'N/A')}",
                "",
            ]

        # Payment receipt
        pr = proof.get("payment_receipt")
        if pr:
            lines += [
                "## 支付收据",
                f"- Receipt ID: {pr.get('receipt_id', pr.get('transaction_id', 'N/A'))}",
                f"- 金额: {pr.get('amount', 'N/A')} {pr.get('token_id', pr.get('token', ''))}",
                f"- 方式: {pr.get('mode', pr.get('payment_method', 'N/A'))}",
            ]
            if pr.get("tx_hash"):
                lines.append(f"- Tx Hash: {pr['tx_hash']}")
            lines.append("")

        # Delivery
        dr = proof.get("delivery_result")
        if dr:
            lines += [
                "## 交付结果",
                f"- 状态: {dr.get('status', 'N/A')}",
                f"- 摘要: {dr.get('summary', 'N/A')}",
                "",
            ]

        with open(path, "w") as f:
            f.write("\n".join(lines))
        return path
