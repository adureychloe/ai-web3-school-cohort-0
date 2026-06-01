"""
Payment execution: dispatches to real testnet or simulation.

REAL mode: sends test ETH via web3.py to Base Sepolia.
SIMULATION mode: returns mock receipt (current default).
"""

from typing import Optional
from . import chain as chain_module


class PaymentReceipt:
    """Payment receipt (unified struct for both modes)."""

    def __init__(self, data: dict):
        self.data = data

    @property
    def receipt_id(self) -> str:
        return self.data.get("tx_hash", self.data.get("receipt_id", "unknown"))

    @property
    def amount(self) -> str:
        return self.data.get("amount_eth", self.data.get("amount", "0"))

    @property
    def token(self) -> str:
        return self.data.get("token", "ETH")

    @property
    def network(self) -> str:
        return self.data.get("network", "Base Sepolia")

    @property
    def mode(self) -> str:
        return self.data.get("mode", "simulation")

    def to_dict(self) -> dict:
        return self.data


def execute_payment(
    to_address: str,
    amount: float,
    token: str = "ETH",
    network: str = "Base",
    real_mode: bool = False,
    config: Optional[chain_module.ChainConfig] = None,
) -> PaymentReceipt:
    """
    Execute a payment.

    In REAL mode (real_mode=True + .env configured):
      - Sends test ETH via web3.py to Base Sepolia
      - Returns real tx receipt with tx_hash

    In SIMULATION mode (default):
      - Returns a mock receipt, no chain interaction
    """
    if real_mode:
        return _execute_real(to_address, amount, config)

    return _execute_simulated(to_address, amount, token, network)


def _execute_real(
    to_address: str,
    amount: float,
    config: Optional[chain_module.ChainConfig] = None,
) -> PaymentReceipt:
    """Real: send test ETH via web3.py."""
    if config is None:
        config = chain_module.load_config_from_env()

    w3 = chain_module.get_web3(config)
    if w3 is None:
        # Fall back to simulation if chain not available
        print("  [WARN] Chain not available, falling back to simulation")
        return _execute_simulated(to_address, amount, "ETH", "Base Sepolia")

    acct = w3.eth.account.from_key(config.private_key)

    tx = {
        "to": w3.to_checksum_address(to_address),
        "value": w3.to_wei(amount, "ether"),
        "gas": 21000,
        "gasPrice": w3.eth.gas_price,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": config.chain_id,
    }

    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return PaymentReceipt({
        "receipt_id": tx_hash.hex(),
        "tx_hash": tx_hash.hex(),
        "from": acct.address,
        "to": to_address,
        "amount_eth": str(amount),
        "token": "ETH",
        "network": f"Base Sepolia (chain_id={config.chain_id})",
        "block_number": receipt["blockNumber"],
        "gas_used": receipt["gasUsed"],
        "status": "completed" if receipt["status"] else "failed",
        "mode": "real",
    })


def _execute_simulated(
    to_address: str,
    amount: float,
    token: str,
    network: str,
) -> PaymentReceipt:
    """Simulation: return mock receipt (existing behavior)."""
    import hashlib
    import time

    mock_hash = hashlib.sha256(
        f"{to_address}{amount}{time.time()}".encode()
    ).hexdigest()

    return PaymentReceipt({
        "receipt_id": f"sim-{int(time.time())}-{mock_hash[:8]}",
        "amount": str(amount),
        "token": token,
        "network": network,
        "to": to_address,
        "mode": "simulation",
    })
