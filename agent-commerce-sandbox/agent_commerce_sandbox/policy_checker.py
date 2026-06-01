"""Policy check engine: validate actions against policy.json rules."""

import json
import os
from typing import Optional

_POLICY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "policy.json")


def load_policy() -> dict:
    """Load policy configuration."""
    with open(_POLICY_PATH) as f:
        return json.load(f)


class PolicyDecision:
    """Result of a policy check."""

    def __init__(
        self,
        allowed: bool,
        reason: str,
        human_confirmation_required: bool = False,
        confirmation_reasons: Optional[list] = None,
    ):
        self.allowed = allowed
        self.reason = reason
        self.human_confirmation_required = human_confirmation_required
        self.confirmation_reasons = confirmation_reasons or []

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "human_confirmation_required": self.human_confirmation_required,
            "confirmation_reasons": self.confirmation_reasons,
        }


def check_add_to_session_spent(amount: float) -> dict:
    """Update session_spent after a successful payment."""
    policy = load_policy()
    policy["session"]["session_spent"] = str(
        round(float(policy["session"]["session_spent"]) + amount, 2)
    )
    with open(_POLICY_PATH, "w") as f:
        json.dump(policy, f, indent=2)
    return policy["session"]


def check_policy(
    service_id: str,
    amount: float,
    token: str,
    network: str,
    action_type: str = "payment",
) -> PolicyDecision:
    """
    Check whether a proposed service action is allowed by policy.

    Returns:
        PolicyDecision with allowed flag, reason, and human confirmation requirements.
    """
    policy = load_policy()

    # 1. Check token
    if token not in policy["allowed"]["tokens"]:
        return PolicyDecision(
            allowed=False,
            reason=f"Token '{token}' not in allowed list: {policy['allowed']['tokens']}",
        )

    # 2. Check network
    if network not in policy["allowed"]["networks"]:
        return PolicyDecision(
            allowed=False,
            reason=f"Network '{network}' not in allowed list: {policy['allowed']['networks']}",
        )

    # 3. Check high-risk action
    if action_type in policy["high_risk_actions"]:
        return PolicyDecision(
            allowed=False,
            reason=f"Action '{action_type}' is classified as high risk. Human confirmation required.",
            human_confirmation_required=True,
            confirmation_reasons=["high_risk_action_detected"],
        )

    # 4. Check allowlist
    in_allowlist = service_id in policy["allowed"]["allowlisted_service_ids"]

    # 5. Check session budget
    session_spent = float(policy["session"]["session_spent"])
    session_limit = float(policy["session"]["session_limit"])
    cumulative = session_spent + amount

    confirmation_reasons = []

    if not in_allowlist:
        confirmation_reasons.append("service_not_in_allowlist")

    if amount > float(policy["single_payment"]["auto_limit"]):
        confirmation_reasons.append("single_payment_exceeds_auto_limit")

    if cumulative > session_limit:
        return PolicyDecision(
            allowed=False,
            reason=f"Payment of {amount} would exceed session limit of {session_limit} "
                   f"(spent: {session_spent}, requested: {amount})",
        )

    if cumulative > session_limit * 0.5:
        confirmation_reasons.append("cumulative_session_exceeds_50_percent")

    # 6. Final decision
    human_confirm = len(confirmation_reasons) > 0

    if human_confirm:
        return PolicyDecision(
            allowed=True,
            reason=f"Payment allowed pending human confirmation. Reasons: {', '.join(confirmation_reasons)}",
            human_confirmation_required=True,
            confirmation_reasons=confirmation_reasons,
        )

    return PolicyDecision(
        allowed=True,
        reason=f"Auto-approved: service '{service_id}' is allowlisted, "
               f"amount {amount} {token} within auto-payment limit.",
        human_confirmation_required=False,
    )
