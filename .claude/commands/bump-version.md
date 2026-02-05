# Bump Version

업데이트 배포 시 version.json을 업데이트합니다.

## 절차

1. `version.json` 파일을 읽습니다
2. 사용자에게 새 버전 번호를 물어봅니다 (기본: 현재 patch 버전 +1)
3. 다음 필드를 업데이트합니다:
   - `version`: 새 버전 번호 (semver 형식: X.Y.Z)
   - `updated_at`: 현재 날짜시간 (YYYY-MM-DD HH:MM:SS 형식)
   - `build_date`: 현재 날짜 (YYYY-MM-DD 형식)
   - `build_number`: 기존 값 + 1
4. version.json을 저장합니다
5. 변경 사항을 git commit 합니다 (사용자 확인 후)

## 파일 위치

- `version.json` (프로젝트 루트)

## 예시

```json
{
    "version": "1.2.0",
    "build_date": "2026-02-05",
    "updated_at": "2026-02-05 15:30:00",
    "build_number": "3",
    "min_required_version": "1.0.0",
    "update_channel": "stable"
}
```
