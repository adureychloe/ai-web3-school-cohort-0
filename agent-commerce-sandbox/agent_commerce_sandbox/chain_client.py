"""
Chain client — web3.py wrapper for ServiceRegistry contract on Sepolia.

Reads ABI and deployment info from contracts/, connects to Sepolia,
and provides methods for service discovery and delivery proof recording.
"""

import json
import os
import time
from pathlib import Path


# ── Paths ─────────────────────────────────────────────────────

_SANDBOX_DIR = Path(__file__).resolve().parent.parent
_CONTRACTS_DIR = _SANDBOX_DIR / "contracts"
_ENV_PATH = _SANDBOX_DIR / ".env"


# ── Helpers ───────────────────────────────────────────────────

def _read_pk_from_env() -> str:
    """Read TEST_PRIVATE_KEY from .env without python-dotenv."""
    if not _ENV_PATH.exists():
        return ""
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("TEST_PRIVATE_KEY="):
                val = line.split("=", 1)[1].strip()
                return val
    return ""


def _connect_web3() -> tuple:
    """Connect to Sepolia, return (w3, chain_id)."""
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(
        "https://ethereum-sepolia-rpc.publicnode.com",
        request_kwargs={"timeout": 30}
    ))
    chain_id = w3.eth.chain_id
    print(f"  [Chain] Connected to Sepolia (chain_id={chain_id})")
    return w3, chain_id


def _load_contract(w3):
    """Load ServiceRegistry contract from deployment info."""
    deployed_path = _CONTRACTS_DIR / "deployed.json"
    abi_path = _CONTRACTS_DIR / "ServiceRegistry.abi.json"

    if not deployed_path.exists():
        raise FileNotFoundError(f"deployed.json not found at {deployed_path}")
    if not abi_path.exists():
        raise FileNotFoundError(f"ABI not found at {abi_path}")

    with open(deployed_path) as f:
        deploy_info = json.load(f)
    with open(abi_path) as f:
        abi = json.load(f)

    addr = deploy_info["contract_address"]
    contract = w3.eth.contract(address=addr, abi=abi)
    print(f"  [Chain] Loaded ServiceRegistry at {addr}")
    return contract, addr


# ── Public API ────────────────────────────────────────────────

class ChainClient:
    """Web3 client for the ServiceRegistry contract on Sepolia."""

    def __init__(self):
        self.w3, self.chain_id = _connect_web3()
        self.contract, self.contract_addr = _load_contract(self.w3)
        self._pk = _read_pk_from_env()
        self._acct = None
        if self._pk:
            pk = self._pk
            if pk.startswith("0x"):
                pk = pk[2:]
            self._acct = self.w3.eth.account.from_key(pk)

    # ── Read Methods ──────────────────────────────────────

    def list_services(self) -> list:
        """Get all active services from the contract.

        Returns:
            List of dicts with keys: id, name, description, paymentAddress,
            priceWei, tokenId, chainId, active, provider
        """
        raw = self.contract.functions.listServices().call()
        services = []
        for s in raw:
            services.append({
                "id": s[0],
                "name": s[1],
                "description": s[2],
                "paymentAddress": s[3],
                "priceWei": s[4],
                "tokenId": s[5],
                "chainId": s[6],
                "active": s[7],
                "provider": s[8],
            })
        return services

    def get_service(self, service_id: int) -> dict:
        """Get a single service by ID."""
        raw = self.contract.functions.getService(service_id).call()
        return {
            "id": raw[0],
            "name": raw[1],
            "description": raw[2],
            "paymentAddress": raw[3],
            "priceWei": raw[4],
            "tokenId": raw[5],
            "chainId": raw[6],
            "active": raw[7],
            "provider": raw[8],
        }

    def get_service_count(self) -> int:
        """Get total registered services (including inactive)."""
        return self.contract.functions.getServiceCount().call()

    def get_proofs(self, offset=0, limit=10) -> list:
        """Get delivery proofs from the contract."""
        raw = self.contract.functions.getProofs(offset, limit).call()
        proofs = []
        for p in raw:
            proofs.append({
                "serviceId": p[0],
                "txHash": p[1],
                "summary": p[2],
                "timestamp": p[3],
                "agent": p[4],
            })
        return proofs

    def get_proof_count(self) -> int:
        """Get total number of delivery proofs."""
        return self.contract.functions.getProofCount().call()

    # ── Write Methods ─────────────────────────────────────

    def record_delivery(self, service_id: int, tx_hash: str, summary: str) -> dict:
        """Record a delivery proof on-chain.

        Signs and sends a transaction via the deployer EOA.

        Args:
            service_id: Service ID from the contract
            tx_hash: CAW transfer transaction hash
            summary: Brief description of delivery

        Returns:
            Dict with tx_hash, block number, and status
        """
        if not self._acct:
            raise RuntimeError("No TEST_PRIVATE_KEY in .env — cannot record delivery")

        gas_price = self.w3.eth.gas_price
        nonce = self.w3.eth.get_transaction_count(self._acct.address)

        txn = self.contract.functions.recordDelivery(
            service_id, tx_hash, summary
        ).build_transaction({
            "from": self._acct.address,
            "nonce": nonce,
            "gas": 200000,
            "gasPrice": gas_price,
            "chainId": self.chain_id,
        })

        signed = self._acct.sign_transaction(txn)
        raw_tx = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hex = raw_tx.hex()

        print(f"  [Chain] Recording delivery tx={tx_hex[:20]}... waiting...")
        receipt = self.w3.eth.wait_for_transaction_receipt(raw_tx, timeout=120)

        result = {
            "tx_hash": tx_hex,
            "block": receipt["blockNumber"],
            "status": receipt["status"],
        }
        if receipt["status"] == 1:
            print(f"  [Chain] ✅ Delivery recorded (block={receipt['blockNumber']})")
        else:
            print(f"  [Chain] ❌ Delivery recording failed")
        return result

    def format_service(self, s: dict) -> str:
        """Format a service dict as a readable string."""
        from web3 import Web3
        price_eth = Web3.from_wei(s["priceWei"], "ether")
        return (
            f"  [{s['id']}] {s['name']}\n"
            f"        {s['description']}\n"
            f"        Price: {price_eth} {s['tokenId']} on {s['chainId']}\n"
            f"        Pay to: {s['paymentAddress']}"
        )
