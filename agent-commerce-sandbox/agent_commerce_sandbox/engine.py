"""
Core flow engine — orchestrates service discovery, payment, and delivery proof.

Flow:
  1. Query ServiceRegistry contract for services
  2. User selects a service and states intent
  3. Submit CAW Pact (transfer + contract_call policies)
  4. Wait for user to approve in CAW App
  5. Execute CAW Transfer
  6. Record delivery proof via CAW tx call (under same pact)
"""

import json
import time
from web3 import Web3

from .chain_client import ChainClient
from .caw_client import CawClient


def discover_services() -> list:
    """Discover all active services from the ServiceRegistry contract.

    Returns:
        List of formatted service dicts.
    """
    print("=" * 60)
    print("  Service Discovery — On-Chain")
    print("=" * 60)
    print()

    client = ChainClient()
    services = client.list_services()

    if not services:
        print("  No active services found on-chain.")
        return []

    print(f"  Found {len(services)} active service(s) on Sepolia:\n")
    for s in services:
        price_eth = Web3.from_wei(s["priceWei"], "ether")
        print(f"  [{s['id']}] {s['name']}")
        print(f"        {s['description']}")
        print(f"        {price_eth} {s['tokenId']} on {s['chainId']}")
        print(f"        Provider: {s['provider'][:10]}...{s['provider'][-6:]}")
        print()

    return services


