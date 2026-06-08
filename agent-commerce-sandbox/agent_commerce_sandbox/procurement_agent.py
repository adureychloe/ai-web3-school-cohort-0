"""Procurement Agent — natural language service procurement.

Matches user requests to on-chain services, shows ranked matches with balance,
lets user pick, then runs the full payment flow with progress reporting.
"""

import json
import re
import subprocess
from web3 import Web3

from .chain_client import ChainClient
from .engine import pay_for_service

# SETH price estimate for USD display
SETH_PRICE_USD = 3000

# Chinese keyword tags to bridge language gap between user query and English
# service descriptions.  Each service ID maps to Chinese keyword tags.
_CN_TAGS = {
    1: {"研究", "笔记", "报告", "项目", "web3", "行业", "趋势", "文章", "写", "文档", "总结"},
    2: {"数据", "链上", "查询", "地址", "余额", "价格", "交易", "历史", "状态", "监控", "获取"},
    3: {"深度", "分析", "市场", "预测", "风控", "评估", "决策", "洞察", "策略", "投资", "行情"},
}


# ── Helpers ─────────────────────────────────────────────────


def _tokenize(text: str) -> set:
    """Split text into keyword tokens (Chinese chars + English words)."""
    chinese = re.findall(r"[\u4e00-\u9fff]+", text)
    english = re.findall(r"[a-zA-Z]{3,}", text)

    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "you", "not",
        "are", "was", "had", "has", "but", "its", "all", "can", "will",
        "xxx", "help", "need", "would", "could", "also", "get", "make",
        "want", "like", "just", "please",
    }

    tokens = set()
    for c in chinese:
        for char in c:
            tokens.add(char)
    for w in english:
        wl = w.lower()
        if wl not in stop_words:
            tokens.add(wl)
    return tokens


def match_and_rank(request: str, services: list) -> list:
    """Score and rank services by keyword overlap. Returns [(score, svc), ...]."""
    req_tokens = _tokenize(request)
    if not req_tokens:
        return [(0, s) for s in services]

    scored = []
    for s in services:
        candidate_text = f"{s['name']} {s['description']}"
        cand_tokens = _tokenize(candidate_text)

        # Score by English keyword overlap
        overlap = len(req_tokens & cand_tokens) if cand_tokens else 0

        # Score by Chinese multi-char tag substrings in request
        tags = _CN_TAGS.get(s["id"], set())
        for tag in tags:
            if tag in request:
                overlap += 1

        scored.append((overlap, s))

    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return scored


def get_balance() -> dict:
    """Get SETH balance via caw CLI. Returns {'amount': '0', 'address': ''}."""
    try:
        result = subprocess.run(
            ["caw", "wallet", "balance", "--timeout", "15"],
            capture_output=True, text=True, timeout=25,
        )
        if result.returncode != 0:
            return {"amount": "unknown", "address": ""}
        data = json.loads(result.stdout)
        for entry in data.get("result", []):
            if entry.get("chain_id") == "SETH" and entry.get("token_id", "SETH") == "SETH":
                return {
                    "amount": entry.get("amount", "0"),
                    "address": entry.get("address", ""),
                }
        return {"amount": "unknown", "address": ""}
    except Exception:
        return {"amount": "unknown", "address": ""}


def format_price(price_wei: int) -> tuple:
    """Convert wei to (eth_str, usd_str)."""
    eth = Web3.from_wei(price_wei, "ether")
    usd = float(eth) * SETH_PRICE_USD
    return f"{float(eth):.5f}", f"${usd:.2f}"


# ── Display ──────────────────────────────────────────────────


def _print_header():
    print()
    print("┌──────────────────────────────────────────────────┐")
    print("│        🤖 Procurement Agent                     │")
    print("│        Agent Commerce Hub — AI × Web3           │")
    print("├──────────────────────────────────────────────────┤")


def _print_footer():
    print("└──────────────────────────────────────────────────┘")


