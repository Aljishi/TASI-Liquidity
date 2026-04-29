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


# ================= CONFIG =================
USERNAME = os.environ["SAHM_USER"]
PASSWORD = os.environ["SAHM_PASS"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "Aljishi/TASI-Liquidity"


# ================= GITHUB =================
def upload(content, filename):
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = f"https://api.github.com/repos/{REPO}/contents/data/{filename}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    r = requests.get(url, headers=headers)

    body = {
        "message": f"update {filename}",
        "content": encoded
    }

    if r.status_code == 200:
        body["sha"] = r.json()["sha"]

    res = requests.put(url, headers=headers, json=body)
    print(f"{filename} -> {res.status_code}")


# ================= SELENIUM =================
def get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=opts)


def get_table(driver):
    return driver.execute_script("""
        var result = [];
        document.querySelectorAll('table tr').forEach(function(row) {
            var cells = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());
            if (cells.some(c => c)) result.push(cells);
        });
        return result;
    """) or []


def click_tab(driver, text):
    els = driver.find_elements(By.XPATH, f"//*[text()='{text}']")
    for el in els:
        try:
            driver.execute_script("arguments[0].click();", el)
            time.sleep(3)
            return True
        except:
            pass
    return False


# ================= SMART LOGIN =================
def safe_type(driver, selectors, value, timeout=20):
    wait = WebDriverWait(driver, timeout)

    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)

            for el in elements:
                if el.is_displayed() and el.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    time.sleep(0.5)
                    el.click()
                    el.clear()
                    el.send_keys(value)
                    return True
        except:
            pass

    # fallback via JS
    for selector in selectors:
        try:
            el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            driver.execute_script("""
                arguments[0].focus();
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """, el, value)
            return True
        except:
            pass

    return False


# ================= MAIN =================
def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    ts = now.strftime("%Y-%m-%d_%H-%M-%S")

    print("Starting TEST MODE at", ts)

    driver = get_driver()

    try:
        # ===== LOGIN =====
        print("Login...")
        driver.get("https://app.sahmcapital.com/login")
        time.sleep(8)

        username_ok = safe_type(
            driver,
            [
                "input[type='email']",
                "input[type='text']",
                "input[name*='user']",
                "input[name*='email']",
                "input[placeholder*='Email']",
                "input[placeholder*='email']",
            ],
            USERNAME
        )

        password_ok = safe_type(
            driver,
            [
                "input[type='password']",
                "input[name*='pass']",
                "input[placeholder*='Password']",
                "input[placeholder*='password']",
            ],
            PASSWORD
        )

        print("username_ok:", username_ok)
        print("password_ok:", password_ok)

        time.sleep(1)

        buttons = driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], button")

        for btn in buttons:
            try:
                if btn.is_displayed() and btn.is_enabled():
                    driver.execute_script("arguments[0].click();", btn)
                    break
            except:
                pass

        time.sleep(10)
        print("Logged in URL:", driver.current_url)

        # ===== MARKET =====
        driver.get("https://app.sahmcapital.com/market")
        time.sleep(8)

        data = {
            "timestamp": ts,
            "mode": "TEST"
        }

        # ===== OVERVIEW =====
        data["overview"] = driver.execute_script("""
            var d = {};
            var lines = document.body.innerText.split('\\n').map(s=>s.trim()).filter(s=>s);

            ['TASI','NOMUC','Value','Volume','Trades','Up','Down','Unchanged'].forEach(function(k){
                var i = lines.indexOf(k);
                if(i>=0 && lines[i+1]) d[k] = lines[i+1];
            });

            return d;
        """) or {}

        # ===== TABLES =====
        data["gainers"] = get_table(driver)

        click_tab(driver, "Trades")
        data["trades"] = get_table(driver)

        click_tab(driver, "Value")
        data["value"] = get_table(driver)

        click_tab(driver, "Volume")
        data["volume"] = get_table(driver)

        content = json.dumps(data, ensure_ascii=False, indent=2)

        upload(content, "latest.json")

        snapshot_name = f"snapshot_test_{ts}.json"
        upload(content, snapshot_name)

        print("Saved:", snapshot_name)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()