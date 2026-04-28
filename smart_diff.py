import os
import json
import base64
import datetime
import requests
from pathlib import Path

REPO = "Aljishi/TASI-Liquidity"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

DATA_DIR = Path("data")
SNAP_DIR = DATA_DIR / "snapshots"
LATEST_FILE = DATA_DIR / "latest.json"
DIFF_FILE = DATA_DIR / "diff.json"

MAX_SNAPS = 3


def now_ksa():
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=3))
    )


def ts():
    return now_ksa().strftime("%Y-%m-%d_%H-%M")


def ensure_dirs():
    SNAP_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def upload_to_github(content, repo_path):
    if not GITHUB_TOKEN:
        print("No GITHUB_TOKEN. Skipping upload.")
        return

    url = f"https://api.github.com/repos/{REPO}/contents/{repo_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    body = {
        "message": f"update {repo_path}",
        "content": encoded,
    }

    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        body["sha"] = r.json()["sha"]

    res = requests.put(url, headers=headers, json=body)
    print(f"{repo_path} -> {res.status_code}")


def to_number(value):
    if value is None:
        return 0.0

    text = str(value).strip()
    text = text.replace(",", "")
    text = text.replace("%", "")
    text = text.replace("+", "")
    text = text.replace("‎", "")
    text = text.replace("SAR", "")
    text = text.replace("ر.س", "")
    text = text.replace("−", "-")

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


def save_snapshot(latest):
    snapshot_file = SNAP_DIR / f"{ts()}.json"
    save_json(latest, snapshot_file)

    files = sorted(SNAP_DIR.glob("*.json"))
    if len(files) > 20:
        for old in files[:-20]:
            old.unlink(missing_ok=True)

    print(f"Snapshot saved: {snapshot_file}")
    return snapshot_file


def get_last_snapshots():
    files = sorted(SNAP_DIR.glob("*.json"))
    return files[-MAX_SNAPS:]


def parse_market_rows(rows, source_name):
    parsed = []

    if not isinstance(rows, list):
        return parsed

    for row in rows:
        if not isinstance(row, list):
            continue

        cells = [str(x).strip() for x in row if str(x).strip()]

        if len(cells) < 8:
            continue

        symbol = None
        name = None

        for i, cell in enumerate(cells):
            if cell.isdigit() and len(cell) == 4:
                symbol = cell
                if i + 2 < len(cells):
                    name = cells[i + 2]
                elif i + 1 < len(cells):
                    name = cells[i + 1]
                break

        if not symbol:
            continue

        price = 0.0
        change_pct = 0.0
        trades = 0.0
        volume = 0.0
        high = 0.0
        low = 0.0
        open_price = 0.0

        percent_cells = [c for c in cells if "%" in c]
        if percent_cells:
            change_pct = to_number(percent_cells[0])

        numeric = []
        for c in cells:
            if c == symbol:
                continue
            if "%" in c:
                continue
            n = to_number(c)
            if n > 0:
                numeric.append(n)

        # Sahm table common order:
        # Code, D, Symbol, Price, %Chg, Chg, Trades, Vol, Bid, BidVol, Ask, AskVol, Open, High, Low
        try:
            idx = cells.index(symbol)
            price = to_number(cells[idx + 3])
            trades = to_number(cells[idx + 6])
            volume = to_number(cells[idx + 7])
            open_price = to_number(cells[idx + 12])
            high = to_number(cells[idx + 13])
            low = to_number(cells[idx + 14])
        except Exception:
            if numeric:
                price = numeric[0]
                trades = max(numeric[-8:]) if len(numeric) >= 8 else 0
                volume = max(numeric)

        parsed.append({
            "symbol": symbol,
            "name": name,
            "price": price,
            "change_pct": change_pct,
            "trades": trades,
            "volume": volume,
            "open": open_price,
            "high": high,
            "low": low,
            "source": source_name,
        })

    return parsed


