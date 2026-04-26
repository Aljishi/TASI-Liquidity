import os
import time
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json

URL_LOGIN = "https://app.sahmcapital.com/login"
URL_MARKET = "https://app.sahmcapital.com/market"
USERNAME = os.environ["SAHM_USER"]
PASSWORD = os.environ["SAHM_PASS"]
FOLDER_ID = os.environ["GDRIVE_FOLDER_ID"]
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def get_drive_service():
    creds_json = json.loads(os.environ["GDRIVE_CREDS"])
    creds = service_account.Credentials.from_service_account_info(
        creds_json, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def upload_to_drive(service, filepath, filename):
    meta = {"name": filename, "parents": [FOLDER_ID]}
    media = MediaFileUpload(filepath, mimetype="image/png")
    file = service.files().create(body=meta, media_body=media, fields="id").execute()
    print("Uploaded: " + filename)

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
            print("Login page detected, logging in...")
            inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='email'], input[type='text'], input[name='email'], input[name='username'], input[name='phone']")
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
            print("Login submitted via JS")
            time.sleep(10)

        print("Navigating to market...")
        driver.get(URL_MARKET)
        time.sleep(8)

        print("Current URL: " + driver.current_url)
        print("Taking screenshot...")
        driver.save_screenshot(filepath)
        print("Screenshot saved: " + filename)

        return filepath, filename

    finally:
        driver.quit()

def main():
    print("Starting TASI Liquidity screenshot...")
    drive_service = get_drive_service()
    filepath, filename = take_screenshot()
    upload_to_drive(drive_service, filepath, filename)
    print("Done!")

if __name__ == "__main__":
    main()