def _show_match_results(request: str, ranked: list):
    """Show ranked matching results and let user pick a service."""
    _print_header()
    _print_line(f"Your request: {request[:44]}")
    _print_line("")
    _print_line("Matching services:")
    _print_line("")

    shown = ranked[:3]
    for i, (score, s) in enumerate(shown, 1):
        eth_s, usd_s = format_price(s["priceWei"])
        prefix = f"[{i}]"
        name = s["name"][:28]
        price_info = f"{eth_s} SETH ({usd_s})"
        _print_line(f"{prefix} {name:<28s} {price_info:<15s}")
        _print_line(f"    match: {score:>3d}")

    if len(shown) > 1:
        _print_line("")
        _print_line(f"[Enter] picks #1 — {shown[0][1]['name'][:32]}")

    _print_footer()
    print()

    try:
        choice = input("  Select service [1-3, Enter=1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""
        print()

    if choice == "":
        idx = 0
    else:
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(shown):
                idx = 0
        except ValueError:
            idx = 0

    return shown[idx][1]


def _print_line(left: str, right: str = "", width: int = 48):
    """Print a formatted line inside the box."""
    if right:
        content = f"{left:<{width - len(right)}}{right}"
    else:
        content = left
    print(f"│  {content:<{width}}│")


def _show_detailed_quote(service: dict, balance: dict) -> bool:
    """Show a detailed quote with service info and wallet balance. Returns confirmed."""
    eth_s, usd_s = format_price(service["priceWei"])
    bal = balance.get("amount", "unknown")

    _print_header()
    _print_line("QUOTE — detailed")
    _print_line("")
    _print_line(f"Service:  [{service['id']}] {service['name'][:38]}")
    _print_line("")
    _print_line(f"{service['description'][:46]}")
    _print_line("")
    _print_line(f"Price:    {eth_s} SETH ({usd_s})")
    _print_line(f"Chain:    {service['chainId']}  |  Token: {service['tokenId']}")
    _print_line(f"Pay to:   {service['paymentAddress'][:42]}")
    _print_line("")
    _print_line(f"Balance:  {bal[:12]} SETH")

    try:
        bal_f = float(bal) if bal != "unknown" else 0
        price_f = float(eth_s)
        if bal_f != 0 and bal_f >= price_f:
            _print_line(f"Status:   ✅ Sufficient balance")
        elif bal_f != 0:
            _print_line(f"Status:   ⚠️  Low balance (short by {price_f - bal_f:.5f} SETH)")
    except (ValueError, TypeError):
        pass

    _print_footer()
    print()

    try:
        confirm = input("  Confirm payment? (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        confirm = "n"
        print()
    return confirm == "y"


def _show_summary(result: dict, service: dict):
    """Display payment result summary."""
    print()
    print("=" * 50)
    if result["status"] == "completed":
        print("  ✅  PAYMENT COMPLETE")
        print(f"     Service: {service['name']}")
        eth_s, _ = format_price(service["priceWei"])
        print(f"     Amount:  {eth_s} SETH")
        tx_hash = result.get("tx_hash", "")
        if tx_hash:
            print(f"     Tx:      {tx_hash[:42]}")
        print(f"     Contract: {service['paymentAddress'][:42]}")
    elif result["status"] == "pending_approval":
        print("  ⏳  PACT SUBMITTED")
        print("     Pact created — approve in CAW App")
        pact_id = result.get("pact", {}).get("pact_id", "")
        if pact_id:
            print(f"     Pact ID: {pact_id[:36]}")
        print()
        print("     After approving, check status with:")
        print("     python run.py pay", service["id"])
    else:
        print(f"  ❌  FAILED: {result.get('error', 'unknown error')}")
    print("=" * 50)
    print()


# ── Main flow ────────────────────────────────────────────────


def procure(request_text: str) -> dict:
    """Main procurement flow for CLI.

    Args:
        request_text: Natural language user request.

    Returns:
        Dict with result status and service info.
    """
    print()
    print("  🔍 Discovering on-chain services...")
    chain = ChainClient()
    services = chain.list_services()
    active = [s for s in services if s.get("active", True)]

    if not active:
        print()
        print("  ❌ No active services available on-chain.")
        return {"status": "failed", "error": "No active services"}

    print(f"     Found {len(active)} active service(s) on Sepolia.\n")

    ranked = match_and_rank(request_text, active)
    service = _show_match_results(request_text, ranked)

    balance = get_balance()
    confirmed = _show_detailed_quote(service, balance)
    if not confirmed:
        print("  ❌ Payment cancelled.\n")
        return {"status": "cancelled", "service": service}

    _show_progress_header(service["name"])
    result = pay_for_service(service["id"], request_text)
    _show_summary(result, service)
    return result


def _show_progress_header(service_name: str):
    print()
    print("─" * 50)
    print(f"  Executing payment for: {service_name}")
    print("─" * 50)
    print()
