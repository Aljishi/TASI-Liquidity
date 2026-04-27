import json
from pathlib import Path

DATA_DIR = Path("data")

SNAPSHOT_1 = DATA_DIR / "snapshot_1.json"
SNAPSHOT_2 = DATA_DIR / "snapshot_2.json"
OUTPUT = DATA_DIR / "diff.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def to_number(value):
    if value is None:
        return 0.0

    text = str(value).replace(",", "").replace("%", "").strip()

    if text.endswith("M"):
        return float(text[:-1]) * 1_000_000

    if text.endswith("K"):
        return float(text[:-1]) * 1_000

    try:
        return float(text)
    except:
        return 0.0


def normalize(data):
    """
    يحول البيانات إلى قاموس حسب الرمز.
    يدعم أكثر من شكل JSON.
    """

    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "stocks" in data:
            data = data["stocks"]
        else:
            data = list(data.values())

    result = {}

    for item in data:
        symbol = (
            item.get("symbol")
            or item.get("code")
            or item.get("رمز")
            or item.get("الرمز")
        )

        if not symbol:
            continue

        result[str(symbol)] = item

    return result


def get_value(item, *keys):
    for key in keys:
        if key in item:
            return item[key]
    return None


def build_diff():
    snap1 = normalize(load_json(SNAPSHOT_1))
    snap2 = normalize(load_json(SNAPSHOT_2))

    results = []

    for symbol, now in snap2.items():
        old = snap1.get(symbol, {})

        name = get_value(now, "name", "company", "السهم", "الشركة", "اسم السهم")
        price = to_number(get_value(now, "price", "last", "السعر", "آخر سعر"))
        change_pct = to_number(get_value(now, "change_pct", "changePercent", "نسبة التغير", "التغير"))
        net_now = to_number(get_value(now, "net_liquidity", "netLiquidity", "صافي السيولة", "صافي"))
        net_old = to_number(get_value(old, "net_liquidity", "netLiquidity", "صافي السيولة", "صافي"))

        value_now = to_number(get_value(now, "value", "traded_value", "القيمة"))
        value_old = to_number(get_value(old, "value", "traded_value", "القيمة"))

        trades_now = to_number(get_value(now, "trades", "transactions", "الصفقات"))
        trades_old = to_number(get_value(old, "trades", "transactions", "الصفقات"))

        volume_now = to_number(get_value(now, "volume", "الحجم"))
        volume_old = to_number(get_value(old, "volume", "الحجم"))

        net_change = net_now - net_old
        value_change = value_now - value_old
        trades_change = trades_now - trades_old
        volume_change = volume_now - volume_old

        score = 0

        if net_now > 0:
            score += 25

        if net_change > 0:
            score += 25

        if change_pct > 0:
            score += 15

        if value_change > 0:
            score += 15

        if trades_change > 0:
            score += 10

        if volume_change > 0:
            score += 10

        if change_pct >= 1 and change_pct <= 5:
            score += 10

        score = min(score, 100)

        if score >= 85:
            signal = "Explosion"
        elif score >= 75:
            signal = "Strong Watch"
        elif score >= 65:
            signal = "Watch"
        else:
            signal = "Ignore"

        results.append({
            "symbol": symbol,
            "name": name,
            "price": price,
            "change_pct": change_pct,
            "net_liquidity_now": net_now,
            "net_liquidity_change": net_change,
            "value_change": value_change,
            "trades_change": trades_change,
            "volume_change": volume_change,
            "score": score,
            "signal": signal,
            "entry": round(price, 2),
            "stop_loss": round(price * 0.985, 2),
            "target_1": round(price * 1.02, 2),
            "target_2": round(price * 1.035, 2),
        })

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    output = {
        "type": "smart_diff",
        "source": "snapshot_1 vs snapshot_2",
        "top_opportunities": results[:10],
        "all_results": results
    }

    save_json(output, OUTPUT)

    print("Smart diff created successfully")
    print("Top 3:")
    for item in results[:3]:
        print(item["symbol"], item["name"], item["score"], item["signal"])


if __name__ == "__main__":
    build_diff()