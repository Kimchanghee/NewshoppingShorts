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

FONT_SOURCES = [
    {
        "id": "seoul_hangang",
        "name": "SeoulHangangB.ttf",
        "urls": [
             "https://github.com/hangeulfont/seoul-hangang/raw/main/SeoulHangangB.ttf",
             "https://raw.githubusercontent.com/hangeulfont/seoul-hangang/main/SeoulHangangB.ttf"
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
        "is_zip": True,
        "urls": ["https://corp.gmarket.com/fonts/GmarketSansTTF.zip"],
        "extract_files": ["GmarketSansBold.ttf"],
        "rename": {"GmarketSansBold.ttf": "GmarketSansTTFBold.ttf"}
    },
    {
        "id": "paperlogy",
        "name": "Paperlogy-9Black.ttf",
        "urls": [
            "https://raw.githubusercontent.com/fonts-archive/Paperlogy/main/Paperlogy-9Black.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/Paperlogy/Paperlogy-9Black.ttf"
        ]
    },
    {
        "id": "unpeople_gothic",
        "name": "UnPeople.ttf",
        "urls": [
            "https://github.com/hangeulfont/UnPeople/raw/main/UnPeople.ttf",
            "https://raw.githubusercontent.com/hangeulfont/UnPeople/main/UnPeople.ttf"
        ]
    },
    {
        "id": "nanum_square",
        "name": "NanumSquareEB.ttf",
        "urls": [
            "https://github.com/hangeulfont/NanumSquare/raw/main/NanumSquareEB.ttf",
            "https://raw.githubusercontent.com/hangeulfont/NanumSquare/main/NanumSquareEB.ttf"
        ]
    },
    {
        "id": "cafe24_surround",
        "name": "Cafe24Ssurround.ttf",
        "urls": [
            "https://github.com/fonts-archive/Cafe24-Ssurround/raw/main/Cafe24Ssurround.ttf",
            "https://raw.githubusercontent.com/hangeulfont/cafe24-surround/main/Cafe24Ssurround.ttf"
        ]
    },
    {
        "id": "spoqa_han_sans",
        "name": "SpoqaHanSansNeo-Bold.ttf",
        "urls": [
            "https://github.com/spoqa/spoqa-han-sans/raw/master/Fonts/SpoqaHanSansNeo/SpoqaHanSansNeo-Bold.ttf"
        ]
    },
    {
        "id": "ibm_plex",
        "name": "IBMPlexSansKR-Bold.ttf",
        "urls": [
            "https://github.com/google/fonts/raw/main/ofl/ibmplexsanskr/IBMPlexSansKR-Bold.ttf"
        ]
    },
    {
        "id": "kopub_batang",
        "name": "KoPubBatangBold.ttf",
        "urls": [
            "https://github.com/fonts-archive/KoPub-Batang/raw/main/KoPubBatangBold.ttf",
            "https://raw.githubusercontent.com/hangeulfont/kopub-batang/main/KoPubBatangBold.ttf"
        ]
    }
]

def download_font(source):
    target_name = source["name"]
    target_path = os.path.join(FONTS_DIR, target_name)
    
    # Check if already exists from renaming or other sources
    if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
        logger.info(f"  [SKIP] {target_name} already exists.")
        return True

    for url in source["urls"]:
        try:
            logger.info(f"  [TRY] {target_name} from {url}...")
            # Use headers to avoid bot detection
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            response = requests.get(url, timeout=30, headers=headers)
            if response.status_code == 200:
                if source.get("is_zip"):
                    with zipfile.ZipFile(BytesIO(response.content)) as zf:
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
                        f.write(response.content)
                    logger.info(f"    [OK] Downloaded {target_name}")
                    return True
            else:
                logger.warning(f"    [FAIL] Status {response.status_code}")
        except Exception as e:
            logger.warning(f"    [ERROR] {e}")
    
    return False

def main():
    logger.info("Starting Font Download...")
    for source in FONT_SOURCES:
        download_font(source)
    logger.info("Done.")

if __name__ == "__main__":
    main()
