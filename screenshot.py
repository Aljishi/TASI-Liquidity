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
URLS = {
    "market": "https://app.sahmcapital.com/market",
    "top_gainers": "https://app.sahmcapital.com/market?tab=top_gainers",
    "most_active": "https://app.sahmcapital.com/market?tab=most_active",
    "liquidity": "https://app.sahmcapital.com/market?tab=liquidity",
}
USERNAME = os.environ["SAHM_USER"]
PASSWORD = os.environ["SAHM_PASS"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "Aljishi/TASI-Liquidity"

def upload_to_github(content_str, filename):
    content = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    url = "https://api.github.com/repos/" + REPO + "/contents/data/" + filename
    headers = {"Authorization": "token " + GITHUB_TOKEN, "Content-Type": "application/json"}
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
        btns = driver.find_elements(By.XPATH,
            "//*[contains(text(),'Skip') or contains(text(),'Next') or contains(text(),'تخطى') or contains(text(),'اغلاق') or contains(text(),'Close')]")
        for btn in btns:
            try:
                btn.click()
                time.sleep(1)
            except:
                pass
    except:
        pass

def extract_table(driver):
    rows = []
    try:
        table_rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
        for row in table_rows:
            cells = [c.text.strip() for c in row.find_elements(By.TAG_NAME, "td")]
            if any(c for c in cells if c):
                rows.append(cells)
    except:
        pass
    if not rows:
        try:
            rows = driver.execute_script("""
                var result = [];
                var rows = document.querySelectorAll('table tr');
                rows.forEach(function(row) {
                    var cells = [];
                    row.querySelectorAll('td').forEach(function(td) {
                        cells.push(td.innerText.trim());
                    });
                    if(cells.some(c => c.length > 0)) result.push(cells);
                });
                return result;
            """)
        except:
            pass
    return rows

def login(driver):
    print("Opening login page...")
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
        print("Login submitted")
        time.sleep(10)
    skip_popups(driver)

def scrape_page(driver, url, label):
    print("Scraping: " + label)
    driver.get(url)
    time.sleep(8)
    skip_popups(driver)
    time.sleep(2)
    rows = extract_table(driver)
    overview_text = driver.execute_script("""
        var el = document.querySelector('[class*="overview"], [class*="summary"], [class*="market"]');
        return el ? el.innerText : '';
    """)
    return {"label": label, "rows": rows, "overview": overview_text}

def scrape():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    timestamp = now.strftime("%Y-%m-%d_%H-%M")
    minute = now.minute
    snapshot_name = "snapshot_1.json" if minute <= 15 else "snapshot_2.json"

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--lang=ar")

    driver = webdriver.Chrome(options=opts)

    try:
        login(driver)

        all_data = {"timestamp": timestamp, "snapshot": snapshot_name, "sections": {}}

        driver.get(URLS["market"])
        time.sleep(8)
        skip_popups(driver)

        overview = driver.execute_script("""
            var texts = [];
            ['Value','Volume','Trades','Up','Down','Unchanged','TASI','NOMUC'].forEach(function(key) {
                var els = document.querySelectorAll('*');
                els.forEach(function(el) {
                    if(el.children.length === 0 && el.innerText && el.innerText.includes(key)) {
                        texts.push(el.parentElement ? el.parentElement.innerText.trim() : el.innerText.trim());
                    }
                });
            });
            return texts.slice(0, 20);
        """)
        all_data["market_overview"] = overview

        market_rows = extract_table(driver)
        all_data["sections"]["top_gainers"] = market_rows[:50]

        tabs = [
            ("most_active_trades", "الأكثر نشاطاً - صفقات"),
            ("most_active_value", "الأكثر نشاطاً - قيمة"),
            ("most_active_volume", "الأكثر نشاطاً - حجم"),
        ]

        for tab_key, tab_label in tabs:
            try:
                tab_btns = driver.find_elements(By.XPATH,
                    "//*[contains(text(),'Trades') or contains(text(),'Value') or contains(text(),'Volume') or contains(text(),'صفقات') or contains(text(),'قيمة') or contains(text(),'حجم')]")
                for btn in tab_btns:
                    if tab_label.split(" - ")[1].lower() in btn.text.lower() or tab_label.split(" - ")[1] in btn.text:
                        btn.click()
                        time.sleep(4)
                        break
                rows = extract_table(driver)
                all_data["sections"][tab_key] = rows[:20]
            except Exception as e:
                print("Tab error: " + str(e))

        content_str = json.dumps(all_data, ensure_ascii=False, indent=2)
        upload_to_github(content_str, snapshot_name)
        upload_to_github(content_str, "latest.json")
        print("Done! Timestamp: " + timestamp)

    finally:
        driver.quit()

if __name__ == "__main__":
    scrape()
