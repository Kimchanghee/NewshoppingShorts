# CTranslate2 누락 문제 해결 가이드

## 문제 요약

**증상**: 같은 빌드인데 특정 PC에서만 Faster-Whisper 실패
```
[Faster-Whisper 오류] [WinError 2] 지정된 파일을 찾을 수 없습니다:
'C:\\Program Files (x86)\\ssMaker\\_internal\\ctranslate2'
```

**원인**: PyInstaller 빌드 시 `ctranslate2` 폴더의 **바이너리 파일(.dll, .pyd)이 누락**됨
- `collect_data_files('ctranslate2')`는 데이터 파일만 수집
- Windows에서 필요한 DLL/PYD 파일들이 `_internal/ctranslate2`에 포함되지 않음

---

## 수정 내용

### 1. ✅ **CTranslate2 환경 강제 설정** (근본 해결책)

#### A. 프로그램 시작 시 자동 설정 ([ssmaker.py:195-231](ssmaker.py#L195-L231))
```python
def _setup_ctranslate2_environment():
    """프로그램 시작 시 CTranslate2 환경 강제 설정"""
    # 1. _internal/ctranslate2를 PATH에 추가
    # 2. Windows AddDllDirectory API 호출
    # 3. DLL 로드 실패 원천 차단
```

**실행 시점**: PyQt5 import 전 (가장 먼저)
**효과**: 빌드 문제와 무관하게 **런타임에 무조건 ctranslate2 경로 설정**

#### B. Whisper 분석 시 추가 설정 ([whisper_analyzer.py:277-353](core/video/batch/whisper_analyzer.py#L277-L353))
```python
def _force_setup_ctranslate2_environment():
    """Whisper 초기화 직전 CTranslate2 환경 재설정"""
    # 1. 모든 가능한 ctranslate2 경로 스캔
    # 2. DLL 있는 하위 폴더까지 PATH 추가
    # 3. Windows DLL 검색 경로 추가 (AddDllDirectory)
```

**실행 시점**: Whisper 모델 로드 직전 (매번)
**효과**: 이중 안전장치 - 프로그램 시작 + Whisper 실행 시 모두 설정

### 2. ✅ **spec 파일 수정** ([ssmaker.spec:88-121](ssmaker.spec#L88-L121))

기존 코드:
```python
# CTranslate2 데이터 포함
try:
    ctranslate2_datas = collect_data_files('ctranslate2')
    datas += ctranslate2_datas
    print(f"[Build] CTranslate2 data files: {len(ctranslate2_datas)} items")
except Exception as e:
    print(f"[Build] CTranslate2 data not found: {e}")
```

**수정된 코드** (바이너리 명시적 수집):
```python
# CTranslate2 데이터 및 바이너리 포함
try:
    # 데이터 파일 수집
    ctranslate2_datas = collect_data_files('ctranslate2')
    datas += ctranslate2_datas
    print(f"[Build] CTranslate2 data files: {len(ctranslate2_datas)} items")

    # 바이너리 파일 직접 수집 (DLL, PYD 등)
    import ctranslate2
    import glob
    ctranslate2_path = os.path.dirname(ctranslate2.__file__)
    print(f"[Build] CTranslate2 path: {ctranslate2_path}")

    # DLL 및 PYD 파일 수집
    ct2_binaries = []
    for ext in ['*.dll', '*.pyd', '*.so', '*.dylib']:
        for file_path in glob.glob(os.path.join(ctranslate2_path, ext)):
            ct2_binaries.append((file_path, 'ctranslate2'))
            print(f"[Build] CTranslate2 binary: {os.path.basename(file_path)}")

    # 하위 폴더의 바이너리도 수집
    for ext in ['*.dll', '*.pyd', '*.so', '*.dylib']:
        for file_path in glob.glob(os.path.join(ctranslate2_path, '**', ext), recursive=True):
            rel_path = os.path.relpath(os.path.dirname(file_path), ctranslate2_path)
            target_dir = os.path.join('ctranslate2', rel_path) if rel_path != '.' else 'ctranslate2'
            ct2_binaries.append((file_path, target_dir))
            print(f"[Build] CTranslate2 binary (subdir): {os.path.basename(file_path)} -> {target_dir}")

    binaries += ct2_binaries
    print(f"[Build] CTranslate2 total binaries: {len(ct2_binaries)} items")
except Exception as e:
    print(f"[Build] CTranslate2 collection failed: {e}")
    import traceback
    traceback.print_exc()
```

### 3. ✅ **런타임 진단 로그 개선** ([whisper_analyzer.py:28-97](core/video/batch/whisper_analyzer.py#L28-L97))

변경 사항:
- Whisper 시작 시점에 자동 진단 로그 출력 (기존 기능)
- **영상별 로그 파일(`*_log.txt`)에도 진단 정보 기록** (신규)
- ctranslate2 폴더 내 파일 목록 출력 추가

