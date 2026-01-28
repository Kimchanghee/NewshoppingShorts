# Google Cloud SQL + Cloud Run 배포 가이드

이 문서는 Google Cloud 웹 콘솔에서 직접 설정하는 단계별 가이드입니다.

---

## 1단계: Google Cloud SQL 설정

### 1.1 Cloud SQL 인스턴스 생성

1. **Google Cloud Console 접속**
   - https://console.cloud.google.com/sql 접속
   - 프로젝트 선택 (없으면 생성)

2. **인스턴스 만들기**
   - "인스턴스 만들기" 버튼 클릭
   - **MySQL** 선택

3. **인스턴스 구성**
   ```
   인스턴스 ID: ssmaker-auth-db
   비밀번호: [강력한 비밀번호 입력 및 저장!]
   데이터베이스 버전: MySQL 8.0
   리전: asia-northeast3 (서울)
   영역 가용성: 단일 영역
   ```

4. **머신 구성**
   ```
   사전 설정 머신 유형: 공유 코어
   머신 유형: db-f1-micro (1vCPU, 0.6GB)
   스토리지 유형: SSD
   스토리지 용량: 10GB
   자동 스토리지 증가: 사용 설정
   고가용성: 사용 안 함 (비용 절감)
   ```

5. **"만들기" 클릭**
   - 인스턴스 생성 완료까지 5-10분 소요

### 1.2 네트워크 설정

1. **생성된 인스턴스 클릭**

2. **왼쪽 메뉴 "연결" 선택**

3. **공개 IP 설정**
   - "네트워킹" 탭 클릭
   - "공개 IP 주소" 체크박스 활성화
   - "승인된 네트워크 추가" 클릭
     ```
     이름: dev-machine
     네트워크: [본인 공개 IP 입력]
     ```
   - IP 확인 방법: https://ifconfig.me 접속
   - "완료" → "저장" 클릭

4. **프라이빗 IP 설정 (선택사항 - Cloud Run 사용 시 권장)**
   - "비공개 IP" 체크박스 활성화
   - VPC 네트워크 선택 또는 자동 생성
   - 프라이빗 IP 주소 메모 (예: 10.x.x.x)

### 1.3 데이터베이스 및 사용자 생성

1. **Cloud Shell에서 연결**
   - 인스턴스 개요 페이지
   - "Cloud Shell에서 연결" 버튼 클릭
   - root 비밀번호 입력

2. **SQL 명령 실행**
   ```sql
   -- 데이터베이스 생성
   CREATE DATABASE ssmaker_auth CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

   -- 애플리케이션 사용자 생성
   CREATE USER 'ssmaker_user'@'%' IDENTIFIED BY 'YOUR_STRONG_PASSWORD';

   -- 권한 부여
   GRANT ALL PRIVILEGES ON ssmaker_auth.* TO 'ssmaker_user'@'%';
   FLUSH PRIVILEGES;

   -- 데이터베이스 선택
   USE ssmaker_auth;
   ```

3. **테이블 생성**
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

4. **테스트 사용자 생성 (임시)**
   ```sql
   -- 비밀번호는 bcrypt로 해시해야 하므로 백엔드에서 생성
   -- 여기서는 플레이스홀더만 삽입
   INSERT INTO users (username, password_hash, is_active)
   VALUES ('testuser', 'TEMP_HASH', TRUE);

   -- 나중에 Python에서 올바른 해시로 업데이트:
   -- python3 -c "from passlib.hash import bcrypt; print(bcrypt.hash('test123'))"
   ```

5. **연결 정보 저장**
   - 인스턴스 개요 페이지에서 다음 정보 복사:
     - **공개 IP 주소**: 예: 34.64.123.456
     - **프라이빗 IP 주소**: 예: 10.20.30.40
     - **연결 이름**: 예: project-id:asia-northeast3:ssmaker-auth-db

---

## 2단계: 로컬 개발 환경 설정

### 2.1 환경 변수 설정

1. **backend 폴더에 `.env` 파일 생성**
   ```bash
   cd backend
   cp .env.example .env
   ```

2. **`.env` 파일 편집**
   ```env
   DB_HOST=34.64.123.456  # Cloud SQL 공개 IP
   DB_PORT=3306
   DB_USER=ssmaker_user
   DB_PASSWORD=YOUR_STRONG_PASSWORD
   DB_NAME=ssmaker_auth
   JWT_SECRET_KEY=<openssl rand -hex 32 결과>
   JWT_EXPIRATION_HOURS=72
   ```

