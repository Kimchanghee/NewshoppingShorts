import os
import sys
import requests
from google import genai
from google.genai import types

# API Key from prompt
# API Key from prompt
API_KEY = os.getenv("GEMINI_API_KEY", "")

# Target directory
BASE_DIR = os.getcwd()
VOICE_DIR = os.path.join(BASE_DIR, "resource", "voice_samples")
os.makedirs(VOICE_DIR, exist_ok=True)

# Voice list (Standard Korean voices if available, otherwise typical ones)
# Using standard Google TTS voice names for Korean
VOICES = [
    "ko-KR-Standard-A",
    "ko-KR-Standard-B",
    "ko-KR-Standard-C",
    "ko-KR-Standard-D",
    "ko-KR-Wavenet-A",
    "ko-KR-Wavenet-B",
    "ko-KR-Wavenet-C",
    "ko-KR-Wavenet-D",
    # Fill up to 10 with others or English if needed, but sticking to KR context
    # Gemini might use different names like "ko-KR-Neural2-A" etc.
    # Let's try generic names that usually work with Google Cloud TTS / Gemini
    # Actually Gemini uses specific voice names. Let's try to list them or use known ones.
    # If using gemini-1.5-flash for TTS, it might be "Puck", "Charon", "Kore", "Fenrir", "Aoede" (OpenAI style)
    # OR standard Google Cloud voices.
    # Let's assume the user wants the "Gemini TTS" voices which are often:
    # "Puck", "Charon", "Kore", "Fenrir", "Aoede" (English mostly?)
    # Wait, the codebase uses `types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name))`.
    # Valid names for Gemini TTS are usually: "Puck", "Charon", "Kore", "Fenrir", "Aoede".
    # But for Korean?
    # Let's generate for the 5 main Gemini voices + 5 Google Cloud standard ones if possible.
    # Actually, let's just stick to the 5 known Gemini voices first:
    "Puck",
    "Charon",
    "Kore",
    "Fenrir",
    "Aoede",
]

# Text to speak
TEXT = "안녕하세요. 쇼핑 숏폼 메이커 목소리 테스트입니다."


def generate_samples():
    print(f"Initializing Gemini Client...")
    try:
        client = genai.Client(api_key=API_KEY)
    except Exception as e:
        print(f"Failed to init client: {e}")
        return

    print(f"Generating samples in {VOICE_DIR}...")

    # We need 10 samples. If only 5 gemini voices, we can change pitch/speed or just duplicate with suffix?
    # Or maybe there are more.
    # Let's try the 5 known ones.

    for i, voice_name in enumerate(VOICES):
        filename = f"{voice_name}.wav"
        filepath = os.path.join(VOICE_DIR, filename)

        if os.path.exists(filepath):
            print(f"Skipping {filename} (exists)")
            continue

        print(f"Generating {filename}...")
        try:
            # Use gemini-2.5-flash-tts which is the latest standard
            model_name = "gemini-2.5-flash-tts"
            response = client.models.generate_content(
                model=model_name,
                contents=[TEXT],
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name
                            )
                        )
                    ),
                ),
            )

            # Extract audio data
            # Check response structure. Usually response.candidates[0].content.parts[0].inline_data.data
            if response.candidates and response.candidates[0].content.parts:
                audio_bytes = response.candidates[0].content.parts[0].inline_data.data
                with open(filepath, "wb") as f:
                    f.write(audio_bytes)
                print(f"Saved {filename}")
            else:
                print(f"No audio content for {voice_name}")

        except Exception as e:
            print(f"Error generating {voice_name}: {e}")


if __name__ == "__main__":
    generate_samples()
