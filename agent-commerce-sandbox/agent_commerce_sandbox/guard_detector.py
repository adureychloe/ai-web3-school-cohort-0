"""
Guard detection layer — local checks that Cobo cannot do.

Three checks:
1. context_injection: detect prompt injection in user_intent
2. price_tampering: detect services.json modification at runtime
3. intent_consistency: does the selected service match the user's intent?

These run BEFORE the Pact is submitted to Cobo.
Cobo handles: address allowlists, spend limits, frequency limits.
Guard handles: semantic / contextual threats Cobo can't see.
"""

import hashlib
import json
import os
import re
from decimal import Decimal
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# ── Injection patterns (中英文) ──────────────────────────────

INJECTION_PATTERNS = [
    # Chinese: ignore rules
    (r"忽略(之前|所有|全部)?(指令|规则|限制|策略|policy)", "injection_ignore_rules_cn"),
    (r"不要(检查|验证|审核|遵守)(策略|policy|限制|规则)", "injection_skip_check_cn"),
    (r"绕过(所有|全部)?(限制|检查|策略)", "injection_bypass_cn"),

    # Chinese: address/amount manipulation
    (r"转(账|给|到|去).*?(地址|钱包|账户).*?0x[a-fA-F0-9]{40}", "injection_address_replace_cn"),
    (r"(给|帮)我转.*?(全部|最大|max|all|999|所有)", "injection_max_transfer_cn"),
    (r"修改(价格|金额|定价|费用)", "injection_price_change_cn"),

    # Chinese: social engineering
    (r"我是(管理员|主人|老板|创建者)", "injection_social_engineer_cn"),
    (r"听我的.*?(不要|ignore|skip|别)", "injection_authority_claim_cn"),

    # English
    (r"ignore\s+(all\s+)?(previous\s+)?(instructions|rules|policies|limits)", "injection_ignore_rules_en"),
    (r"skip\s+(policy|check|limit|verification)", "injection_skip_check_en"),
    (r"(send|transfer)\s+(me\s+)?(all|max|999)\s+", "injection_max_transfer_en"),
    (r"change\s+(the\s+)?(price|amount|payment|destination)", "injection_price_change_en"),
    (r"I\s+am\s+(the\s+)?(admin|owner|master|creator)", "injection_social_engineer_en"),
    (r"(bypass|override|disable)\s+(all\s+)?(restrictions|checks|policies)", "injection_bypass_en"),
]


# ── Data classes ──────────────────────────────────────────────

@dataclass
class GuardCheck:
    name: str
    passed: bool
    severity: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    detail: str
    evidence: Any = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GuardResult:
    passed: bool
    checks: list
    risk_score: float  # 0.0 ~ 1.0
    verdict: str       # "pass" | "block"
    blocking_reasons: list
    report_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": [c.to_dict() if isinstance(c, GuardCheck) else c for c in self.checks],
            "risk_score": self.risk_score,
            "verdict": self.verdict,
            "blocking_reasons": self.blocking_reasons,
            "report_data": self.report_data or None,
        }


# ── Individual checks ────────────────────────────────────────

def check_context_injection(user_intent: str) -> GuardCheck:
    """Detect prompt injection patterns in user intent.

    Cobo can't see the user's raw prompt — this is purely a Guard
    responsibility.
    """
    if not user_intent:
        return GuardCheck(
            name="context_injection",
            passed=True,
            severity="HIGH",
            detail="No user intent to analyze",
        )

    for pattern, pattern_name in INJECTION_PATTERNS:
        match = re.search(pattern, user_intent, re.IGNORECASE)
        if match:
            return GuardCheck(
                name="context_injection",
                passed=False,
                severity="HIGH",
                detail=f"Detected injection pattern: {pattern_name}",
                evidence={
                    "pattern": pattern_name,
                    "matched_text": match.group(0),
                    "position": match.span(),
                },
            )

    return GuardCheck(
        name="context_injection",
        passed=True,
        severity="HIGH",
        detail="No injection patterns detected",
    )


def check_price_tampering(
    service_id: str,
    quote_amount: str,
    services_data: dict,
    registry_snapshot: dict,
) -> GuardCheck:
    """Detect if services.json was modified at runtime.

    Two checks:
    1. Current content hash vs startup snapshot hash
    2. Quote amount vs registered price
    """
    # Check 1: content hash comparison
    current_content = json.dumps(services_data, sort_keys=True).encode()
    current_hash = hashlib.sha256(current_content).hexdigest()
    snapshot_content = json.dumps(registry_snapshot, sort_keys=True).encode()
    snapshot_hash = hashlib.sha256(snapshot_content).hexdigest()

    if current_hash != snapshot_hash:
        return GuardCheck(
            name="price_tampering",
            passed=False,
            severity="CRITICAL",
            detail="services.json hash mismatch — file was modified at runtime",
            evidence={
                "snapshot_hash": snapshot_hash[:16],
                "current_hash": current_hash[:16],
            },
        )

    # Check 2: quote amount vs registered price
    for svc in services_data.get("services", []):
        if svc["id"] == service_id:
            registered_price = svc.get("price", {}).get("amount", "0")
            if Decimal(str(quote_amount).strip()) != Decimal(str(registered_price).strip()):
                return GuardCheck(
                    name="price_tampering",
                    passed=False,
                    severity="CRITICAL",
                    detail=f"Quote amount ({quote_amount}) != registered price ({registered_price})",
                    evidence={
                        "service_id": service_id,
                        "quote_amount": quote_amount,
                        "registered_price": registered_price,
                    },
                )
            break

    return GuardCheck(
        name="price_tampering",
        passed=True,
        severity="CRITICAL",
        detail="services.json hash matches, quote matches registered price",
    )


