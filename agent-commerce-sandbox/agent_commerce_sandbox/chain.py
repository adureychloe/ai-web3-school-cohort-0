"""
Chain connection layer for Agent Commerce Sandbox.

Supports two modes:
  - REAL: connects to Base Sepolia testnet via web3.py
  - SIMULATION: returns mock data, no chain needed (default)

Switching logic:
  - If RPC_URL + TEST_PRIVATE_KEY are set in .env -> REAL mode
  - Otherwise -> SIMULATION mode (current behavior unchanged)
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ── Config ──────────────────────────────────────────────────────────

@dataclass
class ChainConfig:
    rpc_url: str
    private_key: str
    chain_id: int
    receipt_registry: Optional[str] = None

    @property
    def is_real(self) -> bool:
        return bool(self.rpc_url and self.private_key)


def load_config_from_env(env_path: str = ".env") -> ChainConfig:
    """Load chain config from .env file. Missing file = simulation mode."""
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except Exception:
        pass

    rpc = os.environ.get("RPC_URL", "")
    pk = os.environ.get("TEST_PRIVATE_KEY", "")
    chain_id = int(os.environ.get("CHAIN_ID", "84532"))
    registry = os.environ.get("RECEIPT_REGISTRY_ADDRESS", "") or None

    return ChainConfig(
        rpc_url=rpc,
        private_key=pk,
        chain_id=chain_id,
        receipt_registry=registry,
    )


# ── Web3 Connection ─────────────────────────────────────────────────

_web3_instance = None


def get_web3(config: Optional[ChainConfig] = None) -> Optional[object]:
    """
    Get a web3.py instance if in REAL mode.
    Returns None in SIMULATION mode.
    """
    global _web3_instance
    if _web3_instance is not None:
        return _web3_instance

    if config is None:
        config = load_config_from_env()

    if not config.is_real:
        return None

    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(config.rpc_url))
    if not w3.is_connected():
        logger.warning(f"Cannot connect to RPC: {config.rpc_url}")
        return None

    _web3_instance = w3
    return w3


def get_account(config: Optional[ChainConfig] = None) -> Optional[str]:
    """Return the account address derived from the private key."""
    w3 = get_web3(config)
    if w3 is None:
        return None
    if config is None:
        config = load_config_from_env()
    acct = w3.eth.account.from_key(config.private_key)
    return acct.address


# ── Balance Checks ──────────────────────────────────────────────────

def check_balance(config: Optional[ChainConfig] = None) -> Optional[dict]:
    """Check ETH balance on the connected network."""
    w3 = get_web3(config)
    if w3 is None:
        return None

    if config is None:
        config = load_config_from_env()
    acct = w3.eth.account.from_key(config.private_key)
    bal_wei = w3.eth.get_balance(acct.address)
    bal_eth = w3.from_wei(bal_wei, "ether")
    return {
        "address": acct.address,
        "balance_wei": str(bal_wei),
        "balance_eth": str(bal_eth),
        "network": f"chain_id={config.chain_id}",
        "mode": "real",
    }


# ── Real Transfer ───────────────────────────────────────────────────

def send_eth(
    to_address: str,
    amount_eth: float,
    config: Optional[ChainConfig] = None,
) -> dict:
    """
    Send test ETH on Base Sepolia.
    Returns transaction receipt dict.
    """
    w3 = get_web3(config)
    if w3 is None:
        raise RuntimeError("Cannot send: not connected to a network")

    if config is None:
        config = load_config_from_env()
    acct = w3.eth.account.from_key(config.private_key)

    tx = {
        "to": w3.to_checksum_address(to_address),
        "value": w3.to_wei(amount_eth, "ether"),
        "gas": 21000,
        "gasPrice": w3.eth.gas_price,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": config.chain_id,
    }

    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return {
        "tx_hash": tx_hash.hex(),
        "from": acct.address,
        "to": to_address,
        "amount_eth": str(amount_eth),
        "block_number": receipt["blockNumber"],
        "gas_used": receipt["gasUsed"],
        "status": receipt["status"],
        "mode": "real",
    }


# ── Simulation helpers (for compatibility) ──────────────────────────

def simulate_send_eth(to_address: str, amount_eth: float) -> dict:
    """Return a mock receipt (same shape as real send_eth)."""
    import hashlib
    import time
    mock_hash = hashlib.sha256(
        f"{to_address}{amount_eth}{time.time()}".encode()
    ).hexdigest()
    return {
        "tx_hash": f"0x{mock_hash[:64]}",
        "from": "0xSIMULATION_ADDRESS",
        "to": to_address,
        "amount_eth": str(amount_eth),
        "block_number": 0,
        "gas_used": 21000,
        "status": 1,
        "mode": "simulation",
    }
