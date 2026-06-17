import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from core.audio.pipeline import _run_coro_in_isolated_loop


def test_run_coro_in_isolated_loop_without_running_loop():
    async def sample():
        return 7

    assert _run_coro_in_isolated_loop(sample()) == 7


def test_run_coro_in_isolated_loop_with_running_loop():
    async def inner():
        return _run_coro_in_isolated_loop(asyncio.sleep(0, result=11))

    assert asyncio.run(inner()) == 11


def test_generate_edge_tts_wav_works_inside_running_loop(monkeypatch, tmp_path):
    output_path = tmp_path / "edge.wav"

    class FakeCommunicate:
        def __init__(self, text, voice):
            self.text = text
            self.voice = voice

        async def save(self, mp3_path):
            Path(mp3_path).write_bytes(b"fake-mp3")

    fake_module = SimpleNamespace(Communicate=FakeCommunicate)
    monkeypatch.setitem(sys.modules, "edge_tts", fake_module)

    class FakeAudio:
        def export(self, output, format):
            Path(output).write_bytes(b"RIFFfakewav")

    app = SimpleNamespace(edge_tts_voice="ko-KR-HyunsuMultilingualNeural")
    pipeline = SimpleNamespace(app=app)
    monkeypatch.setattr("core.audio.pipeline.AudioSegment.from_file", lambda *_args, **_kwargs: FakeAudio())

    async def inner():
        from core.audio.pipeline import AudioPipeline

        AudioPipeline._generate_edge_tts_wav(pipeline, "테스트", str(output_path))

    asyncio.run(inner())

    assert output_path.exists()