def extract_stocks(snapshot):
    all_rows = []

    sources = [
        "top_gainers",
        "most_active_trades",
        "most_active_value",
        "most_active_volume",
    ]

    for source in sources:
        rows = parse_market_rows(snapshot.get(source, []), source)
        all_rows.extend(rows)

    merged = {}

    for item in all_rows:
        sym = item["symbol"]

        if sym not in merged:
            merged[sym] = {
                "symbol": sym,
                "name": item.get("name"),
                "price": 0,
                "change_pct": 0,
                "trades": 0,
                "volume": 0,
                "open": 0,
                "high": 0,
                "low": 0,
                "sources": [],
            }

        m = merged[sym]

        if item.get("name"):
            m["name"] = item["name"]

        for key in ["price", "change_pct", "trades", "volume", "open", "high", "low"]:
            if item.get(key, 0) > 0:
                m[key] = max(m[key], item[key]) if key in ["trades", "volume"] else item[key]

        if item["source"] not in m["sources"]:
            m["sources"].append(item["source"])

    return merged


def safe_pct_change(new, old):
    if old <= 0:
        return 0
    return ((new - old) / old) * 100


def calculate_stock_signal(s1, s2, s3):
    price = s3["price"]
    change_now = s3["change_pct"]

    delta_change_1 = s2["change_pct"] - s1["change_pct"]
    delta_change_2 = s3["change_pct"] - s2["change_pct"]

    volume_growth_1 = safe_pct_change(s2["volume"], s1["volume"])
    volume_growth_2 = safe_pct_change(s3["volume"], s2["volume"])

    trades_growth_1 = safe_pct_change(s2["trades"], s1["trades"])
    trades_growth_2 = safe_pct_change(s3["trades"], s2["trades"])

    price_above_open = price > s3.get("open", 0) if s3.get("open", 0) > 0 else True
    near_high = False

    if s3.get("high", 0) > 0 and s3.get("low", 0) > 0 and s3["high"] != s3["low"]:
        position = (price - s3["low"]) / (s3["high"] - s3["low"])
        near_high = position >= 0.75
    else:
        position = None

    score = 0
    reasons = []
    risks = []

    if change_now > 0:
        score += 10
        reasons.append("السهم إيجابي سعرياً")

    if 1 <= change_now <= 5:
        score += 15
        reasons.append("نطاق صعود صحي 1%-5%")
    elif 5 < change_now <= 8:
        score += 10
        reasons.append("زخم قوي لكن يحتاج حذر")
    elif change_now > 8:
        score += 4
        risks.append("الصعود مرتفع وقد يكون الدخول متأخراً")

    if delta_change_1 > 0 and delta_change_2 > 0:
        score += 20
        reasons.append("تسارع سعري عبر القراءات الثلاث")
    elif delta_change_2 > 0:
        score += 12
        reasons.append("تحسن سعري في آخر قراءة")

    if volume_growth_1 > 0 and volume_growth_2 > 0:
        score += 18
        reasons.append("الحجم يتزايد باستمرار")
    elif volume_growth_2 > 20:
        score += 12
        reasons.append("قفزة حجم في آخر قراءة")

    if trades_growth_1 > 0 and trades_growth_2 > 0:
        score += 18
        reasons.append("الصفقات تتزايد باستمرار")
    elif trades_growth_2 > 20:
        score += 12
        reasons.append("زيادة صفقات في آخر قراءة")

    if price_above_open:
        score += 8
        reasons.append("السعر فوق الافتتاح")
    else:
        risks.append("السعر تحت الافتتاح")

    if near_high:
        score += 8
        reasons.append("السعر قريب من أعلى اليوم")

    sources_count = len(s3.get("sources", []))
    if sources_count >= 2:
        score += 8
        reasons.append("السهم يظهر في أكثر من قائمة نشاط")

    if s3.get("trades", 0) >= 1000:
        score += 5
        reasons.append("عدد الصفقات جيد")

    if s3.get("volume", 0) >= 1_000_000:
        score += 5
        reasons.append("حجم التداول قوي")

    if change_now > 8 and delta_change_2 <= 0:
        score -= 12
        risks.append("زخم مرتفع لكنه بدأ يبرد")

    if s3.get("trades", 0) < 100:
        score -= 15
        risks.append("عدد الصفقات منخفض")

    score = max(0, min(round(score, 1), 100))

    if score >= 85 and not risks:
        signal = "BUY_NOW"
        action_ar = "دخول الآن"
    elif score >= 85:
        signal = "BUY_WITH_CAUTION"
        action_ar = "دخول بحذر"
    elif score >= 75:
        signal = "STRONG_WATCH"
        action_ar = "مراقبة قوية"
    elif score >= 65:
        signal = "WATCH"
        action_ar = "مراقبة"
    else:
        signal = "IGNORE"
        action_ar = "تجاهل"

    entry = round(price * 1.002, 2)
    stop_loss = round(price * 0.985, 2)
    target_1 = round(price * 1.025, 2)
    target_2 = round(price * 1.045, 2)

    if signal == "BUY_NOW":
        confidence = min(95, round(score))
    elif signal == "BUY_WITH_CAUTION":
        confidence = min(88, round(score))
    else:
        confidence = round(score)

    return {
        "symbol": s3["symbol"],
        "name": s3.get("name"),
        "price": price,
        "change_pct": change_now,
        "trades": s3.get("trades", 0),
        "volume": s3.get("volume", 0),
        "open": s3.get("open", 0),
        "high": s3.get("high", 0),
        "low": s3.get("low", 0),
        "score": score,
        "confidence": confidence,
        "signal": signal,
        "action_ar": action_ar,
        "buy_now": signal in ["BUY_NOW", "BUY_WITH_CAUTION"],
        "entry": entry,
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "delta_change_1": round(delta_change_1, 2),
        "delta_change_2": round(delta_change_2, 2),
        "volume_growth_1_pct": round(volume_growth_1, 2),
        "volume_growth_2_pct": round(volume_growth_2, 2),
        "trades_growth_1_pct": round(trades_growth_1, 2),
        "trades_growth_2_pct": round(trades_growth_2, 2),
        "position_in_range": round(position, 2) if position is not None else None,
        "sources": s3.get("sources", []),
        "reasons": reasons[:6],
        "risks": risks,
    }


