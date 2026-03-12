#!/usr/bin/env python3
"""Subscription Fee Calculator — CLI tool for tracking and comparing subscription costs."""

import json
import argparse
import sys
import urllib.request
from pathlib import Path
from datetime import date

DATA_FILE = Path(__file__).parent / "data.json"

# Period lengths in days (for inter-period conversion)
PERIOD_DAYS = {"day": 1, "month": 30, "quarter": 90, "year": 360}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load() -> list:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def save(data: list) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

def fetch_rate() -> float | None:
    """Fetch live USD→CNY rate from open.er-api.com (no key required)."""
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        with urllib.request.urlopen(url, timeout=6) as resp:
            return json.loads(resp.read())["rates"]["CNY"]
    except Exception:
        return None


def get_rate(manual_rate: float | None) -> float:
    """Return exchange rate: manual override > live fetch."""
    if manual_rate is not None:
        print(f"  汇率（手动）：1 USD = {manual_rate:.4f} CNY")
        return manual_rate
    rate = fetch_rate()
    if rate is None:
        print("错误：无法获取汇率，请用 --rate 手动指定。", file=sys.stderr)
        sys.exit(1)
    print(f"  汇率（实时）：1 USD = {rate:.4f} CNY")
    return rate


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def convert(amount: float, src_period: str, src_currency: str,
            dst_period: str, dst_currency: str, usd_cny: float) -> float:
    """Convert amount from (src_period, src_currency) to (dst_period, dst_currency)."""
    # Step 1: normalize to per-day
    per_day = amount / PERIOD_DAYS[src_period]
    # Step 2: scale to target period
    result = per_day * PERIOD_DAYS[dst_period]
    # Step 3: convert currency
    if src_currency != dst_currency:
        if src_currency == "USD":
            result *= usd_cny       # USD → CNY
        else:
            result /= usd_cny       # CNY → USD
    return result


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(args) -> None:
    data = load()
    entry = {
        "name":     args.name,
        "amount":   args.amount,
        "period":   args.period,
        "currency": args.currency,
        "added":    date.today().isoformat(),
    }
    data.append(entry)
    save(data)
    print(f"已添加：{args.name}  {args.amount} {args.currency}/{args.period}")


def cmd_list(args) -> None:
    data = load()
    if not data:
        print("暂无订阅。")
        return
    hdr = f"{'#':<4}{'名称':<22}{'金额':>10}  {'货币':<6}{'周期':<10}{'添加日期'}"
    print(hdr)
    print("─" * len(hdr))
    for i, s in enumerate(data, 1):
        print(f"{i:<4}{s['name']:<22}{s['amount']:>10.2f}  {s['currency']:<6}{s['period']:<10}{s.get('added','')}")


def cmd_delete(args) -> None:
    data = load()
    idx = args.index - 1
    if not (0 <= idx < len(data)):
        print(f"无效序号：{args.index}，共 {len(data)} 条订阅。", file=sys.stderr)
        sys.exit(1)
    removed = data.pop(idx)
    save(data)
    print(f"已删除：{removed['name']}")


def cmd_summary(args) -> None:
    data = load()
    if not data:
        print("暂无订阅。")
        return

    rate = get_rate(args.rate)
    to_cur, to_per = args.currency, args.period

    sym = {"CNY": "¥", "USD": "$"}[to_cur]
    per_label = {"day": "天", "month": "月", "quarter": "季", "year": "年"}[to_per]

    col_w = 20
    print(f"\n{'─'*60}")
    print(f"  汇总  —  目标：{to_cur} / {to_per}")
    print(f"{'─'*60}")
    print(f"  {'#':<4}{'名称':<{col_w}}{'原始金额':>14}  {'换算金额':>14}")
    print(f"  {'─'*56}")

    total = 0.0
    for i, s in enumerate(data, 1):
        converted = convert(s["amount"], s["period"], s["currency"],
                            to_per, to_cur, rate)
        total += converted
        orig = f"{s['amount']:.2f} {s['currency']}/{s['period']}"
        conv = f"{sym}{converted:.2f}/{per_label}"
        print(f"  {i:<4}{s['name']:<{col_w}}{orig:>14}  {conv:>14}")

    print(f"  {'─'*56}")
    print(f"  {'合计':<{col_w+5}}{sym}{total:.2f}/{per_label}")
    print(f"{'─'*60}\n")


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sub",
        description="订阅费用计算器 — 管理并统一换算所有订阅费用",
    )
    sub = parser.add_subparsers(dest="cmd", metavar="命令")

    # add
    p_add = sub.add_parser("add", help="新增订阅")
    p_add.add_argument("name",     help="订阅名称")
    p_add.add_argument("amount",   type=float, help="金额")
    p_add.add_argument("period",   choices=["day", "month", "quarter", "year"], help="计费周期")
    p_add.add_argument("currency", choices=["CNY", "USD"], help="货币")

    # list
    sub.add_parser("list", help="列出所有订阅")

    # delete
    p_del = sub.add_parser("delete", help="按序号删除订阅（序号见 list）")
    p_del.add_argument("index", type=int, help="订阅序号")

    # summary
    p_sum = sub.add_parser("summary", help="统一换算并汇总所有订阅费用")
    p_sum.add_argument("-c", "--currency", choices=["CNY", "USD"], default="CNY",
                       help="目标货币（默认 CNY）")
    p_sum.add_argument("-p", "--period",   choices=["day", "month", "quarter", "year"],
                       default="month", help="目标周期（默认 month）")
    p_sum.add_argument("-r", "--rate", type=float, metavar="RATE",
                       help="手动指定 USD/CNY 汇率（优先于实时汇率）")

    args = parser.parse_args()

    dispatch = {
        "add":     cmd_add,
        "list":    cmd_list,
        "delete":  cmd_delete,
        "summary": cmd_summary,
    }
    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
