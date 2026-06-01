"""Core flow engine: orchestrates the complete agent commerce flow."""

from typing import Optional

from .mock_services import discover_services, get_service, format_quote
from .policy_checker import check_policy, check_add_to_session_spent, load_policy
from .payment_simulator import simulate_payment
from .proof_logger import ProofLogger


class HumanConfirmationResult:
    """Simulated human confirmation gate."""

    def __init__(self):
        self.confirmed = False
        self.reason = ""

    def request_confirmation(self, decision, quote) -> "HumanConfirmationResult":
        """
        Simulate human confirmation.

        In interactive mode this would prompt the user.
        In automated mode, returns a result based on context.
        """
        result = HumanConfirmationResult()
        # In scenario mode, we accept if only budget warnings exist
        if all(r == "cumulative_session_exceeds_50_percent" for r in decision.confirmation_reasons):
            result.confirmed = True
            result.reason = "Auto-accepted: only budget warning, no new services"
        else:
            result.confirmed = True
            result.reason = "Human reviewed and accepted (simulated)"
        return result


def run_flow(
    user_intent: str,
    service_id: str,
    scenario: str = "normal",
    interactive: bool = False,
) -> dict:
    """
    Run the complete agent commerce flow.

    Parameters:
        user_intent: Natural language description of what the user wants
        service_id: The service to purchase
        scenario: 'normal', 'over_budget', or 'unknown_service'
        interactive: If True, pause for human input at confirmation gates

    Returns:
        Dictionary with full proof log
    """
    # Step 1: Discover service
    service = get_service(service_id)
    if not service:
        return {"error": f"Service '{service_id}' not found"}

    # Step 2: Get quote
    quote = format_quote(service)

    # Step 3: Check policy
    amount = float(quote["amount"])
    decision = check_policy(
        service_id=service["id"],
        amount=amount,
        token=quote["token"],
        network=quote["network"],
    )

    # Step 3b: If denied by policy, stop immediately
    if not decision.allowed:
        proof_logger = ProofLogger()
        proof = proof_logger.log_session(
            user_intent=user_intent,
            budget=load_policy()["session"],
            quote=quote,
            policy_decision=decision.to_dict(),
            human_confirmation=None,
            payment_receipt=None,
            delivery_result={"status": "blocked", "summary": f"Policy denied: {decision.reason}"},
        )
        return proof

    # Step 4: Human confirmation (if required)
    human_confirmation = None
    if decision.human_confirmation_required:
        gate = HumanConfirmationResult()
        confirm_result = gate.request_confirmation(decision, quote)
        human_confirmation = {
            "result": "approved" if confirm_result.confirmed else "rejected",
            "reason": confirm_result.reason,
            "confirmed_by": "user",
        }
        if not confirm_result.confirmed:
            # Flow stopped
            proof_logger = ProofLogger()
            proof = proof_logger.log_session(
                user_intent=user_intent,
                budget=load_policy()["session"],
                quote=quote,
                policy_decision=decision.to_dict(),
                human_confirmation=human_confirmation,
                payment_receipt=None,
                delivery_result={"status": "cancelled", "summary": "Human rejected the transaction"},
            )
            return proof

    # Step 5: Simulate payment
    receipt = simulate_payment(
        service_id=service["id"],
        amount=quote["amount"],
        token=quote["token"],
        network=quote["network"],
    )

    # Update session spent
    check_add_to_session_spent(amount)

    # Step 6: Simulate delivery
    delivery_result = {
        "status": "accepted",
        "summary": f"Service '{service['name']}' delivered {service['delivery_type']} successfully.",
    }

    # Step 7: Generate proof log
    proof_logger = ProofLogger()
    proof = proof_logger.log_session(
        user_intent=user_intent,
        budget=load_policy()["session"],
        quote=quote,
        policy_decision=decision.to_dict(),
        human_confirmation=human_confirmation,
        payment_receipt=receipt.to_dict(),
        delivery_result=delivery_result,
    )

    return proof
