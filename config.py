import random

# 기본 키는 비워 두고, UI/파일(api_keys_config.json)에서 불러옵니다.
GEMINI_API_KEYS = {}

# Gemini 2.5 모델 사용
GEMINI_VIDEO_MODEL = "gemini-2.5-pro"  # 비디오 분석 및 복잡한 추론 작업용
GEMINI_TEXT_MODEL = "gemini-2.5-flash"  # 빠른 텍스트 처리용
# 사용 가능 TTS 모델 (Gemini 2.5 TTS)
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"

# Gemini 2.5 파라미터 설정
GEMINI_THINKING_LEVEL = "low"  # low: 최소 레이턴시 (속도 우선), high: 최대 추론 깊이
GEMINI_MEDIA_RESOLUTION = "media_resolution_low"  # 비디오: low(70 tokens/frame), high(280 tokens/frame)
GEMINI_TEMPERATURE = 1.0  # Gemini 2.5 권장 기본값

FONTSIZE = 25
DAESA_GILI = 1.1

# Google Sheet 연동 사용 여부 (False이면 시트 관련 기능이 비활성화됩니다)

# Payment API Configuration
# 결제 API 설정
import os
PAYMENT_API_BASE_URL = os.getenv(
    "PAYMENT_API_BASE_URL",
    "https://ssmaker-auth-api-1049571775048.us-central1.run.app"
)

# Payment Checkout Configuration
# 결제 체크아웃 설정
CHECKOUT_POLL_INTERVAL = 5.0  # seconds - 결제 상태 확인 주기 (5초)
CHECKOUT_POLL_MAX_TRIES = 60  # 최대 확인 횟수 (5분 = 60 * 5초)

# PayApp 결제 연동 설정
# IMPORTANT: Never ship real PayApp credentials inside the client.
# These must be provided via environment variables in the backend/runtime.
PAYAPP_USERID = os.getenv("PAYAPP_USERID", "")
PAYAPP_LINKKEY = os.getenv("PAYAPP_LINKKEY", "")
PAYAPP_LINKVAL = os.getenv("PAYAPP_LINKVAL", "")
PAYAPP_API_URL = os.getenv("PAYAPP_API_URL", "https://api.payapp.kr/oapi/apiLoad.html")

# 구독 설정
SUBSCRIPTION_PRICE = 190000  # KRW - 프로 구독 월 가격
SUBSCRIPTION_DAYS = 30  # 구독 기간 (1개월)
