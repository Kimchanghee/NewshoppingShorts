# 빠른 시작 가이드 (로컬 개발)

Google Cloud 없이 로컬 환경에서 바로 테스트하는 방법입니다.

## 사전 준비

- Python 3.11 이상
- MySQL 8.0 (로컬 설치 또는 Docker)

---

## 1단계: 로컬 MySQL 설정

### 옵션 A: Docker 사용 (권장)

```bash
# MySQL 컨테이너 실행
docker run --name ssmaker-mysql \
  -e MYSQL_ROOT_PASSWORD=rootpassword \
  -e MYSQL_DATABASE=ssmaker_auth \
  -e MYSQL_USER=ssmaker_user \
  -e MYSQL_PASSWORD=ssmaker123 \
  -p 3306:3306 \
  -d mysql:8.0

# 컨테이너 시작 대기 (10초)
sleep 10
```

### 옵션 B: 기존 MySQL 사용

기존에 설치된 MySQL 사용:

```sql
-- MySQL에 접속
mysql -u root -p

-- 데이터베이스 생성
CREATE DATABASE ssmaker_auth CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 사용자 생성
CREATE USER 'ssmaker_user'@'localhost' IDENTIFIED BY 'ssmaker123';
GRANT ALL PRIVILEGES ON ssmaker_auth.* TO 'ssmaker_user'@'localhost';
FLUSH PRIVILEGES;
```

---

## 2단계: 테이블 생성

```bash
# MySQL에 접속
mysql -u ssmaker_user -p ssmaker_auth
# 비밀번호: ssmaker123

# 또는 Docker 사용 시:
docker exec -it ssmaker-mysql mysql -u ssmaker_user -pssmaker123 ssmaker_auth
```

SQL 실행:

```sql
-- users 테이블
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    subscription_expires_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMP NULL,
    last_login_ip VARCHAR(45) NULL,
    INDEX idx_username (username),
    INDEX idx_active_subscription (is_active, subscription_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- sessions 테이블
CREATE TABLE sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token_jti VARCHAR(36) UNIQUE NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_token_jti (token_jti),
    INDEX idx_user_active (user_id, is_active),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- login_attempts 테이블
CREATE TABLE login_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT FALSE,
    INDEX idx_username_time (username, attempted_at),
    INDEX idx_ip_time (ip_address, attempted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

확인:

```sql
SHOW TABLES;
-- users, sessions, login_attempts 세 테이블이 보여야 함
```

---

## 3단계: 백엔드 설정

```bash
cd backend

# 가상 환경 생성
python -m venv venv

# 가상 환경 활성화
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

---

## 4단계: 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env
```

`.env` 파일 편집:

```env
# 로컬 MySQL (Docker 사용 시)
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=ssmaker_user
DB_PASSWORD=ssmaker123
DB_NAME=ssmaker_auth

# JWT Secret Key 생성
JWT_SECRET_KEY=your_generated_key_here
JWT_EXPIRATION_HOURS=72

# 보안 설정 (개발 환경)
BCRYPT_ROUNDS=12
MAX_LOGIN_ATTEMPTS=5
LOGIN_ATTEMPT_WINDOW_MINUTES=15

# CORS (개발 환경)
ALLOWED_ORIGINS=*
```

JWT Secret Key 생성:

```bash
# Windows PowerShell:
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})

# Linux/Mac:
openssl rand -hex 32
```

생성된 키를 `.env`의 `JWT_SECRET_KEY`에 복사

---

## 5단계: 테스트 사용자 생성

```bash
python create_user.py testuser test123
```

출력:

```
✅ 사용자 'testuser' 생성 완료!
   사용자 ID: 1
   생성일: 2026-01-24 17:30:00
   구독: 무제한
