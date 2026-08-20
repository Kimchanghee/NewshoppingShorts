from user_facing_errors import (
    friendly_error_title,
    sanitize_user_message,
    sanitize_user_title,
)
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


def test_youtube_oauth_missing_message_is_customer_friendly():
    raw = (
        "YouTube OAuth token is missing or invalid. Reconnect the YouTube channel "
        "before consuming pending queue items."
    )

    message = sanitize_user_message(raw)

    assert friendly_error_title(raw) == "YouTube 업로드 권한 만료"
    assert message == "설정에서 YouTube를 다시 연결해 주세요."
    assert "OAuth token" not in message
    assert "pending queue" not in message


def test_active_job_english_exception_is_fully_localized():
    raw = (
        "Only one active job is allowed. Finish or clear the current "
        "waiting/processing item first."
    )

    message = sanitize_user_message(raw)

    assert "대기 중이거나 진행 중인 영상 작업" in message
    assert "Only one" not in message
    assert "waiting" not in message
    assert "processing" not in message


def test_internal_login_prefix_is_removed_but_korean_guidance_is_kept():
    raw = (
        "[caller.rest/LOGIN_REJECTED]\n"
        "아이디 또는 비밀번호가 맞는지 다시 확인해 주세요."
    )

    message = sanitize_user_message(raw)

    assert message == "아이디 또는 비밀번호가 맞는지 다시 확인해 주세요."
    assert "caller.rest" not in message
    assert "LOGIN_REJECTED" not in message


def test_login_rate_limit_is_fully_localized():
    raw = "[caller.rest/LOGIN_RATE_LIMITED] Too many login attempts. Please try again later."

    message = sanitize_user_message(raw)

    assert friendly_error_title(raw) == "잠시 후 다시 로그인해 주세요"
    assert "로그인 시도가 잠시 제한" in message
    assert "Too many" not in message
    assert "LOGIN_RATE_LIMITED" not in message


def test_legacy_error_code_and_request_id_are_not_shown():
    raw = "[EU001] 아이디 또는 비밀번호를 확인해 주세요.\n요청 ID: req-1234"

    message = sanitize_user_message(raw)

    assert message == "아이디 또는 비밀번호를 확인해 주세요."
    assert "EU001" not in message
    assert "req-1234" not in message


def test_startup_recovery_code_and_module_name_are_removed():
    raw = "- [ST-U204] integration.inpock: 해당 기능을 다시 설정해 주세요."

    message = sanitize_user_message(raw)

    assert message == "- 해당 기능을 다시 설정해 주세요."
    assert "ST-U204" not in message
    assert "integration.inpock" not in message


def test_mixed_korean_and_raw_exception_keeps_only_actionable_copy():
    raw = "설정을 저장하지 못했어요.\nPermissionError: [WinError 5] Access is denied"

    message = sanitize_user_message(raw)

    assert message == "설정을 저장하지 못했어요."
    assert "PermissionError" not in message
    assert "WinError" not in message
    assert "Access is denied" not in message


def test_unknown_english_exception_falls_back_to_korean():
    raw = "Unexpected provider invocation failed inside worker bridge"

    message = sanitize_user_message(raw, fallback="작업을 완료하지 못했어요.")

    assert message == "작업을 완료하지 못했어요."


def test_safe_product_names_and_output_path_are_not_removed():
    raw = "YouTube 연결을 완료했어요.\n저장 위치: C:\\Videos\\result.mp4"

    assert sanitize_user_message(raw) == raw


def test_developer_facing_title_is_replaced():
    assert sanitize_user_title("PermissionError: Access denied", fallback="오류") == "오류"
    assert sanitize_user_title("???ㅻ쪟", fallback="오류") == "오류"


def test_sourcing_failure_hides_search_providers_and_internal_workflow():
    raw = (
        "상품 영상 검색에 실패했어요.\n"
        "원인: 검색 사이트가 로그인 또는 안티봇 확인 화면을 표시했습니다.\n"
        "해결: 열린 Chrome에서 해당 사이트에 로그인한 뒤 다시 검색해 주세요.\n"
        "검색 내역: Douyin: 로그인/차단 1회 / Xiaohongshu: 결과 없음 1회 / "
        "Kuaishou: 재생 URL 없음 1회 / Bing: 결과 없음 3회 / "
        "Brave Search: 요청 제한 1회 / DuckDuckGo: 봇 차단 1회\n"
        "후속 단계: 편집, YouTube 업로드, Linktree 등록을 시작하지 않았습니다."
    )

    message = sanitize_user_message(raw)

    assert message == (
        "상품 영상을 찾지 못했어요.\n"
        "잠시 후 다시 시도하거나 다른 상품 링크를 사용해 주세요."
    )
    for internal_detail in (
        "Douyin",
        "Xiaohongshu",
        "Kuaishou",
        "Bing",
        "Brave",
        "DuckDuckGo",
        "검색 내역",
        "후속 단계",
        "안티봇",
        "YouTube",
        "Linktree",
    ):
        assert internal_detail not in message
