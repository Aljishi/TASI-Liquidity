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
        time.sleep(5)

        print("Page title: " + driver.title)
        print("Current URL: " + driver.current_url)

        print("Looking for input fields...")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for i, inp in enumerate(inputs):
            print("Input " + str(i) + ": type=" + str(inp.get_attribute("type")) + " name=" + str(inp.get_attribute("name")) + " placeholder=" + str(inp.get_attribute("placeholder")))

        email_field = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[type='email'], input[type='text'], input[name='email'], input[name='username']")
        ))
        email_field.clear()
        email_field.send_keys(USERNAME)
        print("Email entered")

        pass_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pass_field.clear()
        pass_field.send_keys(PASSWORD)
        print("Password entered")

        buttons = driver.find_elements(By.TAG_NAME, "button")
        for b in buttons:
            print("Button: " + str(b.text) + " type=" + str(b.get_attribute("type")))

        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_btn.click()
        print("Login clicked")
        time.sleep(10)

        print("After login URL: " + driver.current_url)

        if "/market" not in driver.current_url:
            driver.get(URL_MARKET)
            time.sleep(6)

        print("Taking screenshot...")
        driver.save_screenshot(filepath)

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
