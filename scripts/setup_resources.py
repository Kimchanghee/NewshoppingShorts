import os
import asyncio
import logging
from typing import List

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directories
BASE_DIR = os.getcwd()
VOICE_DIR = os.path.join(BASE_DIR, "resource", "voice_samples")
FONT_DIR = os.path.join(BASE_DIR, "resource", "fonts")

os.makedirs(VOICE_DIR, exist_ok=True)
os.makedirs(FONT_DIR, exist_ok=True)

# Sample Text
TEXT = "안녕하세요. 쇼핑 숏폼 메이커 목소리 테스트입니다."


# ==========================================
# 1. TTS Generation (Multi-strategy)
# ==========================================
async def generate_tts():
    logger.info("Starting TTS Generation...")

    # Strategy 1: Edge TTS (Best Quality)
    try:
        import edge_tts

        logger.info("Attempting Edge TTS...")

        voices = [
            ("ko-KR-SunHiNeural", "ko-KR-SunHiNeural.mp3"),
            ("ko-KR-InJoonNeural", "ko-KR-InJoonNeural.mp3"),
            ("ko-KR-SunHiNeural", "ko-KR-SunHiNeural-Fast.mp3", "+20%"),
            ("ko-KR-InJoonNeural", "ko-KR-InJoonNeural-Deep.mp3", "+0%", "-10Hz"),
            ("ko-KR-SunHiNeural", "ko-KR-SunHiNeural-High.mp3", "+0%", "+10Hz"),
        ]

        tasks = []
        for v in voices:
            voice_name, filename = v[0], v[1]
            rate = v[2] if len(v) > 2 else "+0%"
            pitch = v[3] if len(v) > 3 else "+0Hz"

            path = os.path.join(VOICE_DIR, filename)
            if os.path.exists(path):
                continue

            comm = edge_tts.Communicate(TEXT, voice_name, rate=rate, pitch=pitch)
            tasks.append(comm.save(path))

        await asyncio.gather(*tasks)
        logger.info("Edge TTS completed.")
        return  # Success

    except Exception as e:
        logger.warning(f"Edge TTS failed: {e}")

    # Strategy 2: gTTS (Google Translate TTS)
    try:
        from gtts import gTTS

        logger.info("Attempting gTTS (Google Translate)...")

        # gTTS only has one Korean voice, so we can only make 1 sample effectively
        # But we can save it as different filenames to satisfy the "check" if needed,
        # or just save one.
        filename = "ko-KR-Google-Standard.mp3"
        path = os.path.join(VOICE_DIR, filename)

        if not os.path.exists(path):
            tts = gTTS(text=TEXT, lang="ko")
            tts.save(path)
            logger.info(f"Saved {filename}")

    except Exception as e:
        logger.warning(f"gTTS failed: {e}")

    # Strategy 3: pyttsx3 (Offline System TTS)
    try:
        import pyttsx3

        logger.info("Attempting Offline TTS (pyttsx3)...")

        engine = pyttsx3.init()
        # Look for Korean voice
        voices = engine.getProperty("voices")
        ko_voice_id = None
        for v in voices:
            if "korea" in v.name.lower() or "ko-kr" in v.id.lower():
                ko_voice_id = v.id
                break

        if ko_voice_id:
            engine.setProperty("voice", ko_voice_id)

        filename = "ko-KR-System-Offline.wav"  # pyttsx3 saves as wav usually
        path = os.path.join(VOICE_DIR, filename)

        if not os.path.exists(path):
            engine.save_to_file(TEXT, path)
            engine.runAndWait()
            logger.info(f"Saved {filename}")

    except Exception as e:
        logger.warning(f"Offline TTS failed: {e}")


# ==========================================
# 2. Font Download (Direct Links)
# ==========================================
def download_fonts():
    logger.info("Starting Font Download...")
    import requests

    # Updated Links - Verified or Best Guess for High Availability
    links = {
        # Pretendard (Verified)
        "Pretendard-Bold.ttf": "https://github.com/orioncactus/pretendard/raw/main/packages/pretendard/dist/public/static/alternative/Pretendard-Bold.ttf",
        "Pretendard-SemiBold.ttf": "https://github.com/orioncactus/pretendard/raw/main/packages/pretendard/dist/public/static/alternative/Pretendard-SemiBold.ttf",
        # GmarketSans (Raw from correct repo structure)
        "GmarketSansTTFBold.ttf": "https://github.com/Joungkyun/font-gmarketsans/raw/master/ttf/GmarketSansTTFBold.ttf",
        "GmarketSansTTFMedium.ttf": "https://github.com/Joungkyun/font-gmarketsans/raw/master/ttf/GmarketSansTTFMedium.ttf",
        # SeoulHangang (Seoul City Official)
        # Note: Often fails due to server speed or blocking.
        # Using a reliable mirror or skipping if fails.
        "SeoulHangangB.ttf": "https://github.com/seoul-metro/fonts/raw/master/SeoulHangang/SeoulHangangB.ttf",
    }

    for name, url in links.items():
        path = os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            logger.info(f"Skipping {name} (Exists)")
            continue

        try:
            logger.info(f"Downloading {name}...")
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
                logger.info(f"Downloaded {name}")
            else:
                logger.warning(f"Failed {name}: {r.status_code}")
        except Exception as e:
            logger.warning(f"Error {name}: {e}")

    # Create README for manual download
    readme_path = os.path.join(FONT_DIR, "README_FONTS.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("""
[필수 폰트 다운로드 안내]
자동 다운로드에 실패한 폰트는 아래 링크에서 직접 다운로드하여 이 폴더에 넣어주세요.

1. 서울한강체 (SeoulHangang)
   - https://www.seoul.go.kr/seoul/font/font01.html
   
2. Gmarket Sans
   - https://corp.gmarket.com/fonts/
   
3. Pretendard
   - https://github.com/orioncactus/pretendard
   
4. Paperlogy
   - https://github.com/paperlogy/paperlogy-font
""")


if __name__ == "__main__":
    # Run Font Download
    try:
        download_fonts()
    except Exception as e:
        logger.error(f"Font download error: {e}")

    # Run TTS Generation
    try:
        # Use asyncio.run for proper event loop management
        asyncio.run(generate_tts())
    except Exception as e:
        logger.error(f"TTS Generation Error: {e}")
