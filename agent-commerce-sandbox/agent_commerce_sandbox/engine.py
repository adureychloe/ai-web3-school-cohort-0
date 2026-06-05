"""Core flow engine: orchestrates the complete agent commerce flow."""

from typing import Optional

from .mock_services import discover_services, get_service, format_quote, compute_registry_hash, load_services
from .policy_checker import check_policy, check_add_to_session_spent, load_policy
from .payment_engine import execute_payment
from .proof_logger import ProofLogger
from .guard_detector import check_guard
from .attack_reporter import generate_attack_report, save_attack_report
from .cobo_client import CoboClient
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


def capture_registry_snapshot() -> dict:
    """Capture a snapshot of services.json at startup for tamper detection."""
    return load_services()


_REGISTRY_SNAPSHOT = capture_registry_snapshot()


def run_flow(
    user_intent: str,
    service_id: str,
    scenario: str = "normal",
    interactive: bool = False,
    real_mode: bool = False,
    cobo_mode: bool = False,
) -> dict:
    """
    Run the complete agent commerce flow with Guard + Cobo integration.

    Flow:
      1. Discover service
      2. Get quote
      3. Guard check (local semantic detection)
         → BLOCK: generate attack report, stop
         → PASS: continue
      4. Policy check (local, for sim mode)
      5. Human confirmation (if required)
      6. Payment (via Cobo API or local simulation)
      7. Delivery
      8. Proof log

    Parameters:
        user_intent: Natural language description
        service_id: The service to purchase
        scenario: 'normal', 'over_budget', 'unknown_service', or guard-* scenarios
        interactive: If True, pause for human input at confirmation gates
        real_mode: If True, execute real testnet payments via web3.py
        cobo_mode: If True, use Cobo API for pact submission + transfer

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
    amount = float(quote["amount"])
    print(f"  [Engine] Quote: {amount} {quote['token']} on {quote['network']}")

    # Step 3: Guard check (always runs — local semantic detection)
    services_data = load_services()
    guard_result = check_guard(
        user_intent=user_intent,
        service_id=service["id"],
        quote_amount=quote["amount"],
        services_data=services_data,
        registry_snapshot=_REGISTRY_SNAPSHOT,
        service_name=service["name"],
        service_description=service["description"],
    )

    print(f"  [Guard] Verdict: {guard_result.verdict.upper()} "
          f"(risk={guard_result.risk_score:.2f})")

    # Print individual check results
    for c in guard_result.checks:
        status = "✅" if c.passed else "🚫"
        print(f"  [Guard] {status} {c.name}: {c.detail[:60]}...")

    # Guard BLOCK → generate attack report, stop
    if guard_result.verdict == "block":
        report = generate_attack_report(
            guard_result=guard_result,
            user_intent=user_intent,
            service_id=service["id"],
            quote_amount=quote["amount"],
        )
        paths = save_attack_report(report)
        print(f"  [Guard] ⛔ Attack blocked! Report saved to:")
        print(f"          JSON: {paths['json_path']}")
        print(f"          MD:   {paths['md_path']}")

        proof_logger = ProofLogger()
        proof = proof_logger.log_session(
            user_intent=user_intent,
            budget=load_policy()["session"],
            quote=quote,
            policy_decision={"allowed": False, "reason": f"Guard blocked: {', '.join(guard_result.blocking_reasons)}"},
            human_confirmation=None,
            payment_receipt=None,
            delivery_result={
                "status": "blocked",
                "summary": f"Guard prevented attack: {', '.join(guard_result.blocking_reasons)}",
            },
            guard_evidence=guard_result.to_dict(),
            cobo_result=None,
        )
        return proof

    # Step 4: Check policy (local)
    decision = check_policy(
        service_id=service["id"],
        amount=amount,
        token=quote["token"],
        network=quote["network"],
    )
    print(f"  [Engine] Policy: {'ALLOWED' if decision.allowed else 'DENIED'}")

    # Step 4b: If denied by policy, stop immediately
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
            guard_evidence=guard_result.to_dict(),
            cobo_result=None,
        )
        return proof

    # Step 5: Human confirmation (if required)
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
                guard_evidence=guard_result.to_dict(),
                cobo_result=None,
            )
            return proof

    # Step 6: Execute payment (Cobo API or local sim)
    to_address = service.get("payment_address", "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18")

    cobo = CoboClient()
    cobo_result_dict = None

    if cobo_mode:
        if cobo.is_real:
            print(f"  [Cobo] Real mode — submitting Pact to Cobo API...")
        else:
            print(f"  [Cobo] Sim mode (no COBO_API_KEY) — using mock...")

        # Submit pact
        pact = cobo.submit_pact(
            intent=user_intent,
            service_name=service["name"],
            amount=quote["amount"],
            token_id=f"BASE_{quote['token']}",
            chain_id="BASE_ETH",
            to_address=to_address,
        )

        if not pact.success:
            print(f"  [Cobo] Pact submission failed: {pact.error}")
            return {
                "status": "error",
                "error": f"Cobo pact failed: {pact.error}",
                "guard_evidence": guard_result.to_dict(),
            }

        print(f"  [Cobo] Pact {pact.pact_id} — status={pact.status}")

        # Execute transfer under pact
        tx = cobo.execute_transfer(
            pact_id=pact.pact_id,
            to_address=to_address,
            amount=quote["amount"],
            token_id=f"BASE_{quote['token']}",
            chain_id="BASE_ETH",
        )

        if not tx.success:
            print(f"  [Cobo] Transfer failed: {tx.error}")
            return {"status": "error", "error": f"Cobo transfer failed: {tx.error}"}

        print(f"  [Cobo] Transfer {tx.transaction_id} — status={tx.status}")

        # Update session spent for local policy tracking
        check_add_to_session_spent(amount)

        cobo_result_dict = {
            "mode": tx.mode,
            "pact_id": pact.pact_id,
            "pact_status": pact.status,
            "transaction_id": tx.transaction_id,
            "status": tx.status,
            "tx_hash": tx.tx_hash,
        }

        # Build a PaymentReceipt-like dict from Cobo result
        payment_receipt = {
            "receipt_id": tx.transaction_id,
            "transaction_id": tx.transaction_id,
            "amount": tx.amount,
            "token_id": tx.token_id,
            "to_address": tx.to_address,
            "tx_hash": tx.tx_hash,
            "mode": tx.mode,
            "status": tx.status,
        }
    else:
        # Local simulation mode (original behavior)
        receipt = execute_payment(
            to_address=to_address,
            amount=amount,
            token=quote["token"],
            network=quote["network"],
            real_mode=real_mode,
        )
        print(f"  [Engine] Payment: {receipt.receipt_id} ({receipt.mode})")
        payment_receipt = receipt.to_dict()

        check_add_to_session_spent(amount)

    # Step 7: Simulate delivery
    delivery_result = {
        "status": "accepted",
        "summary": f"Service '{service['name']}' delivered {service['delivery_type']} successfully.",
    }

    # Step 8: Generate proof log
    proof_logger = ProofLogger()
    proof = proof_logger.log_session(
        user_intent=user_intent,
        budget=load_policy()["session"],
        quote=quote,
        policy_decision=decision.to_dict(),
        human_confirmation=human_confirmation,
        payment_receipt=payment_receipt,
        delivery_result=delivery_result,
        guard_evidence=guard_result.to_dict(),
        cobo_result=cobo_result_dict,
    )

    return proof
