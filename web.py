#!/usr/bin/env python3
"""Subscription Fee Calculator — Flask web backend."""

import json
import math
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

DATA_FILE = Path(__file__).parent / "data.json"

PERIOD_DAYS: dict[str, int] = {
    "day": 1,
    "month": 30,
    "quarter": 90,
    "half_year": 180,
    "year": 360,
}

SUPPORTED_CURRENCIES = ["USD", "CNY", "EUR", "JPY", "GBP", "HKD", "SGD"]


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
# Currency / conversion
# ---------------------------------------------------------------------------

def fetch_rates(base: str = "USD") -> dict | None:
    """Fetch live rates from open.er-api.com (no key required).
    Returns a dict where rates[X] = how many X per 1 base unit."""
    try:
        url = f"https://open.er-api.com/v6/latest/{base}"
        with urllib.request.urlopen(url, timeout=6) as resp:
            return json.loads(resp.read())["rates"]
    except Exception:
        return None


def convert(amount: float, src_period: str, src_currency: str,
            dst_period: str, dst_currency: str, rates: dict) -> float:
    """Convert amount across periods and currencies.
    rates is USD-based: rates["USD"]==1.0, rates["CNY"]≈7.26, etc."""
    per_day = amount / PERIOD_DAYS[src_period]
    result = per_day * PERIOD_DAYS[dst_period]
    if src_currency != dst_currency:
        # src → USD → dst
        result = result / rates[src_currency] * rates[dst_currency]
    return result


def compute_next_renewal(added_str: str, period: str) -> tuple[str | None, int | None]:
    """Return (next_renewal_iso, days_until) based on start date and period."""
    try:
        added = date.fromisoformat(added_str)
    except (ValueError, TypeError):
        return None, None
    today = date.today()
    pd = PERIOD_DAYS.get(period, 30)
    if added >= today:
        next_date = added
    else:
        days_elapsed = (today - added).days
        cycles = max(1, math.ceil(days_elapsed / pd))
        next_date = added + timedelta(days=cycles * pd)
    days_until = (next_date - today).days
    return next_date.isoformat(), days_until


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/subscriptions", methods=["GET"])
def get_subscriptions():
    data = load()
    result = []
    for sub in data:
        item = dict(sub)
        nr, du = compute_next_renewal(sub.get("added", ""), sub.get("period", "month"))
        item["next_renewal"] = nr
        item["days_until_renewal"] = du
        result.append(item)
    return jsonify(result)


@app.route("/api/subscriptions", methods=["POST"])
def add_subscription():
    body = request.get_json(force=True)
    name = str(body.get("name", "")).strip()
    period = body.get("period", "")
    currency = body.get("currency", "")

    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        amount = float(body["amount"])
        if amount <= 0:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "amount must be a positive number"}), 400
    if period not in PERIOD_DAYS:
        return jsonify({"error": f"period must be one of {list(PERIOD_DAYS)}"}), 400
    if currency not in SUPPORTED_CURRENCIES:
        return jsonify({"error": f"currency must be one of {SUPPORTED_CURRENCIES}"}), 400

    entry: dict = {
        "name": name,
        "amount": amount,
        "period": period,
        "currency": currency,
        "added": date.today().isoformat(),
    }
    # optional fields
    if body.get("added"):
        try:
            date.fromisoformat(str(body["added"]))
            entry["added"] = str(body["added"])
        except ValueError:
            pass
    if body.get("color"):
        entry["color"] = str(body["color"])

    data = load()
    data.append(entry)
    save(data)
    return jsonify(entry), 201