def pay_for_service(service_id: int, user_intent: str) -> dict:
    """Run the full payment flow for a service.

    Args:
        service_id: Service ID from the contract
        user_intent: Natural language description of the user's request

    Returns:
        Dict with full execution summary including tx hashes and proof info.
    """
    result = {
        "status": "started",
        "service": None,
        "pact": None,
        "transfer": None,
        "proof": None,
        "error": None,
    }

    print("=" * 60)
    print("  Agent Commerce Hub — Payment Flow")
    print("=" * 60)
    print()

    # ── Step 1: Get service from contract ─────────────────
    print("[1/5] Querying ServiceRegistry contract...")
    chain = ChainClient()

    try:
        service = chain.get_service(service_id)
    except Exception as e:
        msg = f"Service {service_id} not found on-chain: {e}"
        print(f"  ❌ {msg}")
        result["status"] = "failed"
        result["error"] = msg
        return result

    if not service["active"]:
        msg = f"Service {service_id} is deactivated"
        print(f"  ❌ {msg}")
        result["status"] = "failed"
        result["error"] = msg
        return result

    price_eth = Web3.from_wei(service["priceWei"], "ether")
    print(f"  ✅ Found: [{service['id']}] {service['name']}")
    print(f"     Price: {price_eth} {service['tokenId']} on {service['chainId']}")
    print(f"     Pay to: {service['paymentAddress']}")
    result["service"] = service
    print()

    # ── Step 2: Submit CAW Pact ───────────────────────────
    print("[2/5] Submitting CAW Pact...")
    caw = CawClient()

    service_name = service["name"]
    amount_str = str(price_eth)

    pact_intent = f"Pay {amount_str} {service['tokenId']} for {service_name}. User request: {user_intent[:200]}"

    execution_plan = (
        f"# Summary\n"
        f"Pay for {service_name} via Cobo Agentic Wallet\n\n"
        f"# Operations\n"
        f"- Transfer {amount_str} {service['tokenId']} to {service['paymentAddress']} on {service['chainId']}\n\n"
        f"# Risk Controls\n"
        f"- Single transfer, capped at {amount_str} {service['tokenId']}"
    )

    import json
    # Build policies dynamically — transfer for payment + contract_call for delivery proof
    payment_addr = service["paymentAddress"]
    token_id = service["tokenId"]
    chain_id = service["chainId"]
    contract_addr = chain.contract_addr
    service_name_short = service_name.lower().replace(" ", "-")[:20]
    policies_json = json.dumps([
        {
            "name": f"pay-{service_name_short}",
            "type": "transfer",
            "rules": {
                "effect": "allow",
                "when": {
                    "chain_in": [chain_id],
                    "token_in": [{"chain_id": chain_id, "token_id": token_id}],
                    "destination_address_in": [
                        {"chain_id": chain_id, "address": payment_addr}
                    ],
                },
                "deny_if": {"amount_usd_gt": "5.00"},
            },
        },
        {
            "name": "record-delivery",
            "type": "contract_call",
            "rules": {
                "effect": "allow",
                "when": {
                    "chain_in": [chain_id],
                    "target_in": [
                        {"chain_id": chain_id, "contract_addr": contract_addr}
                    ],
                },
            },
        },
    ])
    # Two tx needed: transfer + contract_call for recordDelivery
    completion_conditions = json.dumps([{"type": "tx_count", "threshold": "2"}])

    # Update execution plan to mention both steps
    execution_plan = (
        f"# Summary\n"
        f"Pay for {service_name} and record delivery proof via Cobo Agentic Wallet\n\n"
        f"# Operations\n"
        f"1. Transfer {amount_str} {token_id} to {payment_addr} on {chain_id}\n"
        f"2. Call recordDelivery() on ServiceRegistry ({contract_addr}) to record proof\n\n"
        f"# Risk Controls\n"
        f"- Transfer capped at {amount_str} {token_id}\n"
        f"- Contract call limited to ServiceRegistry.recordDelivery()"
    )

    try:
        pact = caw.submit_pact(
            intent=pact_intent,
            policies_json=policies_json,
            completion_conditions=completion_conditions,
            name=f"pay-{service_name.lower().replace(' ', '-')[:30]}",
            execution_plan=execution_plan,
        )
        pact_id = pact.get("pact_id", "unknown")
        pact_status = pact.get("status", "unknown")
        print(f"  ✅ Pact submitted!")
        print(f"     Pact ID: {pact_id}")
        print(f"     Status: {pact_status}")
        result["pact"] = pact

        if pact_status in ("pending_approval", "PENDING_APPROVAL"):
            print()
            print("  ╔══════════════════════════════════════════════════╗")
            print("  ║   📱 Open your Cobo Agentic Wallet App          ║")
            print("  ║   and APPROVE the pact to continue.              ║")
            print("  ╚══════════════════════════════════════════════════╝")
            print()

            # ── Step 3: Wait for approval ──────────────────
            print("[3/5] Waiting for pact approval...")
            try:
                active_pact = caw.wait_for_pact_active(pact_id, timeout=300)
                print(f"  ✅ Pact approved! Now ACTIVE.")
                result["pact"] = active_pact
            except TimeoutError:
                msg = "Pact approval timed out. Please approve in the CAW App and try again."
                print(f"  ❌ {msg}")
                result["status"] = "pending_approval"
                result["error"] = msg
                return result
        elif pact_status in ("active", "ACTIVE"):
            print(f"  ✅ Pact already active.")
        else:
            print(f"  ⚠️  Unexpected pact status: {pact_status}")
    except Exception as e:
        msg = f"Pact submission failed: {e}"
        print(f"  ❌ {msg}")
        result["status"] = "failed"
        result["error"] = msg
        return result

    print()

    # ── Step 4: Execute Transfer ──────────────────────────
    print("[4/5] Executing CAW Transfer...")

    # Use the service's payment address as destination
    dst_addr = service["paymentAddress"]
    # For demo purposes, send to own wallet (limited SETH balance)
    # In production, this would be the service provider's address
    # dst_addr = caw.WALLET_SETH_ADDR

    try:
        tx_result = caw.execute_transfer(
            pact_id=pact_id,
            dst_address=dst_addr,
            amount=amount_str,
            token_id=service["tokenId"],
            chain_id=service["chainId"],
            description=f"Payment for {service_name}: {user_intent[:100]}",
        )
        tx_id = tx_result.get("id", "unknown")
        tx_status = tx_result.get("status", "unknown")
        print(f"  ✅ Transfer submitted!")
        print(f"     Transaction ID: {tx_id}")
        print(f"     Status: {tx_status}")
        result["transfer"] = tx_result

        # If processing, wait for completion
        if tx_status == "Processing":
            tx_complete = caw.wait_for_transaction_complete(tx_id, timeout=120)
            tx_onchain_hash = tx_complete.get("transaction_hash", "")
            print(f"     On-chain Tx: {tx_onchain_hash}")
            result["transfer"] = tx_complete
            result["tx_hash"] = tx_onchain_hash
        else:
            result["tx_hash"] = ""

    except Exception as e:
        msg = f"Transfer failed: {e}"
        print(f"  ❌ {msg}")
        result["status"] = "failed"
        result["error"] = msg
        return result

    print()

    # ── Step 5: Record Delivery Proof via CAW tx call ────
    print("[5/5] Recording delivery proof on-chain via CAW...")

    tx_hash_for_proof = result.get("tx_hash", "")
    summary = f"Delivered {service_name} — {user_intent[:100]}"

    try:
        import json as _json
        # Encode recordDelivery(service_id, tx_hash, summary) calldata
        call_data = caw.abi_encode(
            "recordDelivery(uint256,string,string)",
            [service_id, tx_hash_for_proof, summary],
        )

        # Execute via CAW tx call under the same pact
        call_result = caw.execute_contract_call(
            pact_id=pact_id,
            contract_address=chain.contract_addr,
            calldata=call_data,
            chain_id=chain_id,
            request_id=f"delivery-{service_id}-{int(time.time())}",
        )
        call_tx_id = call_result.get("id", "")
        print(f"     Call submitted, tx_id={call_tx_id[:20]}...")

        if call_tx_id:
            call_complete = caw.wait_for_transaction_complete(call_tx_id, timeout=120)
            result["proof"] = call_complete
            proof_tx_hash = call_complete.get("transaction_hash", "")
            print(f"  ✅ Delivery proof recorded on-chain via CAW!")
            if proof_tx_hash:
                print(f"     Proof Tx: {proof_tx_hash}")

            # Show final summary
            print()
            print("─" * 60)
            print("  ✅ PAYMENT COMPLETE (CAW-only)")
            print("─" * 60)
            print(f"  Service:  {service_name}")
            print(f"  Amount:   {amount_str} {service['tokenId']}")
            print(f"  Pact ID:  {pact_id}")
            if tx_hash_for_proof:
                print(f"  Tx Hash:  {tx_hash_for_proof}")
            if proof_tx_hash:
                print(f"  Proof Tx: {proof_tx_hash}")
            print(f"  Contract: {chain.contract_addr}")
            print()

            result["status"] = "completed"
        else:
            msg = "Contract call submitted but no tx_id returned"
            print(f"  ⚠️  {msg}")
            result["status"] = "payment_completed"
            result["error"] = msg
    except Exception as e:
        msg = f"Proof recording failed (payment succeeded): {e}"
        print(f"  ⚠️  {msg}")
        result["status"] = "payment_completed"
        result["error"] = msg

    return result


def show_proofs(service_id: int = 0) -> list:
    """Show delivery proofs from the contract.

    Args:
        service_id: If > 0, filter by service ID

    Returns:
        List of proof dicts.
    """
    chain = ChainClient()
    count = chain.get_proof_count()

    print(f"\n  Delivery proofs on-chain: {count} total\n")

    if count == 0:
        return []

    proofs = chain.get_proofs(0, count)
    filtered = [p for p in proofs if service_id == 0 or p["serviceId"] == service_id]

    for p in filtered:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(p["timestamp"]))
        print(f"  [{p['serviceId']}] {p['summary'][:50]}")
        print(f"        Tx: {p['txHash'][:30]}...")
        print(f"        Agent: {p['agent'][:10]}...")
        print(f"        Time: {ts}")
        print()

    return filtered
