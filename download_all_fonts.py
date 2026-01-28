#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download all required fonts for ShoppingShortsMaker
(Updated with reliable sources and multiple fallbacks)
"""
import logging
import os
import sys
import zipfile
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

# Windows console UTF-8
if sys.platform == 'win32':
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception as e:
        logger.debug("Failed to set UTF-8 encoding for console: %s", e)

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
}


def download_file(url, dest_path, headers=None, silent=False):
    """Download a single file with error handling"""
    try:
        resp = requests.get(url, timeout=120, headers=headers or HEADERS, allow_redirects=True)
        resp.raise_for_status()
        # Check if response is valid font data (not HTML error page)
        if len(resp.content) < 1000 or resp.content[:4] in [b'<!DO', b'<htm', b'<HTM']:
            if not silent:
                logger.error("    Invalid response (possibly HTML error page)")
            return False
        with open(dest_path, 'wb') as f:
            f.write(resp.content)
        return True
    except Exception as e:
        if not silent:
            logger.error("    Download error: %s", e)
        return False


def download_with_fallbacks(local_name, urls, silent_first=True):
    """Try downloading from multiple URLs until one succeeds"""
    dest = os.path.join(FONTS_DIR, local_name)

    # Skip if already exists
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        logger.info("    SKIP: %s (already exists)", local_name)
        return True

    for i, url in enumerate(urls):
        if download_file(url, dest, silent=(i == 0 and silent_first)):
            logger.info("    OK: %s", local_name)
            return True

    logger.warning("    FAIL: %s", local_name)
    return False


def download_and_extract_zip(name, url, files_to_extract, rename_map=None):
    """Download ZIP and extract specific files with optional renaming"""
    logger.info("\n[%s] Downloading...", name)
    try:
        resp = requests.get(url, timeout=180, headers=HEADERS, allow_redirects=True)
        resp.raise_for_status()

        with zipfile.ZipFile(BytesIO(resp.content)) as zf:
            all_files = zf.namelist()
            for target_file in files_to_extract:
                found = False
                # Search for file in ZIP (may be in subdirectory)
                for zip_name in all_files:
                    if zip_name.endswith(target_file) or zip_name.endswith(target_file.replace('.ttf', '.TTF')):
                        with zf.open(zip_name) as src:
                            # Apply rename if specified
                            final_name = rename_map.get(target_file, target_file) if rename_map else target_file
                            dest_path = os.path.join(FONTS_DIR, final_name)
                            with open(dest_path, 'wb') as dst:
                                dst.write(src.read())
                        logger.info("    OK: %s", final_name)
                        found = True
                        break
                if not found:
                    logger.warning("    NOT FOUND in ZIP: %s", target_file)
        return True
    except Exception as e:
        logger.error("    ZIP extraction error: %s", e)
        return False


def main():
    logger.info("=" * 60)
    logger.info("  Font Download Script for Shopping Shorts Maker")
    logger.info("=" * 60)

    # 1. Pretendard (GitHub - Official)
    logger.info("\n[Pretendard] Checking...")
    pretendard_files = ["Pretendard-ExtraBold.ttf", "Pretendard-Bold.ttf", "Pretendard-SemiBold.ttf"]
    pretendard_missing = [f for f in pretendard_files if not os.path.exists(os.path.join(FONTS_DIR, f))]

    if pretendard_missing:
        download_and_extract_zip(
            "Pretendard",
            "https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip",
            pretendard_missing
        )
    else:
        logger.info("    SKIP: All Pretendard fonts already exist")

    # 2. Seoul Hangang (서울한강체) - From Google Fonts
    logger.info("\n[Seoul Hangang] Downloading from Google Fonts...")
    # Google Fonts stores Seoul Hangang with different naming
    # Try direct GitHub raw URLs from Google Fonts repo
    seoul_mapping = {
        "SeoulHangangB.ttf": "SeoulHangang-Bold.ttf",
        "SeoulHangangEB.ttf": "SeoulHangang-ExtraBold.ttf",
        "SeoulHangangM.ttf": "SeoulHangang-Medium.ttf",
        "SeoulHangangL.ttf": "SeoulHangang-Light.ttf",
    }
    google_fonts_base = "https://raw.githubusercontent.com/AhmedN1993/seoul_font/main/"
    for local_name, remote_name in seoul_mapping.items():
        urls = [
            f"{google_fonts_base}{remote_name}",
            f"https://github.com/AhmedN1993/seoul_font/raw/main/{remote_name}",
        ]
        download_with_fallbacks(local_name, urls)

    # 3. Gmarket Sans (지마켓산스) - From GitHub mirror
    logger.info("\n[Gmarket Sans] Downloading...")
    gmarket_mapping = {
        "GmarketSansTTFBold.ttf": "GmarketSans-Bold.ttf",
        "GmarketSansTTFMedium.ttf": "GmarketSans-Medium.ttf",
        "GmarketSansTTFLight.ttf": "GmarketSans-Light.ttf",
    }
    gmarket_base = "https://raw.githubusercontent.com/AhmedN1993/GmarketSansMedium/master/static/"
    for local_name, remote_name in gmarket_mapping.items():
        urls = [
            f"{gmarket_base}{remote_name}",
            f"https://github.com/AhmedN1993/GmarketSansMedium/raw/master/static/{remote_name}",
        ]
        download_with_fallbacks(local_name, urls)

    # 4. Paperlogy (페이퍼로지)
    logger.info("\n[Paperlogy] Checking...")
    paperlogy_files = [
        ("Paperlogy-9Black.ttf", [
            "https://raw.githubusercontent.com/fonts-archive/Paperlogy/main/Paperlogy-9Black.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/Paperlogy/Paperlogy-9Black.ttf",
        ]),
        ("Paperlogy-8ExtraBold.ttf", [
            "https://raw.githubusercontent.com/fonts-archive/Paperlogy/main/Paperlogy-8ExtraBold.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/Paperlogy/Paperlogy-8ExtraBold.ttf",
        ]),
        ("Paperlogy-7Bold.ttf", [
            "https://raw.githubusercontent.com/fonts-archive/Paperlogy/main/Paperlogy-7Bold.ttf",
            "https://cdn.jsdelivr.net/gh/fonts-archive/Paperlogy/Paperlogy-7Bold.ttf",
        ]),
    ]
    for local_name, urls in paperlogy_files:
        download_with_fallbacks(local_name, urls)

    # 5. UnPeople (유앤피플 고딕) - Requires manual download
    logger.info("\n[UnPeople Gothic] Note:")
    unpeople_dest = os.path.join(FONTS_DIR, "UnPeople.ttf")
    if os.path.exists(unpeople_dest):
        logger.info("    OK: UnPeople.ttf (already exists)")
    else:
        logger.info("    INFO: UnPeople font requires manual download.")
        logger.info("    Download from: https://noonnu.cc/font_page/1103")
        logger.info("    Save as: fonts/UnPeople.ttf")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("  Download Complete!")
    logger.info("=" * 60)

    fonts = [f for f in os.listdir(FONTS_DIR) if f.endswith(('.ttf', '.otf', '.TTF', '.OTF'))]
    logger.info("\nTotal %d font files in %s:", len(fonts), FONTS_DIR)
    for f in sorted(fonts):
        size = os.path.getsize(os.path.join(FONTS_DIR, f)) / 1024
        logger.info("  - %s (%.1f KB)", f, size)

    # Check required fonts (UnPeople is optional)
    required = [
        "SeoulHangangB.ttf",
        "Pretendard-Bold.ttf",
        "GmarketSansTTFBold.ttf",
        "Paperlogy-9Black.ttf",
    ]
    optional = [
        "SeoulHangangEB.ttf", "SeoulHangangM.ttf", "SeoulHangangL.ttf",
        "Pretendard-ExtraBold.ttf", "Pretendard-SemiBold.ttf",
        "GmarketSansTTFMedium.ttf", "GmarketSansTTFLight.ttf",
        "Paperlogy-8ExtraBold.ttf", "Paperlogy-7Bold.ttf",
        "UnPeople.ttf"
    ]

    missing_required = [f for f in required if f not in fonts]
    missing_optional = [f for f in optional if f not in fonts]

    if missing_required:
        logger.warning("\n[WARNING] Missing required fonts (%d):", len(missing_required))
        for f in missing_required:
            logger.warning("  - %s", f)

    if missing_optional:
        logger.info("\n[INFO] Missing optional fonts (%d):", len(missing_optional))
        for f in missing_optional:
            logger.info("  - %s", f)

    if not missing_required:
        logger.info("\n[SUCCESS] All required fonts are available!")

    logger.info("\nManual download links:")
    logger.info("  - Seoul Hangang: https://english.seoul.go.kr/seoul-views/seoul-symbols/5-fonts/")
    logger.info("  - Gmarket Sans: https://corp.gmarket.com/fonts/")
    logger.info("  - Paperlogy: https://github.com/fonts-archive/Paperlogy")
    logger.info("  - UnPeople: https://noonnu.cc/font_page/1103")


if __name__ == "__main__":
    main()
