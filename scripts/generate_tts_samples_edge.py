import asyncio
import os
import edge_tts

# Target directory
BASE_DIR = os.getcwd()
VOICE_DIR = os.path.join(BASE_DIR, "resource", "voice_samples")
os.makedirs(VOICE_DIR, exist_ok=True)

# Text to speak
TEXT = "안녕하세요. 쇼핑 숏폼 메이커 목소리 테스트입니다. 오늘도 좋은 하루 되세요."

# Valid Edge-TTS Korean voices
VOICES = [
    # Korean
    "ko-KR-SunHiNeural",
    "ko-KR-InJoonNeural",
    # Multilingual voices that speak Korean well (optional, but sticking to native is safer)
    # We need 10 samples. We can vary rate/pitch to create "new" voices from the base ones.
]


# Function to generate variations
async def generate_samples():
    print(f"Generating samples in {VOICE_DIR}...")

    tasks = []

    # 1. Base Voices
    tasks.append(generate_one("ko-KR-SunHiNeural", "ko-KR-SunHiNeural.mp3"))
    tasks.append(generate_one("ko-KR-InJoonNeural", "ko-KR-InJoonNeural.mp3"))

    # 2. Variations (Speed/Pitch) to simulate different personas
    # SunHi Fast
    tasks.append(
        generate_one("ko-KR-SunHiNeural", "ko-KR-SunHiNeural-Fast.mp3", rate="+20%")
    )
    # InJoon Deep
    tasks.append(
        generate_one("ko-KR-InJoonNeural", "ko-KR-InJoonNeural-Deep.mp3", pitch="-10Hz")
    )
    # SunHi High
    tasks.append(
        generate_one("ko-KR-SunHiNeural", "ko-KR-SunHiNeural-High.mp3", pitch="+10Hz")
    )
    # InJoon Fast
    tasks.append(
        generate_one("ko-KR-InJoonNeural", "ko-KR-InJoonNeural-Fast.mp3", rate="+20%")
    )

    # 3. Extra (using different text style if needed, but here just more pitch variations)
    tasks.append(
        generate_one("ko-KR-SunHiNeural", "ko-KR-SunHiNeural-Slow.mp3", rate="-10%")
    )
    tasks.append(
        generate_one("ko-KR-InJoonNeural", "ko-KR-InJoonNeural-Slow.mp3", rate="-10%")
    )

    # 4. English voices that might work for specific effects (or just fill to 10 with more variations)
    # Let's add more variations
    tasks.append(
        generate_one(
            "ko-KR-SunHiNeural", "ko-KR-SunHiNeural-Calm.mp3", pitch="-5Hz", rate="-5%"
        )
    )
    tasks.append(
        generate_one(
            "ko-KR-InJoonNeural",
            "ko-KR-InJoonNeural-Bright.mp3",
            pitch="+5Hz",
            rate="+5%",
        )
    )

    await asyncio.gather(*tasks)
    print("All samples generated.")


async def generate_one(voice, filename, rate="+0%", pitch="+0Hz"):
    filepath = os.path.join(VOICE_DIR, filename)
    print(f"Generating {filename} ({voice}, rate={rate}, pitch={pitch})...")
    try:
        communicate = edge_tts.Communicate(TEXT, voice, rate=rate, pitch=pitch)
        await communicate.save(filepath)
        print(f"Saved {filename}")
    except Exception as e:
        print(f"Failed {filename}: {e}")


if __name__ == "__main__":
    asyncio.run(generate_samples())
