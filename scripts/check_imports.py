import sys
import os

print("Checking imports...")
try:
    import audioop

    print(f"PASS: audioop imported: {audioop}")
except ImportError as e:
    print(f"FAIL: audioop: {e}")

try:
    from pydub import AudioSegment

    print("PASS: pydub.AudioSegment imported")
except ImportError as e:
    print(f"FAIL: pydub: {e}")

try:
    # Mimic the import chain that failed
    # app.batch_handler -> core.video.DynamicBatch -> core.video.batch -> processor -> VideoTool -> pydub
    import pydub.utils

    print("PASS: pydub.utils imported")
except ImportError as e:
    print(f"FAIL: pydub.utils: {e}")

print("Import check complete.")
