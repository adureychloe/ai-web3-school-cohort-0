"""
Chain client V2 — web3.py wrapper for ServiceRegistryV2 contract on Sepolia.

Reads ABI and deployment info from contracts/deployed_v2.json, connects to
Sepolia, and provides methods for service discovery, registration, updates,
and delivery proof recording.

The V2 Service struct has 11 fields (accessed by index):
    0:id 1:name 2:description 3:paymentAddress 4:priceWei 5:tokenId
    6:chainId 7:active 8:provider 9:endpointURI 10:protocol
"""

import json
import os
import sys
from pathlib import Path


def _log(msg: str):
    """Safe log that doesn't crash in asyncio thread contexts."""
    try:
        print(msg, file=sys.stderr, flush=True)
    except (BrokenPipeError, OSError, ValueError):
        pass


# ── Paths ─────────────────────────────────────────────────────

_SANDBOX_DIR = Path(__file__).resolve().parent.parent
_CONTRACTS_DIR = _SANDBOX_DIR / "contracts"
_ENV_PATH = _SANDBOX_DIR / ".env"

_DEFAULT_RPC = "https://ethereum-sepolia-rpc.publicnode.com"


# ── Helpers ───────────────────────────────────────────────────

def _read_pk_from_env() -> str:
    """Read TEST_PRIVATE_KEY from .env without python-dotenv."""
    if not _ENV_PATH.exists():
        return ""
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("TEST_PRIVATE_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def _load_deploy_info() -> dict:
    """Load V2 deployment info from contracts/deployed_v2.json."""
    deployed_path = _CONTRACTS_DIR / "deployed_v2.json"
    if not deployed_path.exists():
        raise FileNotFoundError(f"deployed_v2.json not found at {deployed_path}")
    with open(deployed_path) as f:
        return json.load(f)


def _connect_web3(rpc_url: str) -> tuple:
    """Connect to Sepolia, return (w3, chain_id)."""
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
    chain_id = w3.eth.chain_id
    _log(f"  [ChainV2] Connected to Sepolia (chain_id={chain_id})")
    return w3, chain_id


def _load_contract(w3, addr):
    """Load ServiceRegistryV2 contract from the V2 ABI."""
    abi_path = _CONTRACTS_DIR / "ServiceRegistryV2.abi.json"
    if not abi_path.exists():
        raise FileNotFoundError(f"V2 ABI not found at {abi_path}")
    with open(abi_path) as f:
        abi = json.load(f)
    contract = w3.eth.contract(address=addr, abi=abi)
    _log(f"  [ChainV2] Loaded ServiceRegistryV2 at {addr}")
    return contract


def _service_from_tuple(s) -> dict:
    """Convert an 11-field Service tuple into a dict."""
    return {
        "id": s[0],
        "name": s[1],
        "description": s[2],
        "paymentAddress": s[3],
        "priceWei": s[4],
        "tokenId": s[5],
        "chainId": s[6],
        "active": s[7],
        "provider": s[8],
        "endpointURI": s[9],
        "protocol": s[10],
    }


# ── Public API ────────────────────────────────────────────────

class ChainClientV2:
    """Web3 client for the ServiceRegistryV2 contract on Sepolia."""

    def __init__(self):
        deploy_info = _load_deploy_info()
        rpc_url = deploy_info.get("rpc_url", _DEFAULT_RPC)
        self.contract_addr = deploy_info["contract_address"]
        self.w3, self.chain_id = _connect_web3(rpc_url)
        self.contract = _load_contract(self.w3, self.contract_addr)
        self._pk = _read_pk_from_env()
        self._acct = None
        if self._pk:
            pk = self._pk[2:] if self._pk.startswith("0x") else self._pk
            self._acct = self.w3.eth.account.from_key(pk)

    # ── Read Methods ──────────────────────────────────────

    def list_services(self, offset: int = 0, limit: int = 100) -> list:
        """Get a paginated list of services from the contract.

        Returns:
            List of dicts with keys: id, name, description, paymentAddress,
            priceWei, tokenId, chainId, active, provider, endpointURI, protocol
        """
        raw = self.contract.functions.listServices(offset, limit).call()
        return [_service_from_tuple(s) for s in raw]

    def get_service(self, service_id: int) -> dict:
        """Get a single service by ID."""
        raw = self.contract.functions.getService(service_id).call()
        return _service_from_tuple(raw)

    def get_service_count(self) -> int:
        """Get total registered services (including inactive)."""
        return self.contract.functions.getServiceCount().call()

    def get_active_service_count(self) -> int:
        """Get the number of active services."""
        return self.contract.functions.getActiveServiceCount().call()

    def get_services_by_provider(self, provider_addr: str) -> list:
        """Get all services registered by a provider."""
        raw = self.contract.functions.getServicesByProvider(provider_addr).call()
        return [_service_from_tuple(s) for s in raw]

    def get_active_services_by_provider(self, provider_addr: str) -> list:
        """Get the active services registered by a provider."""
        raw = self.contract.functions.getActiveServicesByProvider(provider_addr).call()
        return [_service_from_tuple(s) for s in raw]

    def get_proofs(self, offset: int = 0, limit: int = 10) -> list:
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

    def verify_tx_onchain(self, tx_hash: str, expected_to: str, expected_value_wei: int) -> bool:
        """Verify an on-chain transfer by checking the transaction receipt."""
        if not tx_hash or not tx_hash.startswith("0x"):
            return False
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            if receipt is None or receipt.get("status") != 1:
                return False
            if tx.get("to", "").lower() != expected_to.lower():
                return False
            if tx.get("value", 0) < expected_value_wei:
                return False
            return True
        except Exception:
            return False

    # ── Write Methods ─────────────────────────────────────

    def _send_tx(self, fn, gas: int = 400000) -> dict:
        """Build, sign, send a contract function call, and wait for receipt."""
        if not self._acct:
            raise RuntimeError("No TEST_PRIVATE_KEY in .env — cannot sign transaction")

        gas_price = self.w3.eth.gas_price
        nonce = self.w3.eth.get_transaction_count(self._acct.address)
        tx_gas = int(gas)
        try:
            estimated_gas = int(fn.estimate_gas({"from": self._acct.address}))
            # Avoid over-reserving ETH on Sepolia by using a measured limit with
            # headroom instead of the broad per-method fallback.
            tx_gas = min(tx_gas, int(estimated_gas * 1.25) + 10_000)
        except Exception:
            pass

        txn = fn.build_transaction({
            "from": self._acct.address,
            "nonce": nonce,
            "gas": tx_gas,
            "gasPrice": gas_price,
            "chainId": self.chain_id,
        })

        signed = self._acct.sign_transaction(txn)
        raw_tx = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hex = raw_tx.hex()
        if not tx_hex.startswith("0x"):
            tx_hex = "0x" + tx_hex

        _log(f"  [ChainV2] tx={tx_hex[:20]}... waiting for receipt...")
        receipt = self.w3.eth.wait_for_transaction_receipt(raw_tx, timeout=180)

        result = {
            "tx_hash": tx_hex,
            "block": receipt["blockNumber"],
            "status": receipt["status"],
        }
        if receipt["status"] == 1:
            _log(f"  [ChainV2] tx confirmed (block={receipt['blockNumber']})")
        else:
            _log(f"  [ChainV2] tx FAILED (block={receipt['blockNumber']})")
        return result, receipt

    def register_service(
        self,
        name: str,
        desc: str,
        payment_addr: str,
        price_wei: int,
        token_id: str,
        chain_id: str,
        endpoint_uri: str,
        protocol: str = "x402",
    ) -> dict:
        """Register a new service on-chain. Signs register() via the deployer EOA.

        Returns:
            Dict with tx_hash, block, status, and the new service_id (if found).
        """
        fn = self.contract.functions.register(
            name, desc, self.w3.to_checksum_address(payment_addr), int(price_wei),
            token_id, chain_id, endpoint_uri, protocol,
        )
        result, receipt = self._send_tx(fn, gas=600000)

        # Try to recover the new service id from the ServiceRegistered event
        service_id = None
        try:
            logs = self.contract.events.ServiceRegistered().process_receipt(receipt)
            if logs:
                service_id = logs[0]["args"]["id"]
        except Exception:
            pass
        if service_id is None and result["status"] == 1:
            # Fallback: latest service is the highest id (count - 1 in V2 indexing)
            try:
                service_id = self.get_service_count() - 1
            except Exception:
                pass
        result["service_id"] = service_id
        return result

    def update_service(
        self,
        service_id: int,
        name: str,
        desc: str,
        price_wei: int,
        payment_addr: str,
        endpoint_uri: str,
    ) -> dict:
        """Update an existing service's metadata on-chain."""
        fn = self.contract.functions.updateService(
            int(service_id), name, desc, int(price_wei), payment_addr, endpoint_uri,
        )
        result, _ = self._send_tx(fn)
        return result

    def deactivate_service(self, service_id: int) -> dict:
        """Deactivate a service on-chain."""
        fn = self.contract.functions.deactivate(int(service_id))
        result, _ = self._send_tx(fn, gas=200000)
        return result

    def remove_service(self, service_id: int) -> dict:
        """Soft-remove a service by using ServiceRegistryV2.deactivate().

        ServiceRegistryV2 does not expose a hard-delete primitive. Deactivate is
        the on-chain lifecycle operation that removes a service from buyer
        discovery while preserving historical registry/proof data.
        """
        return self.deactivate_service(service_id)

    def reactivate_service(self, service_id: int) -> dict:
        """Reactivate a previously deactivated service on-chain."""
        fn = self.contract.functions.reactivate(int(service_id))
        result, _ = self._send_tx(fn, gas=200000)
        return result

    def record_delivery(self, service_id: int, tx_hash: str, summary: str) -> dict:
        """Record a delivery proof on-chain."""
        fn = self.contract.functions.recordDelivery(int(service_id), tx_hash, summary)
        result, _ = self._send_tx(fn, gas=300000)
        return result

    def format_service(self, s: dict) -> str:
        """Format a service dict as a readable string."""
        from web3 import Web3
        price_eth = Web3.from_wei(s["priceWei"], "ether")
        return (
            f"  [{s['id']}] {s['name']} ({'active' if s['active'] else 'inactive'})\n"
            f"        {s['description']}\n"
            f"        Price: {price_eth} {s['tokenId']} on {s['chainId']}\n"
            f"        Pay to: {s['paymentAddress']}\n"
            f"        Endpoint: {s['endpointURI']} [{s['protocol']}]"
        )