def build_analysis(snapshots):
    parsed = [extract_stocks(s) for s in snapshots]
    s1, s2, s3 = parsed

    results = []

    for sym in s3.keys():
        if sym in s1 and sym in s2:
            item = calculate_stock_signal(s1[sym], s2[sym], s3[sym])
            if item["change_pct"] > 0:
                results.append(item)

    results = sorted(
        results,
        key=lambda x: (
            x["score"],
            x["trades_growth_2_pct"],
            x["volume_growth_2_pct"],
            x["change_pct"],
        ),
        reverse=True,
    )

    best_3 = results[:3]
    buy_now = next((x for x in results if x["buy_now"]), None)

    output = {
        "type": "TASI_AI_TERMINAL_PRO",
        "generated_at": ts(),
        "entry_window": "10:15 KSA",
        "method": "3 snapshots momentum acceleration",
        "buy_now": buy_now,
        "best_3": best_3,
        "top_opportunities": results[:10],
        "all_results": results,
        "notes": [
            "التحليل يعتمد على 3 قراءات متتالية.",
            "إشارة الدخول ليست ضماناً للربح.",
            "يجب الالتزام بوقف الخسارة وعدم مطاردة سهم وصل للتشبع.",
        ],
    }

    return output


def main():
    ensure_dirs()

    if not LATEST_FILE.exists():
        print("latest.json not found.")
        return

    latest = load_json(LATEST_FILE)
    save_snapshot(latest)

    snap_files = get_last_snapshots()

    if len(snap_files) < 3:
        output = {
            "type": "TASI_AI_TERMINAL_PRO",
            "generated_at": ts(),
            "status": "waiting_for_3_snapshots",
            "snapshots_collected": len(snap_files),
            "required_snapshots": 3,
            "best_3": [],
            "top_opportunities": [],
            "all_results": [],
        }
        content = json.dumps(output, ensure_ascii=False, indent=2)
        save_json(output, DIFF_FILE)
        upload_to_github(content, "data/diff.json")
        print("Waiting for 3 snapshots.")
        return

    snapshots = [load_json(p) for p in snap_files]
    output = build_analysis(snapshots)

    content = json.dumps(output, ensure_ascii=False, indent=2)
    save_json(output, DIFF_FILE)
    upload_to_github(content, "data/diff.json")

    print("PRO analysis completed.")
    if output.get("buy_now"):
        b = output["buy_now"]
        print(f"BUY NOW: {b.get('name')} ({b.get('symbol')}) score={b.get('score')}")
    else:
        print("No BUY NOW signal.")


if __name__ == "__main__":
    main()