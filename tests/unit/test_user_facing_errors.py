from user_facing_errors import sanitize_user_message, friendly_error_title
from app.batch_handler import BatchHandler


def test_gemini_permission_payload_is_customer_friendly():
    payload = {
        "reason": "gemini_api_keys_rejected",
        "blocking_reason": "All configured Gemini API keys were rejected by Google Generative Language API.",
        "invalid_aliases": [
            {
                "alias": "api_1",
                "http_status": 403,
                "google_status": "PERMISSION_DENIED",
                "google_code": 403,
                "message_summary": "Lightning dunning decision is restricted",
            }
        ],
        "missing_aliases": ["api_2", "api_3"],
    }

    message = sanitize_user_message(payload)
    title = friendly_error_title(payload)

    assert title == "Gemini API 키를 사용할 수 없어요"
    assert "Google에서 사용 권한을 거절" in message
    assert "api_1" not in message
    assert "PERMISSION_DENIED" not in message
    assert "http_status" not in message


def test_summer_coupang_status_hides_raw_key_diagnostics():
    handler = BatchHandler.__new__(BatchHandler)
    summary = {
        "reason": "gemini_api_keys_rejected",
        "blocking_reason": "All configured Gemini API keys were rejected by Google Generative Language API.",
        "invalid_aliases": [
            {
                "alias": "api_1",
                "http_status": 403,
                "google_status": "PERMISSION_DENIED",
                "google_code": 403,
                "message_summary": "Lightning dunning decision is restricted",
            }
        ],
        "missing_aliases": ["api_2"],
    }

    title, detail, level = handler._summer_run_result_status(summary, 3.2, 1)

    assert title == "Gemini API 키를 사용할 수 없어요"
    assert level == "error"
    assert "Google에서 사용 권한을 거절" in detail
    assert "api_1" not in detail
    assert "PERMISSION_DENIED" not in detail
    assert "message_summary" not in detail
