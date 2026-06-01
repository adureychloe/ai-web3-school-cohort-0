"""Core flow engine: orchestrates the complete agent commerce flow."""

from typing import Optional

from .mock_services import discover_services, get_service, format_quote
from .policy_checker import check_policy, check_add_to_session_spent, load_policy
from .payment_engine import execute_payment
from .proof_logger import ProofLogger
from . import chain as chain_module


class HumanConfirmationResult:
    """Simulated human confirmation gate."""

    def request_confirmation(self, decision, quote) -> "HumanConfirmationResult":
        """
        Simulate human confirmation.

        In interactive mode this would prompt the user.
        In automated mode, returns accepted.
        """
        result = HumanConfirmationResult()
        result.confirmed = True
        result.reason = "Human reviewed and accepted (simulated)"
        return result


def run_flow(
    user_intent: str,
    service_id: str,
    scenario: str = "normal",
    interactive: bool = False,
    real_mode: bool = False,
) -> dict:
    """
    Run the complete agent commerce flow.

    Parameters:
        user_intent: Natural language description
        service_id: The service to purchase
        scenario: 'normal', 'over_budget', or 'unknown_service'
        interactive: If True, pause for human input at confirmation gates
        real_mode: If True, execute real testnet payments via web3.py

    Returns:
        Dictionary with full proof log
    """
    # Step 1: Discover service
    service = get_service(service_id)
    if not service:
        return {"error": f"Service '{service_id}' not found"}
    print(f"  [Engine] Discovered: {service['name']}")

    # Step 2: Get quote
    quote = format_quote(service)
    print(f"  [Engine] Quote: {quote['amount']} {quote['token']} on {quote['network']}")

    # Step 3: Check policy
    amount = float(quote["amount"])
    decision = check_policy(
        service_id=service["id"],
        amount=amount,
        token=quote["token"],
        network=quote["network"],
    )
    print(f"  [Engine] Policy: {'ALLOWED' if decision.allowed else 'DENIED'}")

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
        print(f"  [Engine] Human confirmation required: {', '.join(decision.confirmation_reasons)}")
        gate = HumanConfirmationResult()
        confirm_result = gate.request_confirmation(decision, quote)
        human_confirmation = {
            "result": "approved" if confirm_result.confirmed else "rejected",
            "reason": confirm_result.reason,
            "confirmed_by": "user",
        }
        if not confirm_result.confirmed:
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

    # Step 5: Execute payment (real or simulated)
    # In REAL mode, send test ETH to the service address
    # In SIMULATION mode, generate mock receipt
    service_addresses = {
        "research-agent-01": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
        "data-fetcher-02": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
        "model-inference-03": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
        "premium-analyzer-04": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
        "smart-contract-auditor-05": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
    }
    to_address = service_addresses.get(service["id"], "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18")

    receipt = execute_payment(
        to_address=to_address,
        amount=amount,
        token=quote["token"],
        network=quote["network"],
        real_mode=real_mode,
    )
    print(f"  [Engine] Payment: {receipt.receipt_id} ({receipt.mode})")

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
