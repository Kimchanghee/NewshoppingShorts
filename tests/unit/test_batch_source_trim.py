from types import SimpleNamespace
from unittest.mock import patch

from core.video.batch import processor


def test_trim_source_video_for_batch_registers_temp_clip(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"input video")
    app = SimpleNamespace(_temp_downloaded_files=[])

    def fake_run(cmd, **kwargs):
        output = cmd[-1]
        with open(output, "wb") as f:
            f.write(b"trimmed video")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with patch("utils.ffmpeg.ensure_ffmpeg_on_path", return_value="ffmpeg"), patch(
        "core.video.batch.processor.subprocess.run", side_effect=fake_run
    ) as run_mock:
        output = processor._trim_source_video_for_batch(app, str(source), 35)

    cmd = run_mock.call_args.args[0]
    assert output.endswith(".mp4")
    assert output in app._temp_downloaded_files
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == "35.000"
    assert cmd[-1] == output
