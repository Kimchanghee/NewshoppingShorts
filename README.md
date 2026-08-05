# NewshoppingShortsMaker

상품 URL이나 소스 영상을 바탕으로 쇼핑 쇼츠를 제작하고 게시하는 PyQt6 데스크톱 애플리케이션입니다. 한국어 TTS, 자막, 영상 편집, YouTube·Instagram·TikTok·Threads·Linktree 연동을 한 흐름에서 다룹니다.

## 세 가지 핵심 제작 의도

1. **한글과 상품명이 깨지지 않는 안정적인 영상 제작**
   프로세스 시작 시 UTF-8 환경을 적용하고, 제목·설명·자막을 게시 전에 검증합니다.
2. **같은 상품이나 소스 영상을 반복 게시하지 않는 자동화**
   상품 키, 소스 URL, 영상 프레임 해시를 영구 기록하며 원자 저장과 백업 복구로 중복 차단 상태를 보호합니다.
3. **상품과 실제로 관련 있는 좋은 소스 영상 사용**
   공식 쿠팡 URL만 받고, 후보 영상 자체의 제목·설명 근거가 상품명·다국어 키워드와 90% 이상 일치할 때만 자동 게시 흐름에 넣습니다.

## 주요 기능

- 쿠팡 상품 URL 기반 쇼츠 제작
- Douyin, Kuaishou, Xiaohongshu, Bilibili 소스 검색 및 품질 검증
- 중국어 자막 감지·블러, 한국어 자막과 TTS 생성
- FFmpeg 기반 세로 영상 편집 및 합성
- YouTube 등 소셜 채널 업로드와 Linktree 게시
- 사용량·구독 확인, 관리자 대시보드
- 중복 업로드 차단과 실패 시 안전 중단

## 요구 사항

- Python 3.11 이상
- FFmpeg와 ffprobe
- PyQt6
- Tesseract OCR 또는 RapidOCR
- Gemini API 키
- 선택 사항: NVIDIA GPU와 호환되는 CuPy

Windows에서 Tesseract는 다음 명령으로 설치할 수 있습니다.

```powershell
winget install UB-Mannheim.TesseractOCR
```

## 설치와 실행

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/startup_validation.py
python main.py
```

API 키와 채널 인증은 애플리케이션의 설정 화면에서 등록할 수 있습니다. 비밀값을 저장소에 직접 기록하지 마세요.

## 안전 동작

- 작업 횟수는 렌더링 전에 서버에서 멱등 키로 차감합니다. 네트워크 응답이 유실되어 재시도해도 같은 작업이 중복 차감되지 않습니다.
- URL은 HTTPS, 공식 도메인, 공개 IP 여부를 확인합니다. 내부망·메타데이터 주소·유사 도메인은 거부합니다.
- 중복 기록 파일과 백업이 모두 손상되면 자동 업로드를 중단합니다.
- Linktree 게시가 필요한 설정에서 게시가 실패하면 소셜 업로드도 진행하지 않습니다.
- 서버 Computer Use는 기본 비활성화이며, 별도 브리지 키와 서버 템플릿이 필요합니다.

## 검증

```powershell
# 데스크톱 테스트
python -m pytest tests/unit tests/integration -q

# 백엔드 테스트
python -m pytest backend/tests -q

# 관리자 대시보드
cd program-admin-dashboard
npm ci
npm run verify
```

빌드 전에는 아래 검사도 권장합니다.

```powershell
python scripts/check_utf8.py
python scripts/validate_build.py
python -m pip check
```

## 프로젝트 구조

```text
app/                       애플리케이션 조정 계층
ui/                        PyQt6 화면과 컴포넌트
core/                      다운로드·소싱·영상 처리
managers/                  설정·업로드·중복 기록 관리
caller/                    백엔드 API 클라이언트
backend/                   FastAPI 백엔드와 Alembic 마이그레이션
program-admin-dashboard/   Next.js 관리자 대시보드
tests/                     데스크톱 단위·통합 테스트
```

자세한 구조는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), 빌드 안내는 [docs/BUILD_GUIDE.md](docs/BUILD_GUIDE.md)를 참고하세요.

## 문제 해결

- `FFmpeg not found`: FFmpeg의 `bin` 디렉터리를 `PATH`에 추가합니다.
- OCR을 찾지 못함: Tesseract 설치 후 `TESSERACT_CMD`를 확인합니다.
- 화면 없이 GUI 테스트: `QT_QPA_PLATFORM=offscreen` 환경 변수를 사용합니다.
- 소스 사이트 접근 제한: 해당 사이트에 한 번 직접 로그인한 뒤 저장된 브라우저 프로필로 다시 시도합니다.

## 라이선스

이 저장소의 배포 정책과 라이선스 파일을 따릅니다.
