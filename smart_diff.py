import json
import base64
import os
import datetime
import requests
from pathlib import Path

DATA_DIR = Path("data")
LATEST_FILE = DATA_DIR / "latest.json"
OUTPUT_FILE = DATA_DIR / "diff.json"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "Aljishi/TASI-Liquidity"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def upload_to_github(content, filename):
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not found. Skipping GitHub upload.")
        return

    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = f"https://api.github.com/repos/{REPO}/contents/data/{filename}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    r = requests.get(url, headers=headers)

    body = {
        "message": f"update {filename}",
        "content": encoded,
    }

    if r.status_code == 200:
        body["sha"] = r.json()["sha"]

    res = requests.put(url, headers=headers, json=body)
    print(f"{filename} -> {res.status_code}")


def to_number(value):
    if value is None:
        return 0.0

    text = str(value).strip()
    text = text.replace(",", "")
    text = text.replace("%", "")
    text = text.replace("+", "")
    text = text.replace("−", "-")
    text = text.replace("SAR", "")
    text = text.replace("ر.س", "")
    text = text.strip()

    if not text or text == "-":
        return 0.0

    multiplier = 1

    if text.endswith("B"):
        multiplier = 1_000_000_000
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith("K"):
        multiplier = 1_000
        text = text[:-1]

    try:
        return float(text) * multiplier
    except Exception:
        return 0.0


def parse_rows(rows, table_type):
    parsed = []

    for row in rows:
        if not isinstance(row, list):
            continue

        cleaned = [str(x).strip() for x in row if str(x).strip()]

        if len(cleaned) < 3:
            continue

        item = {
            "source_table": table_type,
            "raw": cleaned,
            "name": None,
            "symbol": None,
            "price": 0.0,
            "change_pct": 0.0,
            "value": 0.0,
            "volume": 0.0,
            "trades": 0.0,
        }

        # محاولة عامة لاستخراج الرمز
        for cell in cleaned:
            if cell.isdigit() and len(cell) == 4:
                item["symbol"] = cell
                break

        # الاسم غالباً قبل الرمز أو أول خلية نصية
        if item["symbol"] and item["symbol"] in cleaned:
            idx = cleaned.index(item["symbol"])
            if idx > 0:
                item["name"] = cleaned[idx - 1]
        else:
            item["name"] = cleaned[0]

        # استخراج النسبة
        for cell in cleaned:
            if "%" in cell:
                item["change_pct"] = to_number(cell)
                break

        # استخراج السعر: أول رقم عشري معقول غير الرمز وغير النسبة
        numeric_candidates = []
        for cell in cleaned:
            if cell == item["symbol"]:
                continue
            if "%" in cell:
                continue
            n = to_number(cell)
            if n > 0:
                numeric_candidates.append(n)

        if numeric_candidates:
            item["price"] = numeric_candidates[0]

        # حسب نوع الجدول
        if table_type == "most_active_value":
            # غالباً أكبر رقم هو القيمة
            if numeric_candidates:
                item["value"] = max(numeric_candidates)

        elif table_type == "most_active_volume":
            if numeric_candidates:
                item["volume"] = max(numeric_candidates)

        elif table_type == "most_active_trades":
            if numeric_candidates:
                item["trades"] = max(numeric_candidates)

        elif table_type == "top_gainers":
            if len(numeric_candidates) >= 2:
                item["price"] = numeric_candidates[0]

        if item["symbol"]:
            parsed.append(item)

    return parsed


def merge_by_symbol(data):
    merged = {}

    tables = {
        "top_gainers": data.get("top_gainers", []),
        "most_active_trades": data.get("most_active_trades", []),
        "most_active_value": data.get("most_active_value", []),
        "most_active_volume": data.get("most_active_volume", []),
    }

    for table_name, rows in tables.items():
        parsed_rows = parse_rows(rows, table_name)

        for item in parsed_rows:
            symbol = item["symbol"]

            if symbol not in merged:
                merged[symbol] = {
                    "symbol": symbol,
                    "name": item.get("name"),
                    "price": 0.0,
                    "change_pct": 0.0,
                    "value": 0.0,
                    "volume": 0.0,
                    "trades": 0.0,
                    "appears_in": [],
                }

            current = merged[symbol]

            if item.get("name"):
                current["name"] = item["name"]

            if item.get("price", 0) > 0:
                current["price"] = item["price"]

            if item.get("change_pct", 0) != 0:
                current["change_pct"] = item["change_pct"]

            current["value"] = max(current["value"], item.get("value", 0))
            current["volume"] = max(current["volume"], item.get("volume", 0))
            current["trades"] = max(current["trades"], item.get("trades", 0))

            if table_name not in current["appears_in"]:
                current["appears_in"].append(table_name)

    return list(merged.values())


