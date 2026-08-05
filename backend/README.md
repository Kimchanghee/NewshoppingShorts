# SSMaker 인증 서버 (FastAPI + Google Cloud SQL)

기존 HTTP 서버를 Google Cloud SQL과 FastAPI 백엔드로 마이그레이션한 인증 시스템입니다.

## 빠른 시작

### 1. 로컬 개발 환경 설정

```bash
# 가상 환경 생성
python -m venv venv

# 가상 환경 활성화
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 데이터베이스 정보 입력

# JWT Secret Key 생성
openssl rand -hex 32
# 결과를 .env의 JWT_SECRET_KEY에 입력

# 스키마 마이그레이션 (MySQL/PostgreSQL 공통)
alembic upgrade head

# 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. API 테스트

브라우저에서 접속:
- http://localhost:8000/ - 기본 엔드포인트
- http://localhost:8000/health - 헬스 체크
- http://localhost:8000/docs - Swagger UI (API 문서)

### 3. 사용자 생성

```bash
# create_user.py 사용
python create_user.py <username> <password>

# 예시
python create_user.py testuser test123
```

## API 엔드포인트

### 관리자 대시보드 세션

- `POST /user/admin/session/login` — `{ "password": "..." }`로 로그인
- `GET /user/admin/session/verify` — Bearer 관리자 세션 확인
- `POST /user/admin/session/logout` — 현재 관리자 세션 폐기
- 보호된 관리자 API는 Bearer 관리자 세션을 사용하며, 기존 운영 자동화는
  `X-Admin-API-Key`도 계속 사용할 수 있습니다.

관리자 비밀번호 원문은 서버에 저장하지 않습니다. `.env`에는 bcrypt
`ADMIN_PASSWORD_HASH`와 별도의 `ADMIN_SESSION_PEPPER`만 설정해야 합니다.

### POST /user/work/use-v2

완료된 작업 횟수를 원자적으로 차감합니다. 요청마다 UUID `idempotency_key`를
보내며, 동일 사용자의 동일 UUID 재시도는 처음 결과를 반환하고 다시 차감하지
않습니다. 기존 `/user/work/use`는 구버전 클라이언트를 위해 유지됩니다.

새 데스크톱 클라이언트는 `/user/work/reserve-v3`로 슬롯을 예약하고, 완성 영상이
안전하게 저장된 경우에만 `/user/work/finalize-v3`로 사용량을 확정합니다. 실패·건너뜀은
`/user/work/release-v3`로 예약을 해제합니다. 모든 전환은 영속 UUID 기준으로 멱등이며,
4시간이 지난 미완료 예약은 서버가 회수합니다.

### POST /v1/computer-use/jobs

Computer Use 작업은 기본적으로 비활성화되어 있으며, 전용 브리지 키와 격리된
절대 작업 경로를 설정한 경우에만 실행됩니다. 데스크톱 앱은 자유 형식 프롬프트를
전송하지 않고 다음 서버 소유 템플릿 ID 중 하나만 요청합니다.

- `setup_all`
- `setup_target_<대상 ID>` (예: `setup_target_youtube`)
- `setup_step_<단계 ID>` (예: `setup_step_youtube`)

운영 서버의 `COMPUTER_USE_PROMPT_TEMPLATES_JSON`에는 실제 사용하는 모든 ID와
20자 이상의 프롬프트를 등록해야 합니다. 자유 형식 프롬프트는 명시적으로
`COMPUTER_USE_ALLOW_FREEFORM_PROMPTS=true`를 설정하지 않는 한 거부됩니다.

## 운영 배포 순서

`deploy.sh`와 `deploy_to_cloudrun.bat`는 새 리비전을 무트래픽으로 빌드한 뒤 동일
이미지의 Cloud Run Job에서 `alembic upgrade head`를 실행합니다. 마이그레이션이
성공한 경우에만 새 리비전으로 트래픽을 100% 전환합니다. Vercel 배포도
`vercel.json`의 build command에서 마이그레이션 실패 시 배포를 중단합니다.

배포 전에 Secret Manager에 `ADMIN_PASSWORD_HASH`(bcrypt)와 32자 이상의
`ADMIN_SESSION_PEPPER`를 포함한 `.env.example`의 운영 비밀값을 모두 등록해야 합니다.

### POST /user/login/god
로그인 (기존 클라이언트와 호환)

**요청:**
```json
{
  "id": "username",
  "pw": "password",
  "key": "ssmaker",
  "ip": "127.0.0.1",
  "force": false
}
```

**응답 (성공):**
```json
{
  "status": true,
  "data": {
    "data": {"id": "123"},
    "ip": "127.0.0.1",
    "token": "eyJhbGci..."
  }
}
```

**응답 (실패):**
```json
{
  "status": "EU001",
  "message": "EU001"
}
```

**에러 코드:**
- `EU001`: 잘못된 로그인 정보
- `EU002`: 구독 만료
- `EU003`: 중복 로그인
- `EU004`: 서버 강제 종료
- `EU005`: 너무 많은 로그인 시도

### POST /user/logout/god
로그아웃

**요청:**
```json
{
  "id": "123",
  "key": "jwt_token_here"
}
```

### POST /user/login/god/check
세션 체크 (5초마다 호출)

**요청:**
```json
{
  "id": "123",
  "key": "jwt_token_here",
  "ip": "127.0.0.1"
}
```

## 프로젝트 구조

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 앱
│   ├── config.py            # 환경 변수 설정
│   ├── database.py          # DB 연결
│   ├── models/              # SQLAlchemy 모델
│   │   ├── user.py
│   │   ├── session.py
│   │   └── login_attempt.py
│   ├── schemas/             # Pydantic 스키마
│   │   └── auth.py
│   ├── routers/             # API 라우터
│   │   └── auth.py
│   ├── services/            # 비즈니스 로직
│   │   └── auth_service.py
│   └── utils/               # 유틸리티
│       ├── password.py      # bcrypt
│       └── jwt_handler.py   # JWT
├── requirements.txt
├── Dockerfile
├── .env.example
└── CLOUD_SQL_SETUP_GUIDE.md # 배포 가이드
```

