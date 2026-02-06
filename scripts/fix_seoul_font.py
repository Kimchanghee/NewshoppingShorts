import logging
import os
import shutil
import time
import requests
from requests.exceptions import RequestException

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

URLS = [
    "https://github.com/kwon37xi/free-korean-fonts/raw/master/fonts/seoul/SeoulHangangB.ttf",
    "https://github.com/googlefonts/seoul-hangang-condensed/raw/main/fonts/ttf/SeoulHangangCondensed-Bold.ttf",
    "https://github.com/seoul-metro/seoul-metro-font/raw/master/SeoulHangangB.ttf",
]

TARGET_DIR = "fonts"
TARGET_FILE = "SeoulHangangB.ttf"
TARGET_PATH = os.path.join(TARGET_DIR, TARGET_FILE)

os.makedirs(TARGET_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}


def download_seoul_font():
    logger.info(f"Searching web for {TARGET_FILE}...")

    for url in URLS:
        try:
            logger.info(f"  Attempting download from: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=20, stream=True, allow_redirects=True)

            if resp.status_code == 200:
                content_length = int(resp.headers.get('content-length', 0))
                if content_length > 0 and content_length < 2000:
                    logger.info("  -> File too small (likely HTML error page). Skipping.")
                    continue

                with open(TARGET_PATH, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                if os.path.getsize(TARGET_PATH) > 10000:
                    logger.info(f"[OK] Downloaded {TARGET_FILE} from web!")
                    return True
                else:
                    logger.info("  -> Downloaded file is too small (broken).")
            else:
                logger.info(f"  -> Failed with status {resp.status_code}")

        except RequestException as e:
            logger.info(f"  -> Connection error: {e}")

        time.sleep(0.5)

    return False


def fallback_solution():
    logger.warning("[WARN] Web download failed for all sources.")
    fallback_fonts = ["Pretendard-Bold.ttf", "Malgun.ttf", "Arial.ttf"]

    for font in fallback_fonts:
        src = os.path.join(TARGET_DIR, font)
        if os.path.exists(src):
            logger.info(f"  -> Applying fallback: Using {font} as {TARGET_FILE} to prevent crash.")
            shutil.copy2(src, TARGET_PATH)
            return True

    return False


if __name__ == "__main__":
    if download_seoul_font():
        logger.info("Font setup complete.")
    else:
        if fallback_solution():
            logger.info("Font setup complete (with fallback).")
        else:
            logger.error("[FAIL] Failed to setup font.")
