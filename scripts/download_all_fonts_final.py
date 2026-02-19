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

# Windows console UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

FONT_SOURCES = [
    {
        "id": "seoul_hangang",
        "name": "SeoulHangangB.ttf",
        "urls": [
            "http://www.seoul.go.kr/v2012/seoul/symbol/file/SeoulHangangB.ttf",
            "https://cdn.jsdelivr.net/gh/webfontworld/seoul/SeoulHangangB.ttf"
        ]
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
        "urls": [
            "https://raw.githubusercontent.com/fonts-archive/GmarketSans/main/GmarketSansBold.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/GmarketSans/GmarketSansBold.ttf"
        ]
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
        "urls": [
            "https://fonts.cafe24.com/Ssurround/Cafe24Ssurround.ttf",
            "https://cdn.jsdelivr.net/gh/webfontworld/cafe24/Cafe24Ssurround.ttf"
        ]
    },
    {
        "id": "nanum_square",
        "name": "NanumSquareEB.ttf",
        "urls": [
            "https://cdn.jsdelivr.net/gh/moonspam/NanumSquare@master/nanumsquareeb.ttf",
            "https://github.com/naver/nanumfont/raw/gh-pages/NanumSquare/NanumSquareEB.ttf"
        ]
    },
    {
        "id": "paperlogy",
        "name": "Paperlogy-9Black.ttf",
        "urls": ["https://raw.githubusercontent.com/fonts-archive/Paperlogy/main/Paperlogy-9Black.ttf"]
    },
    {
        "id": "kopub_batang",
        "name": "KoPubBatangBold.ttf",
        "urls": ["https://raw.githubusercontent.com/fonts-archive/KoPub-Batang/main/KoPubBatangBold.ttf"]
    },
    {
        "id": "unpeople_gothic",
        "name": "UnPeople.ttf",
        "urls": ["https://cdn.jsdelivr.net/gh/fonts-archive/UnPeople/UnPeople.ttf"]
    }
]

def download_font(source):
    target_name = source["name"]
    target_path = os.path.join(FONTS_DIR, target_name)
    
    if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
        logger.info(f"  [ALREADY EXISTS] {target_name}")
        return True

    for url in source["urls"]:
        try:
            logger.info(f"  [TRYING] {target_name} from {url}")
            resp = requests.get(url, timeout=30, headers=HEADERS)
            if resp.status_code == 200:
                if source.get("is_zip"):
                    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
                        extracted = False
                        for file_to_extract in source["extract_files"]:
                            for zip_info in zf.infolist():
                                if zip_info.filename.endswith(file_to_extract):
                                    final_name = source.get("rename", {}).get(file_to_extract, file_to_extract)
                                    with zf.open(zip_info.filename) as src, open(os.path.join(FONTS_DIR, final_name), 'wb') as dst:
                                        dst.write(src.read())
                                    logger.info(f"    - Extracted {final_name}")
                                    extracted = True
                                    break
                        if extracted: return True
                else:
                    with open(target_path, 'wb') as f:
                        f.write(resp.content)
                    logger.info(f"    [OK] Downloaded {target_name}")
                    return True
            else:
                logger.warning(f"    [FAIL] Status {resp.status_code}")
        except Exception as e:
            logger.warning(f"    [ERROR] {e}")
    
    return False

def main():
    logger.info("=" * 60)
    logger.info("Syncing All Fonts for Shopping Shorts Maker")
    logger.info("=" * 60)
    
    for source in FONT_SOURCES:
        download_font(source)
    
    logger.info("\nChecking final fonts directory:")
    fonts = [f for f in os.listdir(FONTS_DIR) if f.endswith('.ttf')]
    for f in sorted(fonts):
        logger.info(f" - {f} ({os.path.getsize(os.path.join(FONTS_DIR, f)) // 1024} KB)")

if __name__ == "__main__":
    main()
