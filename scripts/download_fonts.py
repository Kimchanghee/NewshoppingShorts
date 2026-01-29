import os
import sys
import requests

# Target directory
BASE_DIR = os.getcwd()
FONT_DIR = os.path.join(BASE_DIR, "resource", "fonts")
os.makedirs(FONT_DIR, exist_ok=True)

# Required Fonts (from constants.py)
REQUIRED_FONTS = [
    "SeoulHangangB.ttf",
    "SeoulHangangEB.ttf",
    "SeoulHangangM.ttf",
    "SeoulHangangL.ttf",
    "Pretendard-ExtraBold.ttf",
    "Pretendard-Bold.ttf",
    "Pretendard-SemiBold.ttf",
    "Paperlogy-9Black.ttf",
    "Paperlogy-8ExtraBold.ttf",
    "Paperlogy-7Bold.ttf",
    "GmarketSansTTFBold.ttf",
    "GmarketSansTTFMedium.ttf",
    "GmarketSansTTFLight.ttf",
    "UnPeople.ttf",
]

# GitHub URLs for fonts (using reliable sources)
# SeoulHangang: https://github.com/seoul-metro/fonts/blob/master/SeoulHangang/SeoulHangangB.ttf?raw=true
# Pretendard: https://github.com/orioncactus/pretendard/blob/main/packages/pretendard/dist/public/static/alternative/Pretendard-Bold.ttf?raw=true
# GmarketSans: https://github.com/Joungkyun/font-gmarketsans/blob/master/ttf/GmarketSansTTFBold.ttf?raw=true
# UnPeople: https://github.com/fonts-kr/Un-fonts/blob/master/UnPeople.ttf?raw=true (example)
# Paperlogy: Usually in separate repo

# Updated URLs
FONT_URLS = {
    # SeoulHangang - Official Seoul City Repo (or reliable mirror)
    "SeoulHangangB.ttf": "https://raw.githubusercontent.com/seoul-metro/fonts/master/SeoulHangang/SeoulHangangB.ttf",
    "SeoulHangangEB.ttf": "https://raw.githubusercontent.com/seoul-metro/fonts/master/SeoulHangang/SeoulHangangEB.ttf",
    "SeoulHangangM.ttf": "https://raw.githubusercontent.com/seoul-metro/fonts/master/SeoulHangang/SeoulHangangM.ttf",
    "SeoulHangangL.ttf": "https://raw.githubusercontent.com/seoul-metro/fonts/master/SeoulHangang/SeoulHangangL.ttf",
    # GmarketSans - Official Repo
    "GmarketSansTTFBold.ttf": "https://raw.githubusercontent.com/Joungkyun/font-gmarketsans/master/ttf/GmarketSansTTFBold.ttf",
    "GmarketSansTTFMedium.ttf": "https://raw.githubusercontent.com/Joungkyun/font-gmarketsans/master/ttf/GmarketSansTTFMedium.ttf",
    "GmarketSansTTFLight.ttf": "https://raw.githubusercontent.com/Joungkyun/font-gmarketsans/master/ttf/GmarketSansTTFLight.ttf",
    # Pretendard (Already worked, keeping just in case)
    "Pretendard-ExtraBold.ttf": "https://github.com/orioncactus/pretendard/raw/main/packages/pretendard/dist/public/static/alternative/Pretendard-ExtraBold.ttf",
}


# Add default fallbacks for missing URLs if possible, or just skip
def download_fonts():
    print(f"Checking fonts in {FONT_DIR}...")
    for font_name in REQUIRED_FONTS:
        path = os.path.join(FONT_DIR, font_name)
        if os.path.exists(path):
            print(f"Skipping {font_name} (exists)")
            continue

        url = FONT_URLS.get(font_name)
        if not url:
            print(f"No URL for {font_name}, skipping")
            continue

        print(f"Downloading {font_name}...")
        try:
            r = requests.get(url, stream=True)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"Downloaded {font_name}")
            else:
                print(f"Failed to download {font_name}: {r.status_code}")
        except Exception as e:
            print(f"Error downloading {font_name}: {e}")


if __name__ == "__main__":
    download_fonts()
