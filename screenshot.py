import os, time, datetime, base64, json, requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

USERNAME = os.environ["SAHM_USER"]
PASSWORD = os.environ["SAHM_PASS"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "Aljishi/TASI-Liquidity"

def upload(content, filename):
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = "https://api.github.com/repos/" + REPO + "/contents/data/" + filename
    headers = {"Authorization": "token " + GITHUB_TOKEN}
    r = requests.get(url, headers=headers)
    body = {"message": "update " + filename, "content": encoded}
    if r.status_code == 200:
        body["sha"] = r.json()["sha"]
    res = requests.put(url, headers=headers, json=body)
    print(filename + " -> " + str(res.status_code))

def get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
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
    els = driver.find_elements(By.XPATH, "//*[text()='" + text + "']")
    for el in els:
        try:
            driver.execute_script("arguments[0].click();", el)
            time.sleep(4)
            return True
        except:
            pass
    return False

def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    ts = now.strftime("%Y-%m-%d_%H-%M")
    print("Starting at " + ts)

    driver = get_driver()
    try:
        print("Login...")
        driver.get("https://app.sahmcapital.com/login")
        time.sleep(6)

        if "login" in driver.current_url:
            inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='email'],input[type='text']")
            if inputs:
                inputs[0].send_keys(USERNAME)
            pw = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            if pw:
                pw[0].send_keys(PASSWORD)
            btns = driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
            if btns:
                btns[0].click()
            time.sleep(10)

        print("Go to market...")
        driver.get("https://app.sahmcapital.com/market")
        time.sleep(8)

        try:
            skip = driver.find_elements(By.XPATH, "//*[contains(text(),'Skip') or contains(text(),'Next')]")
            for s in skip:
                try: driver.execute_script("arguments[0].click();", s)
                except: pass
        except: pass
        time.sleep(2)

        data = {"timestamp": ts}

        print("Get overview...")
        data["overview"] = driver.execute_script("""
            var d = {};
            var lines = document.body.innerText.split('\\n').map(s=>s.trim()).filter(s=>s);
            ['TASI','NOMUC','Value','Volume','Trades','Up','Down','Unchanged'].forEach(function(k){
                var i = lines.indexOf(k);
                if(i>=0 && lines[i+1]) d[k] = lines[i+1];
            });
            return d;
        """) or {}
        print("Overview: " + str(data["overview"]))

        print("Get top gainers...")
        data["top_gainers"] = get_table(driver)
        print("Rows: " + str(len(data["top_gainers"])))

        print("Get most active trades...")
        click_tab(driver, "Trades")
        data["most_active_trades"] = get_table(driver)
        print("Rows: " + str(len(data["most_active_trades"])))

        print("Get most active value...")
        click_tab(driver, "Value")
        data["most_active_value"] = get_table(driver)
        print("Rows: " + str(len(data["most_active_value"])))

        print("Get most active volume...")
        click_tab(driver, "Volume")
        data["most_active_volume"] = get_table(driver)
        print("Rows: " + str(len(data["most_active_volume"])))

        content = json.dumps(data, ensure_ascii=False, indent=2)
        upload(content, "latest.json")
        print("Done!")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
