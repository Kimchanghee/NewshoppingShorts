---
description: 최신형 쇼핑 쇼츠 메이커 배포용 빌드 가이드
---

# 쇼핑 쇼츠 메이커 완전 독립 빌드 워크플로우

이 워크플로우는 다른 컴퓨터에서도 별도의 설치 없이 실행될 수 있도록 모든 모듈, AI 모델, 바이너리를 포함하는 빌드 절차를 따릅니다.

## 빌드 원칙
1. **완전성**: 모든 외부 라이브러리(PyQt6, MoviePy, faster-whisper 등) 포함
2. **이동성**: ffmpeg, OCR 모델, AI 가중치 파일을 `_internal` 또는 바로 옆에 동봉
3. **보안**: `.env` 파일과 API Key 정보는 포함하지 않음 (사용자 설정용)
4. **권한**: 관리자 권한(`uac_admin=True`) 요청 포함

## 빌드 절차

// turbo-all
1. 기존 빌드 찌꺼기 제거
   ```powershell
   Remove-Item -Path "build", "dist" -Recurse -Force -ErrorAction SilentlyContinue
   ```

2. 종속성 재확인 (필요 시)
   ```powershell
   .\venv314\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. PyInstaller 실행 (Spec 파일 기준)
   ```powershell
   .\venv314\Scripts\python.exe -m PyInstaller ssmaker.spec
   ```

4. 결과물 검증
   - `dist/ssmaker/ssmaker.exe` 존재 확인
   - `dist/ssmaker/_internal` 내에 ffmpeg, models 등이 포함되었는지 확인

5. 압축 및 배포 준비
   - 전체 폴더를 .zip으로 압축하여 전달