def check_intent_consistency(
    user_intent: str,
    service_name: str,
    service_description: str,
) -> GuardCheck:
    """Check if the selected service matches the user's intent.

    Uses simple keyword overlap analysis.
    Low overlap → MEDIUM alert (informational, does not block).
    """

    def _tokenize(text: str) -> set:
        """Extract meaningful keywords from text.

        Uses character-level tokenization for Chinese (individual meaningful
        characters + bigrams) and word-level for English.
        """
        text = text.lower()
        # Common stop chars/words to filter out
        stop_chars = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
            "都", "一", "上", "也", "很", "到", "说", "要", "去",
            "你", "会", "着", "看", "好", "自己", "这", "他", "她",
            "它", "们", "那", "些", "能", "为", "吗", "吧", "啊", "呢",
            "帮", "让", "把", "被", "从", "个", "与", "对", "等", "或",
            "之", "中", "于", "还", "又", "再", "才", "已", "将", "没",
        }
        stop_en = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "just", "get",
            "and", "or", "but", "if", "as", "at", "by",
        }
        words = set()

        # Chinese: extract individual characters (filter stop chars)
        cn_chars = re.findall(r'[\u4e00-\u9fff]', text)
        cn_meaningful = [c for c in cn_chars if c not in stop_chars]
        words.update(cn_meaningful)

        # Chinese: bigrams (consecutive 2-char pairs for better matching)
        for i in range(len(cn_meaningful) - 1):
            bigram = cn_meaningful[i] + cn_meaningful[i + 1]
            words.add(bigram)

        # English words
        en_words = re.findall(r'[a-z0-9]{3,}', text)
        for w in en_words:
            if w not in stop_en:
                words.add(w)

        return words

    intent_words = _tokenize(user_intent)
    service_text = f"{service_name} {service_description}"
    service_words = _tokenize(service_text)

    if not intent_words or not service_words:
        return GuardCheck(
            name="intent_consistency",
            passed=True,
            severity="MEDIUM",
            detail="Not enough text to analyze intent consistency",
        )

    overlap = intent_words & service_words
    jaccard = len(overlap) / len(intent_words | service_words) if (intent_words | service_words) else 0

    if jaccard < 0.05:
        return GuardCheck(
            name="intent_consistency",
            passed=False,
            severity="MEDIUM",
            detail=f"Low intent-service overlap (jaccard={jaccard:.2f})",
            evidence={
                "jaccard_similarity": round(jaccard, 2),
                "intent_keywords": sorted(intent_words),
                "service_keywords": sorted(service_words),
                "overlap": sorted(overlap),
            },
        )

    return GuardCheck(
        name="intent_consistency",
        passed=True,
        severity="MEDIUM",
        detail=f"Intent matches service (jaccard={jaccard:.2f})",
        evidence={"jaccard_similarity": round(jaccard, 2)},
    )


# ── Main entry ────────────────────────────────────────────────

def check_guard(
    user_intent: str,
    service_id: str,
    quote_amount: str,
    services_data: dict,
    registry_snapshot: dict,
    service_name: str,
    service_description: str,
) -> GuardResult:
    """Run all guard checks and aggregate results.

    Verdict logic:
    - Any CRITICAL fail → block (risk_score=1.0)
    - Any HIGH fail → block (risk_score=0.8)
    - MEDIUM fails → pass (informational only, risk_score=0.3)
    - All pass → pass (risk_score=0.0)
    """
    checks = [
        check_context_injection(user_intent),
        check_price_tampering(service_id, quote_amount, services_data, registry_snapshot),
        check_intent_consistency(user_intent, service_name, service_description),
    ]

    blocking_reasons = []
    risk_score = 0.0
    for c in checks:
        if not c.passed:
            if c.severity == "CRITICAL":
                risk_score = max(risk_score, 1.0)
                blocking_reasons.append(f"[{c.severity}] {c.name}: {c.detail}")
            elif c.severity == "HIGH":
                risk_score = max(risk_score, 0.8)
                blocking_reasons.append(f"[{c.severity}] {c.name}: {c.detail}")
            elif c.severity == "MEDIUM":
                risk_score = max(risk_score, 0.3)
                # MEDIUM doesn't block, just warn

    verdict = "block" if any(
        not c.passed and c.severity in ("CRITICAL", "HIGH") for c in checks
    ) else "pass"

    report_data = {
        "total_checks": len(checks),
        "passed_count": sum(1 for c in checks if c.passed),
        "failed_count": sum(1 for c in checks if not c.passed),
    }

    return GuardResult(
        passed=verdict == "pass",
        checks=checks,
        risk_score=risk_score,
        verdict=verdict,
        blocking_reasons=blocking_reasons,
        report_data=report_data,
    )
