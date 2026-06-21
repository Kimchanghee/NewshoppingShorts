"""
Voice sample generator using Gemini TTS API.
Reads voice profiles from voice_profiles.py and generates WAV samples
for each voice using its sample_text.
"""
import os
import re
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

TTS_MODEL = "gemini-3.1-flash-tts-preview"
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
    legacy_key = SecretsManager.get_api_key("gemini")
    if legacy_key and legacy_key not in keys:
        keys.append(legacy_key)
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
    clients = [{"index": i + 1, "client": genai.Client(api_key=k)} for i, k in enumerate(api_keys)]

    pending = []
    for profile in VOICE_PROFILES:
        filepath = os.path.join(VOICE_DIR, f"{profile['id']}.wav")
        if os.path.exists(filepath):
            print(f"  [{profile['id']}] SKIP (exists)")
        else:
            pending.append(profile)

    print(f"Generating {len(pending)} voice samples in {VOICE_DIR}")

    generated_count = 0
    pending_index = 0
    retry_counts = {}
    while pending_index < len(pending):
        if not clients:
            print("ERROR: All configured Gemini API keys were rejected. Add a valid key and rerun this script.")
            break

        profile = pending[pending_index]
        voice_id = profile["id"]
        voice_name = profile["voice_name"]
        sample_text = (
            "Say in Korean with a natural shopping-shorts narrator voice: "
            f"{profile['sample_text']}"
        )
        label = profile["label"]
        filepath = os.path.join(VOICE_DIR, f"{voice_id}.wav")

        client_slot = clients[generated_count % len(clients)]
        client = client_slot["client"]
        print(f"  [{voice_id}] {label} ({voice_name}) - generating... (key {client_slot['index']})")

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
                generated_count += 1
                pending_index += 1
            else:
                print(f"  [{voice_id}] FAIL - no audio in response")
                retry_counts[voice_id] = retry_counts.get(voice_id, 0) + 1
                if retry_counts[voice_id] <= 2:
                    print(f"  [{voice_id}] retrying after empty audio response...")
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                pending_index += 1

        except Exception as e:
            print(f"  [{voice_id}] ERROR - {e}")
            if "API_KEY_INVALID" in str(e) or "API key expired" in str(e) or "API key not valid" in str(e):
                print(f"  [{voice_id}] key {client_slot['index']} disabled for this run")
                clients = [slot for slot in clients if slot is not client_slot]
                continue
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                retry_counts[voice_id] = retry_counts.get(voice_id, 0) + 1
                if retry_counts[voice_id] <= 4:
                    retry_delay = RATE_LIMIT_WAIT
                    match = re.search(r"retryDelay': '(\d+)s'", str(e))
                    if match:
                        retry_delay = max(retry_delay, int(match.group(1)) + 2)
                    print(f"  [{voice_id}] quota wait {retry_delay}s then retry")
                    time.sleep(retry_delay)
                    continue
            pending_index += 1

        # Wait between requests to avoid rate limiting
        if pending_index < len(pending) and clients:
            print(f"  ... waiting {RATE_LIMIT_WAIT}s (rate limit)...")
            time.sleep(RATE_LIMIT_WAIT)

    print("\nDone!")


if __name__ == "__main__":
    generate_samples()
