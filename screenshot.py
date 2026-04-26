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

# ─── CONFIG ───────────────────────────────────────────────────────────────────
URL        = "https://app.sahmcapital.com/market"
USERNAME   = os.environ["SAHM_USER"]
PASSWORD   = os.environ["SAHM_PASS"]
FOLDER_ID  = os.environ["GDRIVE_FOLDER_ID"]
SCOPES     = ["https://www.googleapis.com/auth/drive.file"]
# ──────────────────────────────────────────────────────────────────────────────

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
    print(f"✅ Uploaded: {filename} → Drive ID: {file.get('id')}")

def take_screenshot():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    timestamp = now.strftime("%Y-%m-%d_%H-%M")
    filename = f"TASI_Liquidity_{timestamp}.png"
    filepath = f"/tmp/{filename}"

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1600,900")
    opts.​​​​​​​​​​​​​​​​
