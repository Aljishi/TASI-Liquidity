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
        return rows if rows else []
    except:
        return []

def click_tab(driver, keywords):
    try:
        for kw in keywords:
            btns = driver.find_elements(By.XPATH,
                "//*[contains(text(),'" + kw + "')]")
            for btn in btns:
                tag = btn.tag_name.lower()
                if tag in ["button", "a", "span", "div", "li"]:
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(4)
                        return True
                    except:
                        pass
    except:
        pass
    return False

def get_market_overview(driver):
    try:
        return driver.execute_script("""
            var data = {};
            var text = document.body.innerText;
            var lines = text.split('\\n').map(s => s.trim()).filter(s => s);
            var keys = ['TASI','NOMUC','Value','Volume','Trades','Up','Down','Unchanged'];
            for(var i=0; i<lines.length; i++) {
                for(var k of keys) {
                    if(lines[i] === k && lines[i+1]) {
                        data[k] = lines[i+1];
                    }
                }
            }
            return data;
        """)
    except:
        return {}

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
    time.sleep(2)

def scrape():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    timestamp = now.strftime("%Y-%m-%d_%H-%M")

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

        print("Loading market page...")
        driver.get(URL_MARKET)
        time.sleep(8)
        skip_popups(driver)
        time.sleep(2)

        all_data = {
            "timestamp": timestamp,
            "market_overview": {},
            "top_gainers": [],
            "most_active_trades": [],
            "most_active_value": [],
            "most_active_volume": [],
        }

        all_data["market_overview"] = get_market_overview(driver)
        print("Overview: " + str(all_data["market_overview"]))

        all_data["top_gainers"] = extract_table(driver)
        print("Top gainers: " + str(len(all_data["top_gainers"])) + " rows")

        print("Clicking Trades tab...")
        click_tab(driver, ["Trades", "صفقات", "Most Active"])
        all_data["most_active_trades"] = extract_table(driver)
        print("Trades: " + str(len(all_data["most_active_trades"])) + " rows")

        print("Clicking Value tab...")
        click_tab(driver, ["Value", "قيمة"])
        all_data["most_active_value"] = extract_table(driver)
        print("Value: " + str(len(all_data["most_active_value"])) + " rows")

        print("Clicking Volume tab...")
        click_tab(driver, ["Volume", "حجم"])
        all_data["most_active_volume"] = extract_table(driver)
        print("Volume: " + str(len(all_data["most_active_volume"])) + " rows")

        content_str = json.dumps(all_data, ensure_ascii=False, indent=2)
        upload_to_github(content_str, "latest.json")
        print("Done! Timestamp: " + timestamp)

    finally:
        driver.quit()

if __name__ == "__main__":
    scrape()
