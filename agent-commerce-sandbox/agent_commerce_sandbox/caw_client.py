"""
CAW Client — Python wrapper around the `caw` CLI.

Provides methods for pact submission, transfer execution, and transaction
tracking. All actual API calls go through the `caw` binary, which handles
authentication via the local credentials store (~/.cobo-agentic-wallet/).
"""

import json
import subprocess
import time
from typing import Optional


# ── Constants ─────────────────────────────────────────────────

# Our CAW wallet's SETH address on Sepolia
WALLET_SETH_ADDR = "0x9e01312e8e96a8133a3c73bed58a5808ecfceaf5"

# Default policy template for transfers — allows transfer to our own address
# with a $0.01 max. Adjust for larger amounts as needed.
DEFAULT_POLICY = json.dumps([
    {
        "name": "service-payment",
        "type": "transfer",
        "rules": {
            "effect": "allow",
            "when": {
                "chain_in": ["SETH"],
                "token_in": [{"chain_id": "SETH", "token_id": "SETH"}],
                "destination_address_in": [
                    {"chain_id": "SETH", "address": WALLET_SETH_ADDR}
                ],
            },
            "deny_if": {"amount_usd_gt": "0.01"},
        },
    }
])


# ── Helpers ───────────────────────────────────────────────────

def _run_caw(*args: str, timeout: int = 60) -> dict:
    """Run a `caw` CLI command and return parsed JSON output.

    Args:
        *args: caw subcommand and flags
        timeout: HTTP timeout in seconds

    Returns:
        Parsed JSON dict from caw stdout

    Raises:
        RuntimeError: if caw exits non-zero or returns invalid JSON
    """
    cmd = ["caw"] + list(args) + ["--timeout", str(timeout)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"caw failed (exit={result.returncode}): {stderr[:300]}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"caw returned invalid JSON: {result.stdout[:200]}") from e


# ── Public API ────────────────────────────────────────────────

class CawClient:
    """Wrapper around the `caw` CLI for Cobo Agentic Wallet operations."""

    # ── Pacts ──────────────────────────────────────────────

    def submit_pact(
        self,
        intent: str,
        policies_json: str = DEFAULT_POLICY,
        completion_conditions: Optional[str] = None,
        execution_plan: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict:
        """Submit a pact for approval.

        Args:
            intent: Natural language description of the pact's purpose
            policies_json: JSON string of policy array
            completion_conditions: JSON string of completion conditions
            execution_plan: Markdown execution plan
            name: Optional human-readable name

        Returns:
            Dict with pact_id, status, etc.
        """
        if completion_conditions is None:
            completion_conditions = json.dumps([{"type": "tx_count", "threshold": "1"}])
        if execution_plan is None:
            execution_plan = "# Summary\nAgent Commerce Hub payment\n\n# Operations\n- Transfer SETH for service\n\n# Risk Controls\n- One-time transfer"

        args = [
            "pact", "submit",
            "--intent", intent,
            "--policies", policies_json,
            "--completion-conditions", completion_conditions,
            "--execution-plan", execution_plan,
        ]
        if name:
            args += ["--name", name]

        data = _run_caw(*args)
        return data.get("result", data)

    def get_pact(self, pact_id: str) -> dict:
        """Get pact details by ID.

        Returns:
            Dict with status, spec, operator info, etc.
        """
        return _run_caw("pact", "show", "--pact-id", pact_id)

    def wait_for_pact_active(self, pact_id: str, timeout: int = 300, poll_interval: int = 5) -> dict:
        """Poll pact status until it becomes ACTIVE or timeout.

        Args:
            pact_id: Pact UUID
            timeout: Max seconds to wait
            poll_interval: Seconds between polls

        Returns:
            Pact details dict with status='active'

        Raises:
            TimeoutError: if pact doesn't become active within timeout
        """
        deadline = time.time() + timeout
        last_status = None

        while time.time() < deadline:
            pact = self.get_pact(pact_id)
            status = pact.get("status", "unknown")
            if status != last_status:
                print(f"  [CAW] Pact {pact_id[:12]}... status={status}")
                last_status = status
            if status == "active":
                return pact
            time.sleep(poll_interval)

        raise TimeoutError(
            f"Pact {pact_id} did not become active within {timeout}s "
            f"(last status: {last_status})"
        )

    # ── Transfers ──────────────────────────────────────────

    def execute_transfer(
        self,
        pact_id: str,
        dst_address: str = WALLET_SETH_ADDR,
        amount: str = "0.00001",
        token_id: str = "SETH",
        chain_id: str = "SETH",
        src_address: str = WALLET_SETH_ADDR,
        description: Optional[str] = None,
    ) -> dict:
        """Execute a token transfer under an active pact.

        Args:
            pact_id: Active pact UUID
            dst_address: Destination on-chain address
            amount: Amount as decimal string (e.g. "0.00001")
            token_id: Token ID (e.g. "SETH")
            chain_id: Chain ID (e.g. "SETH")
            src_address: Source address (REQUIRED by CAW API)
            description: Optional description

        Returns:
            Dict with transfer result (id, status, etc.)
        """
        args = [
            "tx", "transfer",
            "--pact-id", pact_id,
            "--src-address", src_address,
            "--dst-address", dst_address,
            "--amount", amount,
            "--token-id", token_id,
            "--chain-id", chain_id,
        ]
        if description:
            args += ["--description", description]

        data = _run_caw(*args, timeout=120)
        return data

    def get_transaction(self, tx_id: str) -> dict:
        """Get transaction details by ID.

        Args:
            tx_id: Transaction UUID (from execute_transfer result)

        Returns:
            Dict with status, transaction_hash, etc.
        """
        return _run_caw("tx", "get", "--tx-id", tx_id)

    def wait_for_transaction_complete(self, tx_id: str, timeout: int = 120, poll_interval: int = 3) -> dict:
        """Poll transaction until status is complete or timeout.

        Args:
            tx_id: Transaction UUID
            timeout: Max seconds to wait
            poll_interval: Seconds between polls

        Returns:
            Full transaction details dict
        """
        deadline = time.time() + timeout
        last_status = None

        while time.time() < deadline:
            tx = self.get_transaction(tx_id)
            status = tx.get("status", "unknown")
            sub_status = tx.get("sub_status", "")
            if status != last_status:
                print(f"  [CAW] Tx {tx_id[:12]}... status={status}/{sub_status}")
                last_status = status
            if status == "Success":
                return tx
            if status in ("Failed", "Denied", "Expired"):
                return tx
            time.sleep(poll_interval)

        raise TimeoutError(f"Transaction {tx_id} did not complete within {timeout}s")