@app.route("/api/subscriptions/<int:idx>", methods=["PUT"])
def update_subscription(idx: int):
    data = load()
    if not (0 <= idx < len(data)):
        return jsonify({"error": f"index {idx} out of range"}), 404
    body = request.get_json(force=True)
    entry = data[idx]

    if "name" in body:
        name = str(body["name"]).strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        entry["name"] = name

    if "amount" in body:
        try:
            amount = float(body["amount"])
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "amount must be a positive number"}), 400
        entry["amount"] = amount

    if "period" in body:
        if body["period"] not in PERIOD_DAYS:
            return jsonify({"error": f"period must be one of {list(PERIOD_DAYS)}"}), 400
        entry["period"] = body["period"]

    if "currency" in body:
        if body["currency"] not in SUPPORTED_CURRENCIES:
            return jsonify({"error": f"currency must be one of {SUPPORTED_CURRENCIES}"}), 400
        entry["currency"] = body["currency"]

    if "added" in body and body["added"]:
        try:
            date.fromisoformat(str(body["added"]))
            entry["added"] = str(body["added"])
        except ValueError:
            return jsonify({"error": "added must be YYYY-MM-DD"}), 400

    # color: null clears it, a string sets it
    if "color" in body:
        if body["color"]:
            entry["color"] = str(body["color"])
        else:
            entry.pop("color", None)

    save(data)
    return jsonify(entry)


@app.route("/api/subscriptions/<int:idx>", methods=["DELETE"])
def delete_subscription(idx: int):
    data = load()
    if not (0 <= idx < len(data)):
        return jsonify({"error": f"index {idx} out of range"}), 404
    removed = data.pop(idx)
    save(data)
    return jsonify(removed)


@app.route("/api/rate", methods=["GET"])
def get_rate():
    rates = fetch_rates("USD")
    if rates is None:
        return jsonify({"error": "failed to fetch rates"}), 502
    filtered = {c: rates[c] for c in SUPPORTED_CURRENCIES if c in rates}
    return jsonify({"base": "USD", "rates": filtered})


@app.route("/api/summary", methods=["GET"])
def get_summary():
    currency = request.args.get("currency", "CNY")
    period = request.args.get("period", "month")
    rate_param = request.args.get("rate")

    if currency not in SUPPORTED_CURRENCIES:
        return jsonify({"error": f"currency must be one of {SUPPORTED_CURRENCIES}"}), 400
    if period not in PERIOD_DAYS:
        return jsonify({"error": f"period must be one of {list(PERIOD_DAYS)}"}), 400

    rates = fetch_rates("USD")
    rate_source = "live"

    if rates is None:
        # fallback: manual USD/CNY only
        if rate_param is not None:
            try:
                manual = float(rate_param)
                if manual <= 0:
                    raise ValueError
            except ValueError:
                return jsonify({"error": "rate must be a positive number"}), 400
            data_preview = load()
            used = {s["currency"] for s in data_preview} | {currency}
            if not used.issubset({"USD", "CNY"}):
                return jsonify({"error": "live rate fetch failed; manual rate only covers USD/CNY"}), 502
            rates = {"USD": 1.0, "CNY": manual}
            rate_source = "manual"
        else:
            return jsonify({"error": "failed to fetch live rates; supply ?rate= for USD/CNY fallback"}), 502
    elif rate_param is not None:
        try:
            manual = float(rate_param)
            if manual <= 0:
                raise ValueError
        except ValueError:
            return jsonify({"error": "rate must be a positive number"}), 400
        rates["CNY"] = manual
        rate_source = "manual"

    data = load()
    items = []
    total = 0.0
    for sub in data:
        src = sub["currency"]
        if src not in rates or currency not in rates:
            continue
        converted = convert(sub["amount"], sub["period"], src, period, currency, rates)
        total += converted
        items.append({
            "name": sub["name"],
            "amount": sub["amount"],
            "period": sub["period"],
            "currency": sub["currency"],
            "color": sub.get("color"),
            "converted": round(converted, 4),
        })

    return jsonify({
        "currency": currency,
        "period": period,
        "usd_cny": rates.get("CNY", 0),
        "rate_source": rate_source,
        "total": round(total, 4),
        "items": items,
        "rates": {c: rates[c] for c in SUPPORTED_CURRENCIES if c in rates},
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