def calculate_score(stock):
    score = 0

    change_pct = stock.get("change_pct", 0)
    value = stock.get("value", 0)
    volume = stock.get("volume", 0)
    trades = stock.get("trades", 0)
    appears = stock.get("appears_in", [])

    # 1) التغير السعري
    if change_pct > 0:
        score += 15

    if 1 <= change_pct <= 5:
        score += 15
    elif 5 < change_pct <= 8:
        score += 10
    elif change_pct > 8:
        score += 5

    # 2) الظهور في أكثر من قائمة
    if "top_gainers" in appears:
        score += 15

    if "most_active_value" in appears:
        score += 20

    if "most_active_trades" in appears:
        score += 20

    if "most_active_volume" in appears:
        score += 10

    # 3) فلتر القيمة
    if value >= 10_000_000:
        score += 15
    elif value >= 5_000_000:
        score += 10
    elif value >= 1_000_000:
        score += 5

    # 4) فلتر الصفقات
    if trades >= 5000:
        score += 10
    elif trades >= 2000:
        score += 7
    elif trades >= 1000:
        score += 4

    # 5) فلتر الحجم
    if volume >= 5_000_000:
        score += 10
    elif volume >= 1_000_000:
        score += 6
    elif volume >= 500_000:
        score += 3

    return min(round(score, 1), 100)


def classify_signal(stock):
    score = stock["score"]
    change_pct = stock.get("change_pct", 0)

    if change_pct < 0:
        return "Ignore"

    if score >= 85:
        return "Explosion"
    elif score >= 75:
        return "Strong Watch"
    elif score >= 65:
        return "Watch"
    else:
        return "Ignore"


def add_trade_levels(stock):
    price = stock.get("price", 0)

    if price <= 0:
        stock["entry"] = None
        stock["stop_loss"] = None
        stock["target_1"] = None
        stock["target_2"] = None
        return stock

    stock["entry"] = round(price, 2)
    stock["stop_loss"] = round(price * 0.985, 2)
    stock["target_1"] = round(price * 1.02, 2)
    stock["target_2"] = round(price * 1.035, 2)

    return stock


def detect_risk(stock):
    change_pct = stock.get("change_pct", 0)
    appears = stock.get("appears_in", [])
    value = stock.get("value", 0)
    trades = stock.get("trades", 0)

    risks = []

    if change_pct > 8:
        risks.append("مرتفع جداً وقد يكون الدخول متأخر")

    if "top_gainers" in appears and "most_active_value" not in appears:
        risks.append("ارتفاع بدون قيمة تداول قوية")

    if value == 0 and trades == 0:
        risks.append("بيانات النشاط ناقصة")

    if change_pct < 0:
        risks.append("تغير سعري سلبي")

    return risks


def build_report():
    latest = load_json(LATEST_FILE)

    timestamp = latest.get("timestamp")

    stocks = merge_by_symbol(latest)

    results = []

    for stock in stocks:
        stock["score"] = calculate_score(stock)
        stock["signal"] = classify_signal(stock)
        stock["risks"] = detect_risk(stock)
        stock = add_trade_levels(stock)

        if stock.get("change_pct", 0) > 0:
            results.append(stock)

    results = sorted(
        results,
        key=lambda x: (
            x.get("score", 0),
            x.get("value", 0),
            x.get("trades", 0),
            x.get("change_pct", 0),
        ),
        reverse=True,
    )

    top_opportunities = [
        x for x in results
        if x["signal"] in ["Explosion", "Strong Watch", "Watch"]
    ][:10]

    best_3 = top_opportunities[:3]

    now = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=3))
    ).strftime("%Y-%m-%d_%H-%M")

    output = {
        "type": "TASI_AI_TERMINAL_SMART_DIFF",
        "generated_at": now,
        "source_timestamp": timestamp,
        "method": "Opening Scanner PRO",
        "best_3": best_3,
        "top_opportunities": top_opportunities,
        "all_results": results,
        "notes": [
            "هذه النتائج احتمالية وليست توصية مضمونة.",
            "يفضل تأكيد الدخول باختراق قمة أول 15 دقيقة أو إعادة اختبار ناجحة.",
            "تجاهل أي سهم تتحول سيولته إلى سلبية أو يكسر سعر الافتتاح.",
        ],
    }

    save_json(output, OUTPUT_FILE)

    content = json.dumps(output, ensure_ascii=False, indent=2)
    upload_to_github(content, "diff.json")

    print("Smart diff created successfully.")
    print("Top 3 opportunities:")

    for i, item in enumerate(best_3, start=1):
        print(
            f"{i}. {item.get('name')} "
            f"({item.get('symbol')}) | "
            f"Score: {item.get('score')} | "
            f"Signal: {item.get('signal')}"
        )


if __name__ == "__main__":
    build_report()