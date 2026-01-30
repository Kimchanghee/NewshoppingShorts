#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Font Downloader for Shopping Shorts Maker
Downloads all 10 required fonts and ensures they are in the fonts/ directory.
"""
import os
import sys
import logging
import requests
import zipfile
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Windows UTF-8 console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

FONT_SOURCES = [
    {
        "id": "seoul_hangang",
        "name": "SeoulHangangB.ttf",
        "urls": [
            "https://raw.githubusercontent.com/AhmedN1993/seoul_font/main/SeoulHangangB.ttf",
            "https://github.com/AhmedN1993/seoul_font/raw/main/SeoulHangangB.ttf"
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
            "https://raw.githubusercontent.com/AhmedN1993/GmarketSansMedium/master/static/GmarketSans-Bold.ttf",
            "https://github.com/AhmedN1993/GmarketSansMedium/raw/master/static/GmarketSans-Bold.ttf"
        ]
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
            "https://raw.githubusercontent.com/fonts-archive/UnPeople/main/UnPeople.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/UnPeople/UnPeople.ttf",
            "https://raw.githubusercontent.com/hangeulfont/UnPeople/main/UnPeople.ttf"
        ]
    },
    {
        "id": "nanum_square",
        "name": "NanumSquareEB.ttf",
        "urls": [
            "https://github.com/naver/nanumfont/raw/master/NanumSquare/NanumSquareEB.ttf",
            "https://raw.githubusercontent.com/naver/nanumfont/master/NanumSquare/NanumSquareEB.ttf"
        ]
    },
    {
        "id": "cafe24_surround",
        "name": "Cafe24Ssurround.ttf",
        "urls": [
            "https://raw.githubusercontent.com/fonts-archive/Cafe24-Ssurround/main/Cafe24Ssurround.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/Cafe24-Ssurround/Cafe24Ssurround.ttf"
        ]
    },
    {
        "id": "spoqa_han_sans",
        "name": "SpoqaHanSansNeo-Bold.ttf",
        "urls": [
            "https://github.com/spoqa/spoqa-han-sans/raw/master/Fonts/SpoqaHanSansNeo/SpoqaHanSansNeo-Bold.ttf",
            "https://github.com/spoqa/spoqa-han-sans/blob/master/Fonts/SpoqaHanSansNeo/SpoqaHanSansNeo-Bold.ttf?raw=true"
        ]
    },
    {
        "id": "ibm_plex",
        "name": "IBMPlexSansKR-Bold.ttf",
        "urls": [
            "https://github.com/IBM/plex/raw/master/IBM-Plex-Sans-KR/fonts/complete/ttf/IBMPlexSansKR-Bold.ttf",
            "https://github.com/IBM/plex/blob/master/IBM-Plex-Sans-KR/fonts/complete/ttf/IBMPlexSansKR-Bold.ttf?raw=true"
        ]
    },
    {
        "id": "kopub_batang",
        "name": "KoPubBatangBold.ttf",
        "urls": [
            "https://raw.githubusercontent.com/fonts-archive/KoPub-Batang/main/KoPubBatangBold.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/KoPub-Batang/KoPubBatangBold.ttf"
        ]
    }
]

def download_font(source):
    target_name = source["name"]
    target_path = os.path.join(FONTS_DIR, target_name)
    
    if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
        logger.info(f"  [SKIP] {target_name} already exists.")
        return True

    for url in source["urls"]:
        try:
            logger.info(f"  [TRY] Downloading {target_name} from {url}...")
            response = requests.get(url, timeout=30, stream=True)
            if response.status_code == 200:
                if source.get("is_zip"):
                    with zipfile.ZipFile(BytesIO(response.content)) as zf:
                        extracted = False
                        for file_to_extract in source["extract_files"]:
                            # Find it in zip (might have different path)
                            found_in_zip = False
                            for zip_info in zf.infolist():
                                if zip_info.filename.endswith(file_to_extract):
                                    with zf.open(zip_info.filename) as src, open(os.path.join(FONTS_DIR, file_to_extract), 'wb') as dst:
                                        dst.write(src.read())
                                    logger.info(f"    - Extracted {file_to_extract}")
                                    found_in_zip = True
                                    extracted = True
                                    break
                        if extracted: return True
                else:
                    with open(target_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"    [OK] Downloaded {target_name}")
                    return True
            else:
                logger.warning(f"    [FAIL] Status code {response.status_code}")
        except Exception as e:
            logger.warning(f"    [ERROR] {e}")
    
    logger.error(f"  [FAIL] All sources failed for {target_name}")
    return False

def install_font_to_windows(font_path):
    """
    On Windows, this registers the font with font table.
    Note: For persistent installation, it should be copied to C:\Windows\Fonts 
    and registered in registry, but that requires Admin. 
    We will just ensure it's in the project fonts/ folder for now.
    """
    if sys.platform != 'win32':
        return
    
    try:
        import ctypes
        FR_PRIVATE = 0x10
        FR_NOT_ENUM = 0x20
        # This only works for the current session/process generally if not persistent.
        result = ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)
        if result:
            logger.info(f"  [INSTALLED] Registered {os.path.basename(font_path)} for local session.")
        else:
            logger.warning(f"  [INFO] System registration for {os.path.basename(font_path)} might require manual install or it's already there.")
    except Exception as e:
        logger.error(f"  [ERROR] Installation failed: {e}")

def main():
    logger.info("=" * 60)
    logger.info("Shopping Shorts Maker - Font Synchronizer")
    logger.info("=" * 60)
    
    success_count = 0
    for source in FONT_SOURCES:
        if download_font(source):
            success_count += 1
            # Try to register it
            target_path = os.path.join(FONTS_DIR, source["name"])
            if os.path.exists(target_path):
                install_font_to_windows(target_path)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Sync Complete: {success_count}/{len(FONT_SOURCES)} fonts available.")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
