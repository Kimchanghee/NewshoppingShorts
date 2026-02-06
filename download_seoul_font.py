import logging
import os
import time
import requests
from requests.exceptions import RequestException

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

URLS = [
    "https://github.com/kwon37xi/free-korean-fonts/raw/master/fonts/seoul/SeoulHangangB.ttf",
    "https://github.com/seoul-metro/seoul-metro-font/raw/master/SeoulHangangB.ttf",
    "https://github.com/Seo-Riwu/Seoul-Fonts/blob/main/TTF/SeoulHangangB.ttf?raw=true"
]

TARGET = "fonts/SeoulHangangB.ttf"
os.makedirs("fonts", exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://github.com/'
}

logger.info(f"Start downloading {TARGET}...")

for url in URLS:
    try:
        logger.info(f"Trying {url}...")
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)

        if resp.status_code == 200:
            content_length = int(resp.headers.get('content-length', 0))
            if content_length > 0 and content_length < 1000:
                logger.info("  -> File too small (probably error page), skipping.")
                continue

            with open(TARGET, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            size = os.path.getsize(TARGET)
            if size > 10000:
                logger.info(f"[OK] Downloaded {TARGET} ({size} bytes)")
                exit(0)
            else:
                logger.info(f"  -> File too small ({size} bytes), broken download.")
        else:
            logger.info(f"  -> Failed with status {resp.status_code}")

    except RequestException as e:
        logger.info(f"  -> Error: {e}")

    time.sleep(1)

logger.error("[FAIL] ALL DOWNLOAD ATTEMPTS FAILED.")
exit(1)
