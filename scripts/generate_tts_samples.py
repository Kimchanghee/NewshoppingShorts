"""
Voice sample generator using Gemini TTS API.
Reads voice profiles from voice_profiles.py and generates WAV samples
for each voice using its sample_text.
"""
import os
import sys
import time
import wave

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from google import genai
from google.genai import types
from config.voice_profiles import VOICE_PROFILES
from utils.secrets_manager import SecretsManager

VOICE_DIR = os.path.join(PROJECT_ROOT, "resource", "voice_samples")
os.makedirs(VOICE_DIR, exist_ok=True)

TTS_MODEL = "gemini-2.5-flash-preview-tts"
RATE_LIMIT_WAIT = 12  # seconds between requests to avoid 429


def get_api_keys():
    """Get all API keys from SecretsManager or environment."""
    keys = []
    env_key = os.getenv("GEMINI_API_KEY", "")
    if env_key:
        keys.append(env_key)
    for i in range(1, 9):
        key = SecretsManager.get_api_key(f"gemini_api_{i}")
        if key and key not in keys:
            keys.append(key)
    return keys


def save_wav(filepath, audio_data):
    """Save audio data as WAV file."""
    if isinstance(audio_data, str):
        import base64
        audio_data = base64.b64decode(audio_data)

    if audio_data[:4] == b"RIFF":
        with open(filepath, "wb") as f:
            f.write(audio_data)
    else:
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)


def generate_samples():
    api_keys = get_api_keys()
    if not api_keys:
        print("ERROR: No API key found. Set GEMINI_API_KEY env var or add key via SecretsManager.")
        return

    print(f"Found {len(api_keys)} API key(s)")

    # Create clients for each key (rotate to avoid per-key rate limits)
    clients = [genai.Client(api_key=k) for k in api_keys]

    pending = []
    for profile in VOICE_PROFILES:
        filepath = os.path.join(VOICE_DIR, f"{profile['id']}.wav")
        if os.path.exists(filepath):
            print(f"  [{profile['id']}] SKIP (exists)")
        else:
            pending.append(profile)

    print(f"Generating {len(pending)} voice samples in {VOICE_DIR}")

    for idx, profile in enumerate(pending):
        voice_id = profile["id"]
        voice_name = profile["voice_name"]
        sample_text = profile["sample_text"]
        label = profile["label"]
        filepath = os.path.join(VOICE_DIR, f"{voice_id}.wav")

        client = clients[idx % len(clients)]
        print(f"  [{voice_id}] {label} ({voice_name}) - generating... (key {idx % len(clients) + 1})")

        try:
            response = client.models.generate_content(
                model=TTS_MODEL,
                contents=[sample_text],
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

            if response.candidates and response.candidates[0].content.parts:
                audio_bytes = response.candidates[0].content.parts[0].inline_data.data
                save_wav(filepath, audio_bytes)
                print(f"  [{voice_id}] OK ({len(audio_bytes)} bytes)")
            else:
                print(f"  [{voice_id}] FAIL - no audio in response")

        except Exception as e:
            print(f"  [{voice_id}] ERROR - {e}")

        # Wait between requests to avoid rate limiting
        if idx < len(pending) - 1:
            print(f"  ... waiting {RATE_LIMIT_WAIT}s (rate limit)...")
            time.sleep(RATE_LIMIT_WAIT)

    print("\nDone!")


if __name__ == "__main__":
    generate_samples()
