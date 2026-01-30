#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import logging
import requests
import zipfile
from io import BytesIO

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
}

FONT_SOURCES = [
    {
        "id": "seoul_hangang",
        "name": "SeoulHangangB.ttf",
        "urls": ["https://github.com/webfontworld/seoul/raw/main/SeoulHangangB.ttf"]
    },
    {
        "id": "pretendard",
        "name": "Pretendard-ExtraBold.ttf",
        "is_zip": True,
        "urls": ["https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip"],
        "extract_files": ["Pretendard-ExtraBold.ttf", "Pretendard-Bold.ttf", "Pretendard-SemiBold.ttf"]
    },
    {
        "id": "gmarketsans",
        "name": "GmarketSansTTFBold.ttf",
        "is_zip": True,
        "urls": ["https://corp.gmarket.com/fonts/GmarketSansTTF.zip"],
        "extract_files": ["GmarketSansTTFBold.ttf"]
    },
    {
        "id": "ibm_plex",
        "name": "IBMPlexSansKR-Bold.ttf",
        "urls": ["https://github.com/google/fonts/raw/main/ofl/ibmplexsanskr/IBMPlexSansKR-Bold.ttf"]
    },
    {
        "id": "spoqa_han_sans",
        "name": "SpoqaHanSansNeo-Bold.ttf",
        "is_zip": True,
        "urls": ["https://github.com/spoqa/spoqa-han-sans/releases/download/v3.0.0/SpoqaHanSansNeo_all.zip"],
        "extract_files": ["SpoqaHanSansNeo-Bold.ttf"]
    },
    {
        "id": "cafe24_surround",
        "name": "Cafe24Ssurround.ttf",
        "urls": ["https://github.com/webfontworld/cafe24/raw/main/Cafe24Ssurround.ttf"]
    },
    {
        "id": "nanum_square",
        "name": "NanumSquareEB.ttf",
        "is_zip": True,
        "urls": ["https://github.com/naver/nanumfont/archive/refs/tags/1.0.zip"],
        "extract_files": ["NanumSquareEB.ttf"]
    },
    {
        "id": "paperlogy",
        "name": "Paperlogy-9Black.ttf",
        "urls": ["https://github.com/webfontworld/paperlogy/raw/main/Paperlogy-9Black.ttf"]
    },
    {
        "id": "kopub_batang",
        "name": "KoPubBatangBold.ttf",
        "urls": ["https://github.com/webfontworld/kopub/raw/main/KoPubBatangBold.ttf"]
    },
    {
        "id": "unpeople_gothic",
        "name": "UnPeople.ttf",
        "urls": ["https://github.com/webfontworld/un/raw/main/UnPeople.ttf"]
    }
]

def download_font(source):
    target_name = source["name"]
    target_path = os.path.join(FONTS_DIR, target_name)
    
    # Paperlogy is already there, don't redownload
    if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
        logger.info(f"  [OK] {target_name} exists.")
        return True

    for url in source["urls"]:
        try:
            logger.info(f"  [DOWN] {target_name} from {url}")
            resp = requests.get(url, timeout=60, headers=HEADERS, allow_redirects=True)
            if resp.status_code == 200:
                if source.get("is_zip"):
                    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
                        for file_to_extract in source["extract_files"]:
                            for zip_name in zf.namelist():
                                if zip_name.endswith(file_to_extract):
                                    dest = os.path.join(FONTS_DIR, file_to_extract)
                                    with zf.open(zip_name) as src, open(dest, 'wb') as dst:
                                        dst.write(src.read())
                                    logger.info(f"    - Extracted {file_to_extract}")
                                    break
                    return True
                else:
                    with open(target_path, 'wb') as f:
                        f.write(resp.content)
                    logger.info(f"    [OK] Saved {target_name}")
                    return True
            else:
                logger.warning(f"    [FAIL] Status {resp.status_code}")
        except Exception as e:
            logger.warning(f"    [ERROR] {e}")
    return False

def main():
    logger.info("=" * 60)
    logger.info("Installing All 10 Fonts for SSMaker")
    logger.info("=" * 60)
    for source in FONT_SOURCES:
        download_font(source)
    logger.info("=" * 60)
    logger.info("All fonts synced to fonts/ directory.")

if __name__ == "__main__":
    main()
