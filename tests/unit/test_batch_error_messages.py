"""Unit tests for batch error message translation/detail quality."""

from core.video.batch.utils import _get_short_error_message, _translate_error_message


class TestBatchErrorMessages:
    def test_translate_404_video_step_is_specific(self):
        message = _translate_error_message("HTTP 404 Not found", step="video")
        assert "영상 렌더링 리소스" in message

    def test_translate_404_tts_step_is_specific(self):
        message = _translate_error_message("status 404 not found", step="tts")
        assert "TTS 리소스" in message

    def test_translate_404_without_step_keeps_context_hint(self):
        message = _translate_error_message("404 Not found")
        assert "리소스를 찾을 수 없음 (404)" in message

    def test_short_error_message_uses_step_for_not_found(self):
        short_msg = _get_short_error_message(Exception("Not found"), step="video")
        assert short_msg == "렌더링파일없음"
