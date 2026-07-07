# 새 소싱 방식 설계 — 도우인/샤오홍슈/콰이쇼우 영상 다운로드 기반
작성일: 2026-07-06

## 0. 배경 — 왜 바꾸나
현재 방식(AliExpress/1688 소스클립 + 쿠팡 상품 조합 → 렌더)에서 세 가지 문제가 실측됨:
- **제목 깨짐(?????)**: 한글/중문이 CP949↔UTF-8 경계에서 손상. 채널명도 `오늘의 쇼핑` → `?ㅻ뒛???쇳븨`로 저장돼 있었음(같은 원인). 간헐적(07-03·04 배치만).
- **3연속 중복**: 같은 상품/클립이 큐에 여러 번 → 같은 제목 3~7개 업로드.
- 소스 영상의 품질·상품 관련성이 들쭉날쭉.

정리 완료: YouTube 불량 48개(깨진 8 + 테스트정크 40) 삭제, 로컬 테스트 폴더 34개(0.67GB) 삭제.

## 1. 새 방식 개요
Douyin/Xiaohongshu/Kuaishou에서 **잘 나가는 상품 리뷰·데모 영상**을 받아 → **재편집**(컷·리프레임·자막·음성·워터마크 제거) → 쿠팡 제휴 링크 매칭 → YouTube/Instagram/TikTok 업로드.

## 2. 파이프라인 단계
1. **수집 Collector**
   - Douyin/Kuaishou: `yt-dlp` 추출기 지원 → 다운로드 가능(이미 의존성 있음).
   - Xiaohongshu(RED): yt-dlp 지원 불안정 → 전용 브라우저 스크래퍼(zendriver) 필요, 후순위.
   - 키워드/해시태그/트렌드로 후보 검색 → 메타(작성자·조회수·URL·길이) 수집.
2. **중복 제거 Dedup — 재발 방지 핵심**
   - (a) **영상 지각 해시**(프레임 pHash)로 동일/유사 영상 차단.
   - (b) **상품 식별자**(제품명 정규화 + 쿠팡 productId) 기준 1일/1주 쿨다운.
   - (c) **업로드 완료분 persistent set**(SQLite/json)에 기록 → 재시도·재실행이 재업로드 못 하게.
     - ※ 현재 버그: 중복 판정이 `status=="completed"`만 집계 → `linktree_retry_pending`·`completed_linktree_blocked` 상태가 다시 업로드됨(`scripts/run_summer_coupang_queue_once.py`). 새 파이프라인은 "업로드 성공=영상ID 기록" 기준으로 판정.
3. **재가공 Editor**
   - 워터마크/로고 제거(크롭·블러·inpaint) — 플랫폼 정책 + 원작 표식 제거.
   - 앞뒤 컷, 9:16 리프레임, 한국어 자막/TTS 덮어쓰기, BGM 교체 → **변형 저작물** 강도↑.
4. **메타 생성 SEO**
   - 제목/설명/해시태그는 **한국어 원천 텍스트에서만** 생성.
   - 업로드 직전 **손상 감지 가드** `_text_looks_corrupted`(✅ 적용됨) → ????? 원천 차단.
5. **업로드 Publisher**: 기존 YouTube + 신규 Instagram/TikTok 공식 API 재사용.

## 3. 인코딩 재발 방지 (제목 깨짐 근본 대책)
- 앱/모든 스크립트 진입점에서 `sys.stdout/err`를 UTF-8 재설정 + 환경변수 **PYTHONUTF8=1, PYTHONIOENCODING=utf-8** 강제.
- 큐·상품 JSON의 모든 `open()`에 `encoding="utf-8"` 명시(윈도우 기본 cp949 금지).
- `subprocess` 호출 시 `env`에 `PYTHONUTF8=1` 주입(자식 프로세스 stdout 손상 차단).
- 업로드 직전 손상 가드(✅ youtube_manager, 적용 완료) — 인스타/틱톡 매니저에도 동일 적용 예정.

## 4. 저작권 / 스트라이크 리스크 (현실 경고)
- 남의 영상 재업로드는 YouTube/TikTok **저작권 스트라이크** 대상. 원본 그대로는 금지.
- 완화책: 변형 강도↑(재편집·자막·음성·BGM·속도·크롭), 짧은 클립 조합, 가능하면 크리에이터 허가/무료 소스 우선, 채널 분산, 스트라이크 모니터링.
- 리스크 0은 불가능 → 사업 판단 필요(이건 기술이 아니라 정책 문제).

## 5. 구현 우선순위
1. Collector(yt-dlp: Douyin/Kuaishou) + Dedup(pHash + persistent uploaded-set) → **중복 근본 해결**.
2. UTF-8 강제 + 제목 가드(일부 완료) → **인코딩 근본 해결**.
3. Editor(워터마크 제거 + 리프레임/자막/TTS).
4. Xiaohongshu 스크래퍼(난이도 높음, 후순위).

## 6. 바뀌는 모듈(예상)
- 신규: `core/sourcing/video_collector.py`(yt-dlp 래퍼), `core/sourcing/dedup.py`(pHash+set), `managers/uploaded_registry.py`(persistent set).
- 수정: `core/video/batch/processor.py`(소스=다운로드 영상), `core/sourcing/*`, 진입점 UTF-8 강제.
- 재사용: `managers/youtube_manager.py`, `managers/instagram_manager.py`, `managers/tiktok_manager.py`.
