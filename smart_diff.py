import os
import json
import time
import datetime
import base64
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "Aljishi/TASI-Liquidity"

DATA_DIR = "data"
SNAP_DIR = os.path.join(DATA_DIR, "snapshots")
LATEST_FILE = os.path.join(DATA_DIR, "latest.json")
DIFF_FILE = os.path.join(DATA_DIR, "diff.json")

MAX_SNAPS = 3  # نحتاج آخر 3 قراءات فقط


# ===============================
# GitHub upload
# ===============================
def upload(content, filename):
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = f"https://api.github.com/repos/{REPO}/contents/{filename}"
    headers = {"Authorization": "token " + GITHUB_TOKEN}

    r = requests.get(url, headers=headers)
    body = {"message": f"update {filename}", "content": encoded}

    if r.status_code == 200:
        body["sha"] = r.json()["sha"]

    res = requests.put(url, headers=headers, json=body)
    print(f"{filename} -> {res.status_code}")


# ===============================
# Helpers
# ===============================
def now_ts():
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=3))
    ).strftime("%Y-%m-%d_%H-%M")


def ensure_dirs():
    if not os.path.exists(SNAP_DIR):
        os.makedirs(SNAP_DIR)


def load_latest():
    if not os.path.exists(LATEST_FILE):
        return None
    with open(LATEST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(data):
    ts = now_ts()
    path = os.path.join(SNAP_DIR, f"{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def get_last_snapshots():
    files = sorted(os.listdir(SNAP_DIR))
    files = [f for f in files if f.endswith(".json")]
    return [os.path.join(SNAP_DIR, f) for f in files[-MAX_SNAPS:]]


def load_snap(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ===============================
# Extract stocks from latest.json
# ===============================
def extract_stocks(snapshot):
    rows = snapshot.get("most_active_value") or snapshot.get("top_gainers") or []
    stocks = []

    for r in rows:
        try:
            # يعتمد على ترتيب الجدول في سهم
            symbol = r[2]
            price = float(r[3])
            change_pct = float(r[4].replace("%", "").replace("+", ""))
            trades = float(r[6].replace(",", ""))
            volume = float(r[7].replace("M", "").replace(",", "")) * 1_000_000

            stocks.append({
                "symbol": symbol,
                "price": price,
                "change_pct": change_pct,
                "trades": trades,
                "volume": volume
            })
        except:
            continue

    return stocks


def index_by_symbol(stocks):
    return {s["symbol"]: s for s in stocks}


# ===============================
# Momentum Calculation
# ===============================
def calc_score(s1, s2, s3):
    # تغير السعر
    delta_price = s3["change_pct"] - s1["change_pct"]

    # تسارع الحجم
    vol_acc = (s3["volume"] - s2["volume"]) + (s2["volume"] - s1["volume"])

    # تسارع الصفقات
    trade_acc = (s3["trades"] - s2["trades"]) + (s2["trades"] - s1["trades"])

    # معادلة مبسطة
    score = (
        delta_price * 5 +
        (vol_acc / 1_000_000) * 2 +
        (trade_acc / 1000) * 3
    )

    return round(score, 2)


# ===============================
# Main Analysis
# ===============================
def analyze(snaps):
    s1 = index_by_symbol(extract_stocks(snaps[0]))
    s2 = index_by_symbol(extract_stocks(snaps[1]))
    s3 = index_by_symbol(extract_stocks(snaps[2]))

    results = []

    for sym in s3:
        if sym in s1 and sym in s2:
            score = calc_score(s1[sym], s2[sym], s3[sym])

            if s3[sym]["change_pct"] > 0:  # استبعاد السالب
                results.append({
                    "symbol": sym,
                    "price": s3[sym]["price"],
                    "change_pct": s3[sym]["change_pct"],
                    "score": score,
                    "entry": round(s3[sym]["price"] * 1.002, 2),
                    "stop_loss": round(s3[sym]["price"] * 0.985, 2),
                    "target_1": round(s3[sym]["price"] * 1.03, 2),
                    "target_2": round(s3[sym]["price"] * 1.06, 2),
                })

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return {
        "generated_at": now_ts(),
        "best_3": results[:3],
        "top_opportunities": results[:10],
        "all_results": results
    }


# ===============================
# Main
# ===============================
def main():
    ensure_dirs()

    latest = load_latest()
    if not latest:
        print("No latest.json")
        return

    save_snapshot(latest)

    snaps_paths = get_last_snapshots()

    if len(snaps_paths) < 3:
        print("Waiting for 3 snapshots...")
        return

    snaps = [load_snap(p) for p in snaps_paths]

    result = analyze(snaps)

    content = json.dumps(result, ensure_ascii=False, indent=2)

    with open(DIFF_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    upload(content, "data/diff.json")

    print("Analysis done ✔")


if __name__ == "__main__":
    main()