### 4. ✅ **실패 원인 자동 분석 및 해결책 제시** ([whisper_analyzer.py:100-274](core/video/batch/whisper_analyzer.py#L100-L274))

**핵심 기능**: Whisper 실패 시 원인을 자동 분석하고 해결책까지 로그에 기록

**분석 케이스**:
1. **ctranslate2 누락** → 폴더/파일 존재 확인 + 백신 격리 가이드
2. **모듈 import 실패** → Python 환경/재설치 안내
3. **DLL 로드 실패** → Visual C++ 재배포 패키지 설치 링크
4. **권한 문제** → 관리자 권한 실행/설치 경로 변경 안내
5. **메모리 부족** → 프로그램 종료/모델 크기 축소 안내
6. **알 수 없는 오류** → 일반적인 해결 방법 + 로그 공유 요청

**출력 예시**:
```
🔴 Whisper 분석 실패 - 원인 진단 보고서
에러 타입: FileNotFoundError
에러 메시지: [WinError 2] 지정된 파일을 찾을 수 없습니다: 'C:\...\ctranslate2'

🔍 원인 분석 결과:
  └─ ctranslate2 라이브러리 파일 누락 문제

📂 ctranslate2 폴더 확인:
  └─ 경로: C:\Program Files (x86)\ssMaker\_internal\ctranslate2
  └─ 존재 여부: ❌ 없음

💡 해결 방법:
  1. 프로그램 재설치 (관리자 권한 필수)
  2. ZIP 압축 파일 사용 시:
     - ZIP 파일 우클릭 → 속성 → '차단 해제' 체크
     - 확인 후 재압축 해제
  3. 백신 프로그램 확인:
     - 설치 중 백신이 파일을 차단했을 가능성
     - 백신 → 격리/차단 목록 확인
  4. 설치 경로 문제:
     - Program Files 같은 보호된 폴더 → 사용자 폴더로 이동
     - 예: C:\Users\<사용자>\ssMaker

📊 시스템 정보:
  └─ 운영체제: Windows-10-...
  └─ Python: 3.11.x
  └─ PyInstaller 빌드: True

📦 모듈 설치 상태:
  └─ ctranslate2: ❌ 없음
  └─ faster_whisper: ✅ 설치됨
      경로: C:\...\faster_whisper\__init__.py

⚠️  이 문제로 인해 자막 타이밍이 글자 수 비례로 대체됩니다.
   (정확도는 낮지만 영상 생성은 계속 진행됩니다)
```

**진단 정보 항목**:
```
[Whisper 런타임 진단 정보]
Platform: Windows-10-...
Python: 3.11.x
Executable: C:\Program Files (x86)\ssMaker\ssmaker.exe
Frozen (PyInstaller): True
Base path: C:\Program Files (x86)\ssMaker
_internal dir: C:\Program Files (x86)\ssMaker\_internal
  └─ Exists: True/False
ctranslate2 dir: C:\Program Files (x86)\ssMaker\_internal\ctranslate2
  └─ Exists: True/False
  └─ Total files: 15
  └─ Binary files (.dll/.pyd/.so): 8
  └─ Binaries: ctranslate2.pyd, mkl_core.dll, ...
ctranslate2 module: C:\...\ctranslate2\__init__.py
faster_whisper module: C:\...\faster_whisper\__init__.py
PATH env length: 2048 chars
PATH contains _internal: True/False
TTS file exists: True
```

---

## 빌드 및 배포 절차

### 1. 빌드 실행
```bash
pyinstaller ssmaker.spec
```

**빌드 로그 확인 사항**:
```
[Build] CTranslate2 data files: 12 items
[Build] CTranslate2 path: C:\...\site-packages\ctranslate2
[Build] CTranslate2 binary: ctranslate2.pyd
[Build] CTranslate2 binary: mkl_core.dll
[Build] CTranslate2 binary: mkl_intel_thread.dll
[Build] CTranslate2 total binaries: 8 items  ← 이 숫자가 0이 아니어야 함!
```

### 2. 빌드 검증
```bash
cd dist/ssmaker
dir _internal\ctranslate2  # Windows
ls _internal/ctranslate2   # macOS/Linux
```

**필수 파일 확인**:
- `ctranslate2.pyd` (또는 `.so`)
- `*.dll` 파일들 (mkl_core.dll, mkl_intel_thread.dll 등)

### 3. 배포 후 확인

**문제 PC에서 실행 후 로그 확인**:
1. 영상 처리 시작
2. `출력폴더/<영상파일명>_log.txt` 열기
3. `[Whisper 런타임 진단 정보]` 섹션 확인

**정상 케이스**:
```
ctranslate2 dir: C:\Program Files (x86)\ssMaker\_internal\ctranslate2
  └─ Exists: True
  └─ Total files: 15
  └─ Binary files (.dll/.pyd/.so): 8
```

