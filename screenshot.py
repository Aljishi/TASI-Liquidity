import os
import time
import datetime
import base64
import json
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL_LOGIN = "https://app.sahmcapital.com/login"
URL_MARKET = "https://app.sahmcapital.com/market"
USERNAME = os.environ["SAHM_USER"]
PASSWORD = os.environ["SAHM_PASS"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "Aljishi/TASI-Liquidity"

def upload_to_github(content_str, filename):
    content = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    url = "https://api.github.com/repos/" + REPO + "/contents/data/" + filename
    headers = {
        "Authorization": "token " + GITHUB_TOKEN,
        "Content-Type": "application/json"
    }
    get_resp = requests.get(url, headers=headers)
    data = {"message": "Update " + filename, "content": content}
    if get_resp.status_code == 200:
        data["sha"] = get_resp.json()["sha"]
    response = requests.put(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        print("Uploaded: " + filename)
    else:
        print("Failed: " + str(response.status_code))

def skip_popups(driver):
    try:
        skip_btns = driver.find_elements(By.XPATH,
            "//*[contains(text(),'Skip') or contains(text(),'Next') or contains(text(),'تخطى') or contains(text(),'التالي') or contains(text(),'Close') or contains(text(),'اغلاق')]"
        )
        for btn in skip_btns:
            try:
                btn.click()
                print("Clicked popup button: " + btn.text)
                time.sleep(1)
            except:
                pass
    except:
        pass

def extract_liquidity_data(driver):
    data = {}
    try:
        tables = driver.find_elements(By.TAG_NAME, "table")
        table_data = []
        for table in tables:
            headers = [h.text.strip() for h in table.find_elements(By.TAG_NAME, "th")]
            rows = []
            for row in table.find_elements(By.TAG_NAME, "tr"):
                cells = [c.text.strip() for c in row.find_elements(By.TAG_NAME, "td")]
                if any(c for c in cells if c):
                    rows.append(cells)
            if rows:
                table_data.append({"headers": headers, "rows": rows})
        data["tables"] = table_data

        data["full_text"] = driver.execute_script("return document.body.innerText;")

        rows = driver.execute_script("""
            var result = [];
            var els = document.querySelectorAll('[class*="row"],[class*="item"],[class*="stock"],[class*="card"],[class*="list"]');
            els.forEach(function(el) {
                var t = el.innerText.trim();
                if(t.length > 5 && t.length < 500) result.push(t);
            });
            return result;
        """)
        data["elements"] = rows

    except Exception as e:
        data["error"] = str(e)

    return data

def scrape():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    timestamp = now.strftime("%Y-%m-%d_%H-%M")

    hour = now.hour
    minute = now.minute
    if minute <= 15:
        snapshot_name = "snapshot_1.json"
    else:
        snapshot_name = "snapshot_2.json"

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--lang=ar")

    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 40)

    try:
        print("Opening login...")
        driver.get(URL_LOGIN)
        time.sleep(6)

        if "login" in driver.current_url:
            print("Logging in...")
            inputs = driver.find_elements(By.CSS_SELECTOR,
                "input[type='email'], input[type='text'], input[name='email'], input[name='username']")
            if inputs:
                inputs[0].clear()
                inputs[0].send_keys(USERNAME)
            pass_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            if pass_inputs:
                pass_inputs[0].clear()
                pass_inputs[0].send_keys(PASSWORD)
            driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for(var b of buttons) {
                    if(b.type=='submit' || b.textContent.includes('Login') || b.textContent.includes('دخول')) {
                        b.click(); break;
                    }
                }
            """)
            time.sleep(8)

        skip_popups(driver)
        time.sleep(2)

        print("Going to market...")
        driver.get(URL_MARKET)
        time.sleep(8)

        skip_popups(driver)
        time.sleep(3)

        print("Extracting data...")
        data = extract_liquidity_data(driver)
        data["timestamp"] = timestamp
        data["snapshot"] = snapshot_name

        content_str = json.dumps(data, ensure_ascii=False, indent=2)
        upload_to_github(content_str, snapshot_name)
        upload_to_github(content_str, "latest.json")

        if snapshot_name == "snapshot_2.json":
            try:
                url1 = "https://api.github.com/repos/" + REPO + "/contents/data/snapshot_1.json"
                headers = {"Authorization": "token " + GITHUB_TOKEN}
                r1 = requests.get(url1, headers=headers)
                if r1.status_code == 200:
                    s1 = json.loads(base64.b64decode(r1.json()["content"]).decode("utf-8"))
                    diff = {
                        "timestamp_1": s1.get("timestamp"),
                        "timestamp_2": timestamp,
                        "text_1_length": len(s1.get("full_text", "")),
                        "text_2_length": len(data.get("full_text", "")),
                        "tables_count_1": len(s1.get("tables", [])),
                        "tables_count_2": len(data.get("tables", [])),
                        "snapshot_1_text": s1.get("full_text", "")[:5000],
                        "snapshot_2_text": data.get("full_text", "")[:5000],
                    }
                    upload_to_github(json.dumps(diff, ensure_ascii=False, indent=2), "diff.json")
                    print("Diff created!")
            except Exception as e:
                print("Diff error: " + str(e))

        print("Done!")

    finally:
        driver.quit()

if __name__ == "__main__":
    scrape()
