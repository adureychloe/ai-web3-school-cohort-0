#!/usr/bin/env python3
"""Register two additional demo x402 services in ServiceRegistryV2.

Uses the existing ChainClientV2 signer (TEST_PRIVATE_KEY from .env). It skips
services whose names already exist so repeated demo setup is safe.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web3 import Web3

from agent_commerce_sandbox.caw_client import WALLET_SETH_ADDR
from agent_commerce_sandbox.chain_client_v2 import ChainClientV2


DEMO_SERVICES = [
    {
        "name": "Wallet Risk Snapshot",
        "description": "Summarizes wallet exposure, recent activity, and simple risk flags for a Web3 address.",
        "price_seth": "0.00005",
    },
    {
        "name": "DeFi Route Brief",
        "description": "Produces a concise DeFi swap/route brief with liquidity notes and execution considerations.",
        "price_seth": "0.00005",
    },
]


def _endpoint() -> str:
    endpoint = (os.environ.get("X402_SELF_URL") or os.environ.get("X402_PUBLIC_URL") or "").strip().rstrip("/")
    if not endpoint:
        endpoint = "http://127.0.0.1:8888"
    if endpoint.endswith("/request"):
        endpoint = endpoint[: -len("/request")].rstrip("/")
    return endpoint


def main() -> int:
    chain = ChainClientV2()
    endpoint_uri = _endpoint()
    payment_addr = Web3.to_checksum_address(os.environ.get("DEMO_SELLER_ADDRESS", WALLET_SETH_ADDR))

    existing = {s.get("name", "").lower() for s in chain.list_services(0, 200)}
    created = 0
    for svc in DEMO_SERVICES:
        if svc["name"].lower() in existing:
            print(f"skip existing: {svc['name']}")
            continue
        result = chain.register_service(
            name=svc["name"],
            desc=svc["description"],
            payment_addr=payment_addr,
            price_wei=Web3.to_wei(float(svc["price_seth"]), "ether"),
            token_id="SETH",
            chain_id="SETH",
            endpoint_uri=endpoint_uri,
            protocol="x402",
        )
        if result.get("status") != 1:
            raise RuntimeError(f"registration failed for {svc['name']}: {result.get('tx_hash')}")
        created += 1
        print(f"registered #{result.get('service_id')}: {svc['name']} tx={result.get('tx_hash')}")

    print(f"done: {created} created, endpoint={endpoint_uri}, payment={payment_addr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
