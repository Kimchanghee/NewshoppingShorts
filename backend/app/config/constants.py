"""
Application Constants and Configuration
중앙 집중식 설정 상수
"""

# Trial/Registration Settings
EARLY_BIRD_WORK_COUNT = 5  # 얼리버드 체험판 작업 수
FREE_TRIAL_WORK_COUNT = 2  # 기본 체험판 작업 수 (registration.py와 동기화)
DEFAULT_TRIAL_WORK_COUNT = 2  # 기본 체험판 작업 수
DEFAULT_TRIAL_DAYS = 365   # 체험판 유효 기간 (일)

# Security Settings
MAX_LOGIN_ATTEMPTS = 5  # 최대 로그인 시도 횟수
LOGIN_ATTEMPT_WINDOW_MINUTES = 15  # 로그인 시도 제한 시간 (분)
MAX_IP_ATTEMPTS = 10  # IP별 최대 로그인 시도 횟수

# Password Policy
MIN_PASSWORD_LENGTH = 8
BCRYPT_ROUNDS = 14  # bcrypt 해싱 rounds (2^14 iterations)

# Session Settings
SESSION_EXPIRY_DAYS = 30  # 세션 만료 기간 (일)
JWT_EXPIRY_HOURS = 24  # JWT 토큰 만료 시간 (시간)

# Admin Dashboard
ADMIN_REFRESH_INTERVAL_MS = 60000  # 관리자 대시보드 자동 새로고침 (밀리초)
ADMIN_PAGE_SIZE_DEFAULT = 50  # 기본 페이지 크기
ADMIN_PAGE_SIZE_MAX = 100  # 최대 페이지 크기

# Rate Limiting
REGISTRATION_RATE_LIMIT = "5/hour"  # 회원가입 요청 제한
ADMIN_LIST_RATE_LIMIT = "100/hour"  # 관리자 목록 조회 제한
ADMIN_ACTION_RATE_LIMIT = "50/hour"  # 관리자 작업 제한
