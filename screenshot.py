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

def upload_to_github(filepath, filename):
    with open(filepath, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
    url = "https://api.github.com/repos/" + REPO + "/contents/screenshots/" + filename
    headers = {
        "Authorization": "token " + GITHUB_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "message": "Add screenshot " + filename,
        "content": content
    }
    response = requests.put(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        print("Uploaded to GitHub: " + filename)
    else:
        print("Upload failed: " + str(response.status_code) + " " + response.text)

def take_screenshot():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    timestamp = now.strftime("%Y-%m-%d_%H-%M")
    filename = "TASI_Liquidity_" + timestamp + ".png"
    filepath = "/tmp/" + filename

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
        print("Opening login page...")
        driver.get(URL_LOGIN)
        time.sleep(6)

        print("Current URL: " + driver.current_url)

        if "login" in driver.current_url:
            print("Logging in...")
            inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='email'], input[type='text'], input[name='email'], input[name='username']")
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
                    if(b.type=='submit' || b.textContent.includes('Login') || b.textContent.includes('Sign') || b.textContent.includes('دخول')) {
                        b.click();
                        break;
                    }
                }
            """)
            print("Login submitted")
            time.sleep(10)

        print("Navigating to market...")
        driver.get(URL_MARKET)
        time.sleep(8)

        print("Taking screenshot...")
        driver.save_screenshot(filepath)
        print("Screenshot saved: " + filename)

        return filepath, filename

    finally:
        driver.quit()

def main():
    print("Starting TASI Liquidity screenshot...")
    filepath, filename = take_screenshot()
    upload_to_github(filepath, filename)
    print("Done!")

if __name__ == "__main__":
    main()
