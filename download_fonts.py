#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
폰트 다운로드 스크립트
무료 한글 폰트를 fonts 폴더에 다운로드합니다.
"""
import logging
import os
import sys
import zipfile
from io import BytesIO

import requests

logger = logging.getLogger(__name__)

# Windows 콘솔 UTF-8 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

# 무료 한글 폰트 다운로드 URL
FONT_SOURCES = {
    # Pretendard (GitHub에서 직접 다운로드)
    "Pretendard": {
        "url": "https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip",
        "files": ["Pretendard-ExtraBold.ttf", "Pretendard-Bold.ttf", "Pretendard-SemiBold.ttf"],
        "zip_path": "public/static/"
    },
}

def download_and_extract(name, info):
    """폰트 다운로드 및 압축 해제"""
    logger.info(f"[{name}] downloading...")
    try:
        response = requests.get(info["url"], timeout=120)
        response.raise_for_status()

        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            for file in info["files"]:
                # ZIP 내부 경로
                zip_path = info.get("zip_path", "") + file

                # 파일 찾기 (경로가 다를 수 있음)
                for zip_name in zf.namelist():
                    if zip_name.endswith(file):
                        zip_path = zip_name
                        break

                try:
                    with zf.open(zip_path) as src:
                        dest_path = os.path.join(FONTS_DIR, file)
                        with open(dest_path, 'wb') as dst:
                            dst.write(src.read())
                        logger.info(f"  OK: {file}")
                except KeyError:
                    logger.warning(f"  FAIL: {file} - not found")

    except (requests.RequestException, zipfile.BadZipFile, OSError) as e:
        logger.error(f"  ERROR: {e}")

def main():
    os.makedirs(FONTS_DIR, exist_ok=True)

    logger.info("=" * 50)
    logger.info("Font Download Script")
    logger.info("=" * 50)

    # Pretendard (GitHub)
    download_and_extract("Pretendard", FONT_SOURCES["Pretendard"])

    # Noto Sans Korean (Google Fonts - reliable)
    logger.info("\n[NotoSansKR] downloading...")
    noto_base = "https://fonts.gstatic.com/s/notosanskr/v36/"
    noto_files = [
        ("notosanskr-bold-webfont.woff2", "NotoSansKR-Bold.woff2"),
        ("notosanskr-medium-webfont.woff2", "NotoSansKR-Medium.woff2"),
    ]

    # Use Google Fonts static files
    noto_urls = [
        ("https://raw.githubusercontent.com/nicennnnnnnlee/download-fonts/master/fonts/NotoSansKR-Bold.ttf", "NotoSansKR-Bold.ttf"),
        ("https://raw.githubusercontent.com/nicennnnnnnlee/download-fonts/master/fonts/NotoSansKR-Medium.ttf", "NotoSansKR-Medium.ttf"),
    ]
    for url, filename in noto_urls:
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            dest_path = os.path.join(FONTS_DIR, filename)
            with open(dest_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"  OK: {filename}")
        except (requests.RequestException, OSError) as e:
            logger.warning(f"  FAIL: {filename}: {e}")

    logger.info("\n" + "=" * 50)
    logger.info("Download complete!")
    logger.info(f"Font location: {FONTS_DIR}")
    logger.info("=" * 50)

    # 결과 확인
    fonts = [f for f in os.listdir(FONTS_DIR) if f.endswith(('.ttf', '.otf', '.woff2'))]
    logger.info(f"Total {len(fonts)} font files:")
    for f in fonts:
        logger.info(f"  - {f}")

if __name__ == "__main__":
    main()
