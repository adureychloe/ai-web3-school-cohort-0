"""Procurement Agent — natural language service procurement.

Matches user requests to on-chain services using AI-powered semantic
analysis. Supports any language (Chinese, English, mixed).
"""

import json
import os
import subprocess
import urllib.request
from web3 import Web3

from .chain_client import ChainClient
from .engine import pay_for_service

# SETH price estimate for USD display
SETH_PRICE_USD = 3000

# AI matching configuration
_AI_MODEL = "deepseek-v4-flash"
_AI_ENDPOINT = os.environ.get(
    "AI_MATCH_ENDPOINT",
    "https://api.deepseek.com/v1/chat/completions",
)
_AI_KEY = os.environ.get(
    "AI_MATCH_API_KEY",
    os.environ.get("DEEPSEEK_API_KEY",
    os.environ.get("OPENAI_API_KEY", "")),
)


# ── Helpers ─────────────────────────────────────────────────



def _ai_match(request: str, services: list) -> tuple[list, str]:
    """Use AI to semantically match a request to available services.

    Calls the configured LLM to analyze intent. Falls back to local scoring on error.
    Returns ([(score, service), ...], source) where source is 'ai' or 'local_fallback'.
    """
    if not _AI_KEY or not services:
        return [(0, s) for s in services], "local_fallback"

    service_list = [
        {"id": s["id"], "name": s["name"], "description": s["description"]}
        for s in services
    ]

    import json as _json
    prompt = (
        "You are a service matching AI. Given a user request and available services, "
        "score each service by semantic relevance.\n\n"
        f'User request: "{request}"\n\n'
        f"Available services:\n{_json.dumps(service_list, indent=2, ensure_ascii=False)}\n\n"
        "Return ONLY a JSON array of objects with:\n"
        "- service_id: int\n"
        "- score: int (0-10, 10=perfect match)\n"
        "- reason: str (one sentence)\n\n"
        'Example: [{"service_id": 1, "score": 8, "reason": "..."}]\n\n'
        "Rules:\n"
        "- Understand intent beyond keywords.\n"
        "- Support any language: Chinese, English, mixed.\n"
        "- Score 8-10: obvious match. 4-7: partial. 0-3: minimal/no match.\n"
        "- Return ALL services. ONLY output JSON, nothing else."
    )

    payload = _json.dumps({
        "model": _AI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500,
    }).encode()

    try:
        req = urllib.request.Request(
            _AI_ENDPOINT,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_AI_KEY}",
                "x-api-key": _AI_KEY,
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=30)
        body = _json.loads(resp.read())
        content = body["choices"][0]["message"]["content"]

        ai_results = _json.loads(content)
        ai_by_id = {r["service_id"]: r for r in ai_results if isinstance(r, dict) and "score" in r}
        scored = [(ai_by_id.get(s["id"], {"score": 0})["score"], s) for s in services]
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return scored, "ai"
    except Exception:
        # Fallback: local semantic scoring via phrase matching
        return _local_score(request, services), "local_fallback"


def _local_score(request: str, services: list) -> list:
    """Local fallback scoring when AI endpoint is unavailable.

    Uses phrase-level matching and semantic word groups instead of
    single-character tokenization. Supports Chinese and English.
    """
    import difflib
    import re

    req_lower = request.lower()

    # Define semantic intent groups (AI-powered replacement of _CN_TAGS)
    intent_groups = {
        "write": ["写", "研究", "研究", "笔记", "notes", "research", "report", "文档", "doc", "summary",
                   "总结", "生成", "generate", "create", "article", "文章", "project", "项目"],
        "data": ["数据", "data", "查询", "query", "地址", "address", "余额", "balance",
                 "价格", "price", "交易", "transaction", "history", "历史", "链上", "onchain",
                 "状态", "status", "监控", "monitor", "fetch", "获取", "rpc"],
        "analyze": ["分析", "analysis", "市场", "market", "预测", "predict", "深度", "deep",
                    "行情", "趋势", "trend", "insight", "洞察", "评估", "evaluate",
                    "strategy", "策略", "indicator", "指标", "fund", "资金", "flow"],
    }

    scored = []
    for s in services:
        text = f"{s['name']} {s['description']}".lower()

        # Score 1: Direct word/phrase overlap
        words_req = set(re.findall(r'[a-zA-Z]{3,}', req_lower))
        words_svc = set(re.findall(r'[a-zA-Z]{3,}', text))
        eng_overlap = len(words_req & words_svc) if words_svc else 0

        # Score 2: Intent group overlap
        intent_score = 0
        req_intents = set()
        for group_name, keywords in intent_groups.items():
            for kw in keywords:
                if kw.lower() in request.lower():
                    req_intents.add(group_name)
                    break

        for intent in req_intents:
            for kw in intent_groups[intent]:
                if kw.lower() in text:
                    intent_score += 1

        # Score 3: Chinese multi-character phrase overlap (not single chars)
        ch_phrases_req = set(re.findall(r'[\u4e00-\u9fff]{2,}', request))
        ch_phrases_svc = set(re.findall(r'[\u4e00-\u9fff]{2,}', text))
        ch_overlap = len(ch_phrases_req & ch_phrases_svc)

        # Score 4: SequenceMatcher similarity on full text
        sim = difflib.SequenceMatcher(None, req_lower[:200], text[:200]).ratio()

        total = eng_overlap * 2 + intent_score * 3 + ch_overlap * 2 + int(sim * 10)
        scored.append((total, s))

    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return scored


def match_and_rank(request: str, services: list) -> tuple[list, str]:
    """Use AI-powered semantic matching instead of keyword overlap.

    Falls back to equal scores if AI endpoint is unavailable.
    Returns ([(score, svc), ...], source) sorted by relevance (highest first),
    where source is 'ai' or 'local_fallback'.
    """
    return _ai_match(request, services)


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

    ranked, match_source = match_and_rank(request_text, active)
    print(f"     Match method: {'🤖 AI' if match_source == 'ai' else '📊 Local fallback'}")
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