## 데이터베이스 스키마

### users 테이블
- `id`: INT (PK, AUTO_INCREMENT)
- `username`: VARCHAR(50) UNIQUE
- `password_hash`: VARCHAR(255) (bcrypt)
- `subscription_expires_at`: TIMESTAMP NULL
- `is_active`: BOOLEAN
- `last_login_at`: TIMESTAMP
- `last_login_ip`: VARCHAR(45)

### sessions 테이블
- `id`: INT (PK)
- `user_id`: INT (FK → users.id)
- `token_jti`: VARCHAR(36) UNIQUE (JWT ID)
- `ip_address`: VARCHAR(45)
- `expires_at`: TIMESTAMP
- `is_active`: BOOLEAN

### login_attempts 테이블
- `id`: INT (PK)
- `username`: VARCHAR(50)
- `ip_address`: VARCHAR(45)
- `attempted_at`: TIMESTAMP
- `success`: BOOLEAN

## 보안 기능

- ✅ bcrypt 비밀번호 해싱 (12 라운드)
- ✅ JWT 토큰 기반 인증 (72시간 만료)
- ✅ IP 기반 세션 검증
- ✅ Rate Limiting (5회 시도 / 15분)
- ✅ SQL Injection 방지 (SQLAlchemy ORM)
- ✅ HTTPS 지원 (Cloud Run 자동)

## 배포

### Google Cloud Run 배포

상세한 배포 가이드는 [CLOUD_SQL_SETUP_GUIDE.md](CLOUD_SQL_SETUP_GUIDE.md)를 참조하세요.

**요약:**
1. Google Cloud SQL 인스턴스 생성
2. 데이터베이스 및 테이블 생성
3. Docker 이미지 빌드 및 푸시
4. Cloud Run 서비스 배포
5. 환경 변수 및 Secret Manager 설정

```bash
# Docker 이미지 빌드
docker build -t gcr.io/PROJECT_ID/ssmaker-auth:v1 .

# 이미지 푸시
docker push gcr.io/PROJECT_ID/ssmaker-auth:v1

# Cloud Run 배포 (웹 콘솔 사용 권장)
# https://console.cloud.google.com/run
```

## 환경 변수

필수 환경 변수 (`.env` 파일):

```env
DB_HOST=your_cloud_sql_ip
DB_PORT=3306
DB_USER=ssmaker_user
DB_PASSWORD=your_password
DB_NAME=ssmaker_auth
JWT_SECRET_KEY=your_secret_key
JWT_EXPIRATION_HOURS=72
```

선택 환경 변수:
```env
BCRYPT_ROUNDS=12
MAX_LOGIN_ATTEMPTS=5
LOGIN_ATTEMPT_WINDOW_MINUTES=15
ALLOWED_ORIGINS=*
```

## 트러블슈팅

### 데이터베이스 연결 오류
```
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (2003, "Can't connect...")
```
**해결:**
- DB_HOST가 정확한지 확인
- Cloud SQL 승인된 네트워크에 IP 추가
- Cloud Run에서는 프라이빗 IP 사용

### JWT 토큰 오류
```
ValueError: Token expired
```
**해결:**
- 클라이언트에서 재로그인
- JWT_EXPIRATION_HOURS 확인

### Rate Limiting 오류
```
{"status": "EU005", "message": "너무 많은 로그인 시도..."}
```
**해결:**
- 15분 대기 후 재시도
- login_attempts 테이블에서 기록 확인 및 삭제 (관리자만)

## 라이선스

이 프로젝트는 SSMaker의 일부입니다.

## 지원

문제가 발생하면 [CLOUD_SQL_SETUP_GUIDE.md](CLOUD_SQL_SETUP_GUIDE.md)의 트러블슈팅 섹션을 참조하세요.
