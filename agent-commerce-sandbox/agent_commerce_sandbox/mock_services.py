"""Mock services: predefined services and service discovery."""

import json
import os
from typing import Optional

_SERVICES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "services.json")


def load_services() -> dict:
    """Load the services list from services.json."""
    with open(_SERVICES_PATH) as f:
        return json.load(f)


def discover_services(keyword: str = "") -> list:
    """Discover available services, optionally filtered by keyword."""
    data = load_services()
    services = data["services"]
    if keyword:
        kw = keyword.lower()
        services = [s for s in services if kw in s["name"].lower() or kw in s["description"].lower()]
    return services


def get_service(service_id: str) -> Optional[dict]:
    """Lookup a single service by ID."""
    data = load_services()
    for s in data["services"]:
        if s["id"] == service_id:
            return s
    return None


def format_quote(service: dict) -> dict:
    """Generate a quote from a service definition."""
    return {
        "service_id": service["id"],
        "service_name": service["name"],
        "amount": service["price"]["amount"],
        "token": service["price"]["token"],
        "network": service["price"]["network"],
        "delivery_type": service["delivery_type"],
        "estimated_delivery_time": service["estimated_delivery_time"],
        "allowlisted": service["allowlisted"],
    }
