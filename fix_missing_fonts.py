import logging
import os
import shutil
import requests
from requests.exceptions import RequestException

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

FONTS_DIR = "fonts"
os.makedirs(FONTS_DIR, exist_ok=True)

MISSING_FONTS = [
    {
        "name": "KoPubBatangBold.ttf",
        "urls": [
            "https://raw.githubusercontent.com/fonts-archive/KoPub-Batang/main/KoPubBatangBold.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/KoPub-Batang/KoPubBatangBold.ttf"
        ]
    },
    {
        "name": "UnPeople.ttf",
        "urls": [
            "https://raw.githubusercontent.com/fonts-archive/UnPeople/main/UnPeople.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/UnPeople/UnPeople.ttf"
        ]
    }
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

logger.info("Checking and fixing missing fonts...")

for font in MISSING_FONTS:
    target_path = os.path.join(FONTS_DIR, font["name"])

    if os.path.exists(target_path) and os.path.getsize(target_path) > 10000:
        logger.info(f"[OK] {font['name']} already exists.")
        continue

    logger.info(f"Downloading {font['name']}...")
    success = False

    for url in font["urls"]:
        try:
            logger.info(f"  Attempting: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
            if resp.status_code == 200:
                with open(target_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                if os.path.getsize(target_path) > 10000:
                    logger.info("  [OK] Success!")
                    success = True
                    break
        except RequestException as e:
            logger.info(f"  Error: {e}")

    if not success:
        logger.warning(f"[WARN] Failed to download {font['name']}. Trying fallback copy from Pretendard.")
        pretendard = os.path.join(FONTS_DIR, "Pretendard-Bold.ttf")
        if os.path.exists(pretendard):
            shutil.copy2(pretendard, target_path)
            logger.info(f"  -> Created fallback copy for {font['name']}")

logger.info("All missing fonts check complete.")
