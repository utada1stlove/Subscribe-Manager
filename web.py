#!/usr/bin/env python3
"""Subscription Fee Calculator — Flask web backend."""

import json
import urllib.request
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

DATA_FILE = Path(__file__).parent / "data.json"

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
# Currency / conversion
# ---------------------------------------------------------------------------

def fetch_rate() -> float | None:
    """Fetch live USD→CNY rate from open.er-api.com (no key required)."""
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        with urllib.request.urlopen(url, timeout=6) as resp:
            return json.loads(resp.read())["rates"]["CNY"]
    except Exception:
        return None


def convert(amount: float, src_period: str, src_currency: str,
            dst_period: str, dst_currency: str, usd_cny: float) -> float:
    """Convert amount from (src_period, src_currency) to (dst_period, dst_currency)."""
    per_day = amount / PERIOD_DAYS[src_period]
    result = per_day * PERIOD_DAYS[dst_period]
    if src_currency != dst_currency:
        if src_currency == "USD":
            result *= usd_cny
        else:
            result /= usd_cny
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/subscriptions", methods=["GET"])
def get_subscriptions():
    return jsonify(load())


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
    if currency not in ("CNY", "USD"):
        return jsonify({"error": "currency must be CNY or USD"}), 400

    data = load()
    entry = {
        "name": name,
        "amount": amount,
        "period": period,
        "currency": currency,
        "added": date.today().isoformat(),
    }
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
        if body["currency"] not in ("CNY", "USD"):
            return jsonify({"error": "currency must be CNY or USD"}), 400
        entry["currency"] = body["currency"]

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
    rate = fetch_rate()
    if rate is None:
        return jsonify({"error": "failed to fetch rate"}), 502
    return jsonify({"usd_cny": rate})


@app.route("/api/summary", methods=["GET"])
def get_summary():
    currency = request.args.get("currency", "CNY")
    period = request.args.get("period", "month")
    rate_param = request.args.get("rate")

    if currency not in ("CNY", "USD"):
        return jsonify({"error": "currency must be CNY or USD"}), 400
    if period not in PERIOD_DAYS:
        return jsonify({"error": f"period must be one of {list(PERIOD_DAYS)}"}), 400

    if rate_param is not None:
        try:
            usd_cny = float(rate_param)
            if usd_cny <= 0:
                raise ValueError
        except ValueError:
            return jsonify({"error": "rate must be a positive number"}), 400
        rate_source = "manual"
    else:
        usd_cny = fetch_rate()
        if usd_cny is None:
            return jsonify({"error": "failed to fetch live rate; supply ?rate="}), 502
        rate_source = "live"

    data = load()
    items = []
    total = 0.0
    for sub in data:
        converted = convert(sub["amount"], sub["period"], sub["currency"],
                            period, currency, usd_cny)
        total += converted
        items.append({
            "name": sub["name"],
            "amount": sub["amount"],
            "period": sub["period"],
            "currency": sub["currency"],
            "converted": round(converted, 4),
        })

    return jsonify({
        "currency": currency,
        "period": period,
        "usd_cny": usd_cny,
        "rate_source": rate_source,
        "total": round(total, 4),
        "items": items,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
