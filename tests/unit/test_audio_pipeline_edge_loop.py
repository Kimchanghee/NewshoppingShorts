import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from core.audio.pipeline import AudioPipeline, _run_coro_in_isolated_loop


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


def test_generate_tts_internal_skips_gemini_when_client_missing(monkeypatch, tmp_path):
    calls = {"edge": 0}

    class FakeAudio:
        channels = 2
        sample_width = 2
        raw_data = b"\0" * 44100

        @property
        def duration_seconds(self):
            return 1.0

        def __len__(self):
            return 1000

        def export(self, output, format, parameters=None):
            Path(output).write_bytes(b"RIFFfakewav")

    def fake_edge(self, text, output_path):
        calls["edge"] += 1
        Path(output_path).write_bytes(b"RIFFfakewav")

    app = SimpleNamespace(
        genai_client=None,
        tts_output_dir=str(tmp_path),
        config=SimpleNamespace(GEMINI_TTS_MODEL="gemini-tts-test"),
        edge_tts_voice="ko-KR-HyunsuMultilingualNeural",
    )
    pipeline = AudioPipeline(app)

    monkeypatch.setattr(AudioPipeline, "_generate_edge_tts_wav", fake_edge)
    monkeypatch.setattr("core.audio.pipeline.AudioSegment.from_file", lambda *_args, **_kwargs: FakeAudio())
    monkeypatch.setattr("core.video.batch.audio_utils._prepare_segment", lambda segment: segment)
    monkeypatch.setattr("core.video.batch.audio_utils._ensure_pydub_converter", lambda: None)
    monkeypatch.setattr(pipeline, "_apply_speed", lambda path, *_args: (path, 1.0))
    monkeypatch.setattr(
        pipeline,
        "_analyze_with_whisper",
        lambda path, script, segments, duration: (
            [{"idx": 0, "start": 0.0, "end": duration, "text": script}],
            "test_fallback",
            0.0,
            duration,
        ),
    )

    result = pipeline._generate_tts_internal("test script", "Charon", ["test script"])

    assert calls["edge"] == 1
    assert Path(result.audio_path).exists()
    assert result.timestamps_source == "test_fallback"
