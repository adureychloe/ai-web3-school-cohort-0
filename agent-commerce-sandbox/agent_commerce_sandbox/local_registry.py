"""Local Service Registry — off-chain provider self-registration.

Since ServiceRegistry.sol can only be updated by the contract owner,
this provides an off-chain registry where any agent can register
as a service provider. Compatible with the on-chain format.

Service IDs start at 100 to distinguish from on-chain services (1-99).
"""

import json
import os
import time
from pathlib import Path

REGISTRY_FILE = os.path.join(os.path.dirname(__file__), "..", "services_registry.json")
_next_id = [100]  # mutable counter


class LocalServiceRegistry:
    """Off-chain service registry stored as JSON file."""

    def __init__(self, path: str = REGISTRY_FILE):
        self.path = path
        self._services: dict[int, dict] = {}
        self._load()

    def _load(self):
        """Load services from JSON file."""
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    data = json.load(f)
                self._services = {int(k): v for k, v in data.get("services", {}).items()}
                # Update next_id
                ids = list(self._services.keys())
                if ids:
                    _next_id[0] = max(ids) + 1
            except (json.JSONDecodeError, IOError):
                self._services = {}

    def _save(self):
        """Persist services to JSON file."""
        data = {"services": {str(k): v for k, v in self._services.items()}}
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def register(
        self,
        provider: str,
        name: str,
        description: str,
        price_seth: str,
        endpoint: str = "",
        token_id: str = "SETH",
        chain_id: str = "SETH",
        tags: list | None = None,
        protocol: str = "x402",
    ) -> dict:
        """Register a new service. Returns the service dict."""
        service_id = _next_id[0]
        _next_id[0] += 1

        service = {
            "id": service_id,
            "name": name,
            "description": description,
            "price_seth": price_seth,
            "token_id": token_id,
            "chain_id": chain_id,
            "provider": provider,
            "endpoint": endpoint,
            "protocol": protocol,
            "tags": tags or [],
            "active": True,
            "registered_at": time.time(),
        }
        self._services[service_id] = service
        self._save()
        return service

    def unregister(self, service_id: int, provider: str) -> bool:
        """Deactivate a service. Only the provider can unregister."""
        svc = self._services.get(service_id)
        if not svc:
            return False
        if svc.get("provider", "").lower() != provider.lower():
            return False
        svc["active"] = False
        self._save()
        return True

    def update(
        self,
        service_id: int,
        provider: str,
        **kwargs,
    ) -> dict | None:
        """Update a service's metadata. Only the provider can update."""
        svc = self._services.get(service_id)
        if not svc:
            return None
        if svc.get("provider", "").lower() != provider.lower():
            return None
        allowed = {"name", "description", "price_seth", "endpoint", "tags", "protocol"}
        for k, v in kwargs.items():
            if k in allowed and v is not None:
                svc[k] = v
        self._save()
        return svc

    def list_services(self, active_only: bool = True) -> list[dict]:
        """List all services, optionally filtering by active."""
        services = list(self._services.values())
        if active_only:
            services = [s for s in services if s.get("active", True)]
        return sorted(services, key=lambda s: s["id"])

    def get_service(self, service_id: int) -> dict | None:
        """Get a single service by ID."""
        return self._services.get(service_id)

    def query_by_tags(self, tags: list[str]) -> list[dict]:
        """Find services matching any of the given tags."""
        tag_set = set(t.lower() for t in tags)
        results = []
        for s in self._services.values():
            if not s.get("active", True):
                continue
            svc_tags = set(t.lower() for t in s.get("tags", []))
            if tag_set & svc_tags:
                results.append(s)
        return results
