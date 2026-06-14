"""Tests for the Agent Console UI wiring in web/index.html."""

from __future__ import annotations

from pathlib import Path
import re


HTML = Path(__file__).resolve().parents[1] / "web" / "index.html"


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def test_agent_console_ui_exists_and_calls_buyer_agent_endpoint() -> None:
    html = _html()

    for marker in (
        'id="agentConsoleTab"',
        'id="agentConsoleView"',
        'id="agentConsoleRequest"',
        'id="agentConsoleBudget"',
        'id="agentConsoleAutoPay"',
        'id="runBuyerAgentBtn"',
        'id="agentConsoleResult"',
        "Agent Console",
        "Buyer Agent",
        "Seller Agent",
        "/api/agent/buyer/procure",
    ):
        assert marker in html

    assert re.search(r"function\s+runBuyerAgent\s*\(", html)
    assert re.search(
        r'el\("runBuyerAgentBtn"\)\.addEventListener\("click",\s*runBuyerAgent\)',
        html,
    )
