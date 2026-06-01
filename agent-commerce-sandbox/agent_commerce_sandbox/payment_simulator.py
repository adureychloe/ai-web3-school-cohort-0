"""Payment simulator: mock x402 / EIP-3009 payments."""

import hashlib
import json
import time
from typing import Optional


class PaymentReceipt:
    """Simulated payment receipt."""

    def __init__(
        self,
        service_id: str,
        amount: str,
        token: str,
        network: str,
        payment_method: str = "x402_mock",
    ):
        self.receipt_id = f"receipt-{int(time.time())}-{hashlib.md5(service_id.encode()).hexdigest()[:8]}"
        self.service_id = service_id
        self.amount = amount
        self.token = token
        self.network = network
        self.payment_method = payment_method
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "service_id": self.service_id,
            "amount": self.amount,
            "token": self.token,
            "network": self.network,
            "payment_method": self.payment_method,
            "timestamp": self.timestamp,
            "status": "completed",
        }


def simulate_payment(
    service_id: str,
    amount: str,
    token: str,
    network: str,
    payment_method: str = "x402_mock",
) -> PaymentReceipt:
    """
    Simulate a payment via x402-like flow.

    In production this would call:
      - Cobo CAW SDK / x402 Payment recipe
      - transferWithAuthorization (EIP-3009)
      - Or smart account execute on user's behalf

    Currently returns a mock receipt.
    """
    receipt = PaymentReceipt(
        service_id=service_id,
        amount=amount,
        token=token,
        network=network,
        payment_method=payment_method,
    )
    return receipt