```

---

## 6단계: 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

출력:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

---

## 7단계: API 테스트

### 브라우저 테스트

1. http://localhost:8000/ → `{"status": "ok"}`
2. http://localhost:8000/health → `{"status": "healthy"}`
3. http://localhost:8000/docs → Swagger UI

### 자동 테스트 스크립트

```bash
# 새 터미널 열기
cd backend
python test_api.py
```

출력:

```
🧪 SSMaker Auth API 테스트
============================================================
1️⃣  루트 엔드포인트 테스트 (GET /)
   ✅ 성공: {'status': 'ok', 'service': 'SSMaker Auth API'}

2️⃣  헬스 체크 테스트 (GET /health)
   ✅ 성공: {'status': 'healthy'}

...

🎉 모든 테스트 통과!
```

### cURL 테스트

```bash
# 로그인
curl -X POST http://localhost:8000/user/login/god \
  -H "Content-Type: application/json" \
  -d '{
    "id": "testuser",
    "pw": "test123",
    "key": "ssmaker",
    "ip": "127.0.0.1",
    "force": false
  }'
```

응답:

```json
{
  "status": true,
  "data": {
    "data": {"id": "1"},
    "ip": "127.0.0.1",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

---

## 8단계: 클라이언트 연결

`caller/rest.py` 확인:

```python
# Line 11: 로컬 서버 URL 확인
main_server = 'http://localhost:8000/'  # 로컬 테스트용
```

PyQt5 앱 실행:

```bash
cd ..  # 프로젝트 루트로 이동
python ssmaker.py
```

로그인:
- ID: `testuser`
- PW: `test123`

---

## 유용한 명령어

### 사용자 관리

```bash
# 사용자 생성
python create_user.py newuser password123

# 사용자 목록 조회
python create_user.py --list

# 비밀번호 변경
python create_user.py --update testuser newpassword
```

### 데이터베이스 조회

```bash
# Docker MySQL 접속
docker exec -it ssmaker-mysql mysql -u ssmaker_user -pssmaker123 ssmaker_auth

# 또는 로컬 MySQL 접속
mysql -u ssmaker_user -p ssmaker_auth
```

```sql
-- 사용자 목록
SELECT id, username, is_active, last_login_at FROM users;

-- 활성 세션
SELECT s.id, u.username, s.ip_address, s.created_at, s.expires_at
FROM sessions s
JOIN users u ON s.user_id = u.id
WHERE s.is_active = TRUE;

-- 로그인 시도 내역
SELECT username, ip_address, attempted_at, success
FROM login_attempts
ORDER BY attempted_at DESC
LIMIT 10;
```

### 서버 재시작

```bash
# Ctrl+C로 서버 중지 후
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 트러블슈팅

### 포트 8000이 이미 사용 중

```bash
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac:
lsof -ti:8000 | xargs kill -9
```

또는 다른 포트 사용:

```bash
uvicorn app.main:app --reload --port 8001
```

### MySQL 연결 오류

```
sqlalchemy.exc.OperationalError: (2003, "Can't connect...")
```

**해결:**

```bash
# Docker 컨테이너 상태 확인
docker ps | grep ssmaker-mysql

# 컨테이너가 없으면 다시 실행
docker start ssmaker-mysql

# 또는 새로 생성
docker run --name ssmaker-mysql ...
```

### 테이블 없음 오류

```
sqlalchemy.exc.ProgrammingError: (1146, "Table 'ssmaker_auth.users' doesn't exist")
```

**해결:** 2단계의 SQL을 다시 실행

---

## 다음 단계

로컬 테스트가 완료되면:

1. [CLOUD_SQL_SETUP_GUIDE.md](CLOUD_SQL_SETUP_GUIDE.md) - Google Cloud 배포
2. [README.md](README.md) - 전체 문서
3. http://localhost:8000/docs - API 문서

---

## 정리

개발이 끝났을 때:

```bash
# 서버 중지: Ctrl+C

# 가상 환경 비활성화
deactivate

# Docker MySQL 중지 (선택사항)
docker stop ssmaker-mysql

# Docker MySQL 삭제 (데이터 포함)
docker rm -f ssmaker-mysql
```
