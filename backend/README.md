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