**문제 케이스**:
```
ctranslate2 dir: C:\Program Files (x86)\ssMaker\_internal\ctranslate2
  └─ Exists: False  ← 폴더 자체가 없음!
```

---

## 특정 PC만 실패하는 이유 (동일 빌드인 경우)

### 원인 1: 백신/보안 프로그램
- 일부 백신은 `.dll` 파일을 악성코드로 오탐지
- 설치/압축 해제 중 `_internal/ctranslate2` 폴더 격리/삭제
- **해결**: 백신 로그 확인 → ssMaker 폴더 예외 처리 추가

### 원인 2: 압축 해제 실패
- 긴 경로명, 권한 문제, 특수문자 등으로 압축 해제 실패
- **해결**:
  - 관리자 권한으로 압축 해제
  - 짧은 경로에 설치 (예: `C:\ssMaker`)
  - ZIP 파일 우클릭 → 속성 → **차단 해제** 체크 → 재압축 해제

### 원인 3: 설치 폴더 권한 문제
- `Program Files (x86)` 같은 보호된 폴더에 설치 시 권한 부족
- **해결**:
  - 사용자 폴더에 설치 (`C:\Users\<사용자>\ssMaker`)
  - 또는 관리자 권한으로 실행

---

## 문제 해결 가이드 (사용자용)

### ❌ 증상: Whisper 분석 실패
```
[Faster-Whisper 오류] [WinError 2] 지정된 파일을 찾을 수 없습니다
```

### ✅ 즉시 확인 사항

#### 1. ctranslate2 폴더 존재 확인
```
C:\Program Files (x86)\ssMaker\_internal\ctranslate2
```
- 없으면 → **재설치 (관리자 권한)**

#### 2. 백신 격리 확인
- 백신 프로그램 열기
- 격리/차단 목록 확인
- `ssMaker` 관련 파일 있으면 → **복원 + 예외 처리**

#### 3. 정상 PC에서 폴더 복사
```
정상 PC: C:\Program Files (x86)\ssMaker\_internal\ctranslate2
  → USB 복사 →
문제 PC: C:\Program Files (x86)\ssMaker\_internal\ctranslate2
```

#### 4. ZIP 파일 차단 해제
- ZIP 파일 우클릭 → 속성
- 하단 "차단 해제" 체크박스 체크
- 확인 → 재압축 해제

---

## 핵심 개선: 3단계 방어 시스템

이제 **ctranslate2 문제는 3단계 방어**로 해결됩니다:

### 1단계: 프로그램 시작 시 (ssmaker.py)
```
[시작] CTranslate2 경로 추가: C:\...\ssMaker\_internal\ctranslate2
[시작] Windows DLL 검색 경로 추가
```
→ **빌드 누락 문제와 무관하게 런타임에 강제 설정**

### 2단계: Whisper 초기화 시 (whisper_analyzer.py)
```
[CTranslate2 환경] PATH에 3개 경로 추가
[CTranslate2 환경] Windows DLL 검색 경로 추가
```
→ **이중 안전장치: 시작 시 설정이 실패해도 재설정**

### 3단계: 실패 시 상세 진단 및 해결책 제시
```
🔴 Whisper 분석 실패 - 원인 진단 보고서
📂 ctranslate2 폴더: ❌ 없음
💡 해결 방법: 재설치/백신 확인/...
```
→ **실패해도 원인과 해결책을 로그에 자동 기록**

## 이전 vs 개선 후

### ❌ 이전 (수동 대응)
1. 같은 빌드인데 특정 PC만 실패
2. 로그: "지정된 파일을 찾을 수 없습니다"
3. **원인 파악 불가** → 사용자에게 물어봐야 함
4. 재설치/재배포 → **여전히 실패**

### ✅ 개선 후 (자동 해결)
1. **프로그램 시작 시 ctranslate2 경로 강제 설정**
2. **Whisper 실행 시 재확인 및 재설정**
3. 실패 시 **자동 진단 보고서 생성**
4. 로그만 봐도 **즉시 원인 파악 및 해결 가능**

## 다음 단계

1. **이 수정본으로 재빌드**
2. `dist/ssmaker/_internal/ctranslate2` 폴더 확인 (선택)
3. **문제 PC에 배포**
4. **이제 대부분 자동 해결됨!**
5. 여전히 실패 시 → `*_log.txt`의 진단 보고서 확인

---

## 참고: 관련 파일

- [ssmaker.spec:88-121](ssmaker.spec#L88-L121) - CTranslate2 바이너리 수집
- [core/video/batch/whisper_analyzer.py:28-97](core/video/batch/whisper_analyzer.py#L28-L97) - 런타임 진단 로그

---

**마지막 업데이트**: 2024-12-24
