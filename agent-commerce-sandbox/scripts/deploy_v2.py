#!/usr/bin/env python3
"""
Deploy ServiceRegistryV2.sol to Sepolia.

Usage:
    python scripts/deploy_v2.py [--private-key 0x...]

Reads TEST_PRIVATE_KEY from ../.env if not provided via --private-key.
Saves deployment info to ../contracts/deployed_v2.json.
"""

import json
import os
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
CONTRACTS_DIR = PROJECT_DIR / "contracts"
ENV_PATH = PROJECT_DIR / ".env"

# ── Read private key ─────────────────────────────────────────

def _read_pk_from_env() -> str:
    if not ENV_PATH.exists():
        return ""
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("TEST_PRIVATE_KEY="):
                return line.split("=", 1)[1].strip()
    return ""

# ── Main ──────────────────────────────────────────────────────

def main():
    # Parse CLI args
    pk = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--private-key" and i + 1 < len(sys.argv) - 1:
            pk = sys.argv[i + 2]

    if not pk:
        pk = _read_pk_from_env()

    if not pk:
        print("❌ No private key found. Set TEST_PRIVATE_KEY in .env or pass --private-key")
        sys.exit(1)

    if pk.startswith("0x"):
        pk = pk[2:]

    # ── Compile ──────────────────────────────────────────────
    print("🔧 Compiling ServiceRegistryV2.sol...")
    import solcx
    # Install v0.8.20 if not already installed
    solcx.install_solc("0.8.20")
    solcx.set_solc_version("0.8.20")

    sol_path = str(CONTRACTS_DIR / "ServiceRegistryV2.sol")
    compiled = solcx.compile_files(
        [sol_path],
        output_values=["abi", "bin"],
        optimize=True,
        optimize_runs=200,
        via_ir=True,  # Stack too deep fix
    )

    # Key format: relative_path:ContractName
    contract_key = "contracts/ServiceRegistryV2.sol:ServiceRegistryV2"
    contract_data = compiled[contract_key]
    abi = contract_data["abi"]
    bytecode = contract_data["bin"]

    # Save ABI + bytecode
    with open(CONTRACTS_DIR / "ServiceRegistryV2.abi.json", "w") as f:
        json.dump(abi, f, indent=2)
    with open(CONTRACTS_DIR / "ServiceRegistryV2.bin", "w") as f:
        f.write(bytecode)

    print(f"  ✅ Compiled. ABI saved, bytecode size = {len(bytecode)} bytes")

    # ── Deploy ───────────────────────────────────────────────
    print("🔗 Connecting to Sepolia...")
    from web3 import Web3

    rpc_url = "https://ethereum-sepolia-rpc.publicnode.com"
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 60}))
    chain_id = w3.eth.chain_id
    print(f"  Chain ID: {chain_id}")

    acct = w3.eth.account.from_key(pk)
    deployer = acct.address
    print(f"  Deployer: {deployer}")

    balance = w3.eth.get_balance(deployer)
    print(f"  Balance:  {w3.from_wei(balance, 'ether')} ETH")

    if balance < 1000000000000000:  # < 0.001 ETH
        print("⚠️  Low balance — deployment may fail")

    # Build deployment transaction
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(deployer)
    gas_price = w3.eth.gas_price

    print(f"  Nonce:    {nonce}")
    print(f"  Gas price: {w3.from_wei(gas_price, 'gwei'):.2f} gwei")
    print()

    construct_txn = Contract.constructor().build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gas": 5000000,
        "gasPrice": gas_price,
        "chainId": chain_id,
    })

    print("📤 Sending deployment transaction...")
    signed_txn = acct.sign_transaction(construct_txn)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print(f"  Tx hash: 0x{tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    contract_addr = receipt["contractAddress"]

    print(f"  ✅ Deployed! Contract: {contract_addr}")
    print(f"     Block:   {receipt['blockNumber']}")
    print(f"     Gas used: {receipt['gasUsed']}")

    # ── Save deployment info ─────────────────────────────────
    deploy_info = {
        "chain": "Sepolia",
        "chain_id": chain_id,
        "contract_address": contract_addr,
        "deploy_tx_hash": tx_hash.hex(),
        "block": receipt["blockNumber"],
        "deployer": deployer,
        "rpc_url": rpc_url,
    }

    with open(CONTRACTS_DIR / "deployed_v2.json", "w") as f:
        json.dump(deploy_info, f, indent=2)

    print(f"\n  📄 Deployment info saved to contracts/deployed_v2.json")
    print(f"  Contract: {contract_addr}")
    print()

    # ── Quick verification ──────────────────────────────────
    print("🔍 Verifying deployment...")
    deployed = w3.eth.contract(address=contract_addr, abi=abi)
    count = deployed.functions.getServiceCount().call()
    owner = deployed.functions.owner().call()
    print(f"  Owner: {owner}")
    print(f"  Total services: {count}")
    print(f"  ✅ V2 ready!")


if __name__ == "__main__":
    main()