3. **JWT Secret Key 생성**
   ```bash
   openssl rand -hex 32
   ```
   결과를 복사해서 JWT_SECRET_KEY에 입력

### 2.2 로컬 테스트

1. **가상 환경 생성 및 의존성 설치**
   ```bash
   cd backend
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate

   pip install -r requirements.txt
   ```

2. **FastAPI 서버 실행**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **브라우저에서 확인**
   - http://localhost:8000/ → {"status": "ok"}
   - http://localhost:8000/docs → Swagger UI

4. **테스트 사용자 비밀번호 업데이트**
   ```python
   # Python 콘솔 실행
   python

   from app.utils.password import hash_password
   hashed = hash_password("test123")
   print(hashed)
   # 출력된 해시를 복사
   ```

   ```sql
   -- MySQL에서 실행
   UPDATE users SET password_hash = '복사한_해시' WHERE username = 'testuser';
   ```

5. **로그인 테스트**
   - Swagger UI (http://localhost:8000/docs)에서 POST /user/login/god 테스트
   ```json
   {
     "id": "testuser",
     "pw": "test123",
     "key": "ssmaker",
     "ip": "127.0.0.1",
     "force": false
   }
   ```

---

## 3단계: Google Cloud Run 배포

### 3.1 Docker 이미지 빌드 및 푸시

1. **gcloud CLI 설치 확인**
   ```bash
   gcloud --version
   ```
   없으면: https://cloud.google.com/sdk/docs/install

2. **프로젝트 설정**
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   gcloud auth configure-docker
   ```

3. **이미지 빌드**
   ```bash
   cd backend
   docker build -t gcr.io/YOUR_PROJECT_ID/ssmaker-auth:v1 .
   ```

4. **이미지 푸시**
   ```bash
   docker push gcr.io/YOUR_PROJECT_ID/ssmaker-auth:v1
   ```

### 3.2 Google Secret Manager 설정

1. **Secret Manager API 활성화**
   - https://console.cloud.google.com/security/secret-manager
   - "API 사용 설정" 클릭

2. **보안 비밀 생성**
   - "보안 비밀 만들기" 버튼 클릭

   **db-password**:
   ```
   이름: db-password
   보안 비밀 값: YOUR_STRONG_PASSWORD
   ```

   **jwt-secret-key**:
   ```
   이름: jwt-secret-key
   보안 비밀 값: <openssl rand -hex 32 결과>
   ```

3. **"만들기" 클릭**

### 3.3 Cloud Run 서비스 배포

1. **Cloud Run 페이지 접속**
   - https://console.cloud.google.com/run

2. **"서비스 만들기" 클릭**

3. **컨테이너 이미지 선택**
   ```
   컨테이너 이미지 URL: gcr.io/YOUR_PROJECT_ID/ssmaker-auth:v1
   서비스 이름: ssmaker-auth
   리전: asia-northeast3 (서울)
   ```

4. **인증**
   ```
   인증되지 않은 호출 허용: 선택
   ```

5. **"컨테이너, 네트워킹, 보안" 확장**

   **컨테이너 탭**:
   - 컨테이너 포트: `8080`

   **환경 변수**:
   ```
   DB_HOST = 10.x.x.x  (Cloud SQL 프라이빗 IP)
   DB_PORT = 3306
   DB_USER = ssmaker_user
   DB_NAME = ssmaker_auth
   JWT_EXPIRATION_HOURS = 72
   ```

   **보안 비밀 참조**:
   - "보안 비밀 참조" 클릭
   - `db-password` → 환경 변수로 마운트 → `DB_PASSWORD`
   - `jwt-secret-key` → 환경 변수로 마운트 → `JWT_SECRET_KEY`

   **연결 탭**:
   - "Cloud SQL 연결" 섹션
   - "연결 추가" 클릭
   - Cloud SQL 인스턴스 선택: `ssmaker-auth-db`

6. **"만들기" 클릭**
   - 배포 완료까지 2-3분 소요

7. **URL 확인**
   - 배포 완료 후 URL 표시
   - 예: `https://ssmaker-auth-xxxxxxxxx-an.a.run.app`

### 3.4 배포 확인

1. **브라우저에서 테스트**
   ```
   https://ssmaker-auth-xxxxxxxxx-an.a.run.app/
   → {"status": "ok", "service": "SSMaker Auth API"}

   https://ssmaker-auth-xxxxxxxxx-an.a.run.app/health
   → {"status": "healthy"}
   ```

2. **로그 확인**
   - Cloud Run 서비스 페이지 → "로그" 탭
   - 요청/응답 로그 확인

---

## 4단계: 클라이언트 연결

### 4.1 클라이언트 코드 수정

1. **`caller/rest.py` 편집**
   ```python
   # Line 11: 서버 URL 변경
   main_server = 'https://ssmaker-auth-xxxxxxxxx-an.a.run.app/'
   ```

2. **앱 실행 및 로그인 테스트**
   - PyQt5 앱 실행
   - testuser / test123 로그인
   - 성공 시 메인 UI 표시

---

## 5단계: 프로덕션 사용자 추가

### 5.1 사용자 생성 스크립트

1. **`backend/create_user.py` 생성**
   ```python
   import sys
   from app.database import SessionLocal
   from app.models.user import User
   from app.utils.password import hash_password

   def create_user(username, password):
       db = SessionLocal()
       try:
           # 기존 사용자 확인
           existing = db.query(User).filter(User.username == username).first()
           if existing:
               print(f"사용자 '{username}' 이미 존재합니다.")
               return

           # 새 사용자 생성
           user = User(
               username=username,
               password_hash=hash_password(password),
               is_active=True
           )
           db.add(user)
           db.commit()
           print(f"사용자 '{username}' 생성 완료!")
       finally:
           db.close()

   if __name__ == "__main__":
       if len(sys.argv) != 3:
           print("사용법: python create_user.py <username> <password>")
           sys.exit(1)

       create_user(sys.argv[1], sys.argv[2])
   ```

2. **사용자 추가**
   ```bash
   cd backend
   python create_user.py newuser password123
   ```

---

## 6단계: 모니터링 및 유지보수

### 6.1 Cloud SQL 모니터링

1. **Cloud SQL 콘솔**
   - https://console.cloud.google.com/sql
   - 인스턴스 클릭 → "모니터링" 탭

2. **확인 항목**
   - CPU 사용률
   - 메모리 사용률
   - 연결 수
   - 쿼리 성능

### 6.2 Cloud Run 모니터링

1. **Cloud Run 콘솔**
   - https://console.cloud.google.com/run
   - 서비스 클릭 → "측정항목" 탭

2. **확인 항목**
   - 요청 수
   - 지연 시간
   - 오류율
   - 인스턴스 수

### 6.3 로그 분석

1. **Cloud Logging**
   - https://console.cloud.google.com/logs
   - 리소스 → Cloud Run 리비전 선택
   - 로그 스트림 확인

2. **알림 설정**
   - Cloud Monitoring → 알림 → 정책 만들기
   - 조건:
     - Cloud Run 오류율 > 5%
     - Cloud SQL 연결 수 > 80%
     - 응답 시간 > 2초

### 6.4 백업 설정

1. **Cloud SQL 자동 백업**
   - Cloud SQL 인스턴스 → "백업" 탭
   - "자동 백업 사용 설정" 활성화
   - 백업 시간 선택
   - 보존 기간: 7일

---

## 트러블슈팅

### 문제 1: 클라이언트에서 연결 안 됨

**해결:**
1. Cloud Run URL이 정확한지 확인
2. CORS 설정 확인 (`app/main.py`)
3. Cloud Run 로그에서 오류 확인

### 문제 2: 데이터베이스 연결 실패

**해결:**
1. Cloud SQL 연결 설정 확인
2. 프라이빗 IP 사용 시 VPC 네트워크 연결 확인
3. DB_HOST 환경 변수 값 확인

### 문제 3: JWT 토큰 오류

**해결:**
1. JWT_SECRET_KEY가 백엔드와 일치하는지 확인
2. 토큰 만료 시간 확인
3. IP 주소 변경 시 재로그인

---

## 비용 최적화

- **Cloud SQL**: db-f1-micro (~$15/월)
- **Cloud Run**: 무료 할당량 활용 (~$5/월)
- **총 예상 비용**: ~$20-25/월

**절감 팁**:
1. Cloud SQL 자동 백업 보존 기간 단축 (7일 → 3일)
2. Cloud Run 최소 인스턴스 수 0으로 설정
3. 사용하지 않을 때 Cloud SQL 중지 (개발 환경)

---

## 추가 리소스

- [Google Cloud SQL 문서](https://cloud.google.com/sql/docs)
- [Google Cloud Run 문서](https://cloud.google.com/run/docs)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [SQLAlchemy 문서](https://docs.sqlalchemy.org/)
