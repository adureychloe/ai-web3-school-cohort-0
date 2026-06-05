"""
Attack report generator.

Receives a GuardResult (when guard blocks) and produces:
- JSON report (machine-readable) → output/attack-report-{session_id}.json
- Markdown report (human-readable) → output/attack-report-{session_id}.md
"""

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Optional


OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


@dataclass
class AttackReport:
    report_id: str
    timestamp: str
    attack_type: str          # "context_injection" | "price_tampering"
    severity: str             # "CRITICAL" | "HIGH" | "MEDIUM"
    guard_checks: list
    risk_score: float
    blocking_reasons: list
    request_snapshot: dict    # what triggered the attack
    blocked_by: str           # "guard"
    mitigation: str           # description of what was prevented
    session_id: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema_version"] = "1.0"
        return d


def generate_attack_report(
    guard_result,
    user_intent: str,
    service_id: str,
    quote_amount: str,
    session_id: str = "",
) -> AttackReport:
    """Generate an attack report from a GuardResult.

    Args:
        guard_result: GuardResult object (from guard_detector)
        user_intent: The user's original request
        service_id: The service being requested
        quote_amount: The quoted payment amount
        session_id: Optional session identifier

    Returns:
        AttackReport with full details
    """
    # Determine attack type from blocking reasons
    attack_type = "unknown"
    severity = "HIGH"

    for reason in guard_result.blocking_reasons:
        if "context_injection" in reason:
            attack_type = "context_injection"
        elif "price_tampering" in reason:
            attack_type = "price_tampering"
            severity = "CRITICAL"
        elif "intent_consistency" in reason:
            attack_type = "intent_mismatch"
            severity = "MEDIUM"

    severity = guard_result._get_severity() if hasattr(guard_result, '_get_severity') else severity

    return AttackReport(
        report_id=f"report_{uuid.uuid4().hex[:12]}",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        attack_type=attack_type,
        severity=severity,
        guard_checks=[c.to_dict() if hasattr(c, 'to_dict') else c
                      for c in guard_result.checks],
        risk_score=guard_result.risk_score,
        blocking_reasons=guard_result.blocking_reasons,
        request_snapshot={
            "user_intent": user_intent,
            "service_id": service_id,
            "quote_amount": quote_amount,
        },
        blocked_by="guard",
        mitigation=_get_mitigation(attack_type),
        session_id=session_id,
    )


def save_attack_report(report: AttackReport) -> dict:
    """Save report to output/ as JSON and Markdown.

    Returns:
        dict with paths: {"json_path": "...", "md_path": "..."}
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base = f"attack-report-{re.sub(r'[^a-zA-Z0-9_-]', '_', str(report.session_id or report.report_id))}"

    # JSON
    json_path = os.path.join(OUTPUT_DIR, f"{base}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    # Markdown
    md_path = os.path.join(OUTPUT_DIR, f"{base}.md")
    md_content = _format_markdown(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {"json_path": json_path, "md_path": md_path}


def _get_mitigation(attack_type: str) -> str:
    mitigations = {
        "context_injection": (
            "Guard detected prompt injection patterns in the user's request "
            "and blocked the Pact submission before it reached Cobo. "
            "This prevents the agent from being tricked into unauthorized payments."
        ),
        "price_tampering": (
            "Guard detected that the service pricing configuration was tampered "
            "with at runtime. The Pact was not submitted to Cobo. "
            "Recommended: verify services.json integrity and check for unauthorized access."
        ),
        "intent_mismatch": (
            "Guard detected that the selected service does not match the user's "
            "stated intent. This may indicate a misconfigured agent or an attempt "
            "to purchase a different service than intended."
        ),
    }
    return mitigations.get(attack_type, "Attack blocked by Guard layer before reaching Cobo.")


def _format_markdown(report: AttackReport) -> str:
    """Generate human-readable attack report in Markdown."""
    lines = [
        "# 🚨 攻击分析报告",
        "",
        f"**报告 ID**: {report.report_id}",
        f"**检测时间**: {report.timestamp}",
        f"**攻击类型**: {report.attack_type}",
        f"**严重等级**: {report.severity}",
        f"**检测层**: Guard (本地语义检测)",
        f"**风险评分**: {report.risk_score:.2f} / 1.0",
        "",
        "---",
        "",
        "## 检测详情",
        "",
        "| 检测项 | 结果 | 详情 |",
        "|--------|------|------|",
    ]

    for c in report.guard_checks:
        name = c.get("name", "unknown")
        passed = c.get("passed", True)
        detail = c.get("detail", "")
        result_icon = "✅ 通过" if passed else "🚫 拦截"
        lines.append(f"| {name} | {result_icon} | {detail} |")

    lines += [
        "",
        "---",
        "",
        "## 阻断原因",
        "",
    ]
    for reason in report.blocking_reasons:
        lines.append(f"- {reason}")

    lines += [
        "",
        "## 请求上下文",
        "",
        f"**用户意图**: {report.request_snapshot.get('user_intent', 'N/A')}",
        f"**目标服务**: {report.request_snapshot.get('service_id', 'N/A')}",
        f"**报价金额**: {report.request_snapshot.get('quote_amount', 'N/A')}",
        "",
        "## 防护措施",
        "",
        report.mitigation,
        "",
        "---",
        "",
        "*此报告由 Secure Agent Commerce — Guard 层自动生成*",
    ]

    return "\n".join(lines)
