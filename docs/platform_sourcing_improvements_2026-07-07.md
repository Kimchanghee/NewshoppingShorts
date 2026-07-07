# 3플랫폼 소싱 검증 결과 + 개선방안
작성일: 2026-07-07 · 대상: `platform_shorts_searcher.py` / `reeditor.py` / `sourcing_panel.py` 3플랫폼 흐름

## 1. 검증 결과 — 어제 작업은 코드에 실제로 들어가 있음

| 항목 | 상태 |
|---|---|
| `platform_shorts_searcher.py` (도우인→콰이쇼우→샤오홍슈 first-hit-wins) | ✅ 존재, 기존 `_download_video`/`_extract_video_urls`/`_page_has_access_challenge`/zendriver 영구 프로필 재사용 |
| `chinese`/`english` 키 수정 | ✅ `sourcing_panel.py:1017`에서 `kw.get("chinese")` 사용 (중국어→한국어→영어 폴백) |
| 재편집기 `reedit` (크롭+9:16+훅, UTF-8 subprocess) | ✅ 존재 |
| UI 분기 (`platform_video` 방식 → `_run_platform_pipeline`) | ✅ 존재 |
| 업로드단 중복 차단 + 제목 손상 가드 | ✅ youtube_manager 경유라 자동 적용 |

## 2. 발견된 문제 (우선순위순)

### P0-1. 수익화 누락 — 딥링크/링크트리 없음 ★가장 치명적
`_run_platform_pipeline`은 `source_url=쿠팡 원본 링크`만 넘김. 파트너스 딥링크 생성도, 링크트리 발행도 없음 → **업로드돼도 제휴 수익 0원**. 큐 배치에는 제휴링크 게이트(`blocked_affiliate_link_missing`)까지 있는데 이 흐름만 원본 링크로 우회되는 셈.
- **개선**: coupang 방식의 deep_link 스텝(`SourcingPipeline` step 2) + linktree_publish를 platform 흐름에 그대로 재사용. `add_to_upload_queue(coupang_deep_link=..., linktree_url=...)` 전달. `_validate_linktree_publish_ready()` 검사도 복원.

### P0-2. 풀자동화 미연동 — 수동 버튼에서만 동작
`get_automation_sourcing_method()` 참조처는 sourcing_panel뿐. 스케줄 배치(`run_summer_coupang_queue_once.py`)에는 platform_video 분기가 없음 → "풀자동화 소싱 방식" 설정인데 실제 풀자동화(4시간 큐)는 여전히 coupang 방식만 탐.
- **개선**: 큐 스크립트 `run_sourcing()`에 method 분기 추가 — platform_video면 `scrape_product`→키워드→`search_platform_shorts`→`reedit` 후 기존 업로드/링크트리 단계 합류. 기존 상태머신(SUCCESS/SKIP/RETRY 상태들) 재사용.

### P1-3. 도우인 추출 취약 — 실전 성공률 낮을 것
도우인 검색 페이지 영상은 대부분 `blob:`이고, 데이터는 percent-encoded `RENDER_DATA`라 `"playAddr"` 정규식이 원문 HTML에서 안 잡힘. 콰이쇼우 의존이 될 가능성 높음.
- **개선(효과 큰 순)**:
  1. 검색 결과에서 **영상 페이지 링크**(`douyin.com/video/{id}`, `kuaishou.com/short-video/{id}`)를 긁고, 다운로드는 **yt-dlp**에 위임 — 서명된 CDN URL·만료 문제를 yt-dlp가 처리. 이미 스캐폴드가 있는 `platform_video_collector.py`(현재 미사용 고아 모듈)를 여기에 연결해 통합.
  2. zendriver CDP 네트워크 이벤트로 `.mp4` 응답 스니핑(스크롤 중 캡처) — 정규식보다 견고.
  3. `RENDER_DATA` decodeURIComponent 후 파싱을 보강 JS에 추가.

### P1-4. 키워드 변환이 rule-based뿐 — 사전 미등록 상품은 검색 실패
coupang 방식은 Gemini 변환 우선인데 platform 방식은 `convert_keywords_rule_based`만 사용. 컴파운드 맵(~100개) 밖 상품명 → 중국어 없음 → 한국어로 도우인 검색 → 거의 안 잡힘.
- **개선**: `convert_keywords_gemini` 우선 + rule-based 폴백 (coupang 방식과 동일 패턴, pipeline.py:513 참조).

### P1-5. 소싱단 중복 차단 없음
중복 차단이 업로드 직전뿐이라, 같은 상품 재실행 시 검색→다운로드→재편집 전 과정을 낭비하고, 서로 다른 상품이 같은 소스 영상을 잡아도 모름(설계문서 §2의 pHash+persistent set이 소스단에는 미적용).
- **개선**: `uploaded_registry`에 소스 영상 URL/ID 기록 → `search_one_platform`에서 이미 쓴 URL 스킵. 설계문서대로 pHash는 후속.

### P2-6. 후보 검증 없음 — 첫 mp4가 광고/무관 영상일 수 있음
first-hit-wins가 "페이지에서 첫 번째로 잡힌 mp4"라 관련성·품질 보장 없음.
- **개선**: 다운로드 후 ffprobe로 길이 5~60초·세로(또는 크롭 가능 비율)·최소 720p 검증, 실패 시 다음 후보(이미 상위 5개 시도 구조라 검증만 끼우면 됨).

### P2-7. 재편집 변형 강도 부족 — 원본 오디오 그대로
현재 크롭+리프레임+훅 텍스트뿐. **원본 음성이 그대로 남는 게 Content ID에 가장 잘 걸림**. 설계문서 §4도 BGM/음성/속도 변형을 요구.
- **개선**: reedit에 옵션 추가 — BGM 교체(또는 음소거+TTS), 속도 1.02~1.05x, 좌우 미러 옵션.

### P2-8. 자잘한 버그·정합
- **UI 진행률 버그**: platform 흐름은 pct를 10/30/60/100으로 넘기는데 `_update_step`은 `pct >= 1.0`을 완료로 판정 → 모든 스텝이 즉시 '완료' 표시. 0.1/0.3/0.6/1.0으로 수정.
- **설정 불일치**: 기본 `platform_video_sources=["douyin","kuaishou"]`인데 UI 문구·검색기 기본값은 3채널(샤오홍슈 포함). 문구 또는 기본값 통일.
- **미사용 스텝 표시**: platform 모드에서 deep_link/keyword_convert/linktree 등 인디케이터가 영원히 pending — 모드별 스텝 세트 분리(P0-1 반영 시 대부분 해소).
- **산출물 정리 없음**: `~/.ssmaker/platform_video_output`에 원본+편집본 누적(지난번 0.67GB 정리 재발 우려) — 업로드 성공 시 원본 삭제 or N일 보존.
- **테스트 0개**: platform_shorts_searcher/reeditor 유닛 테스트 없음(어제 "32개 통과"는 기존 스위트). URL 템플릿·키워드 폴백·reedit 인자 생성 정도는 mock으로 가능.

## 3. 권장 실행 순서
1. **P0-1 딥링크+링크트리** (수익 직결, 기존 스텝 재사용이라 반나절감)
2. **P0-2 풀자동화 큐 분기** (이게 돼야 '풀자동화'라는 이름값)
3. **P1-3 yt-dlp 하이브리드 다운로드** (실전 성공률 좌우)
4. P1-4 Gemini 키워드 → P1-5 소싱단 중복 → P2 순
5. 각 단계 후 실기기 스모크: 쿠팡 링크 1개로 3플랫폼 실행, 어느 채널에서 잡히는지 + 업로드 설명란에 딥링크 들어갔는지 확인

## 4. 구현·실전 테스트 결과 (2026-07-07 심야, 같은 날 완료)
P0~P2 전부 구현 완료. 유닛 379개 통과. 실기기 스모크(`scripts/smoke_platform_run.cmd`) 반복 실행으로 검증:

| 회차 | 결과 | 배운 것 → 수정 |
|---|---|---|
| 1~2 | 실패 | 로깅 미초기화, `chinese/english` 중복 토큰 → 토큰 dedup+상한 |
| 3~4 | 행/급사 | `browser.get` 무한대기 → 페이지 열기 40s·평가 15s 타임아웃, 플랫폼당 240s 예산 |
| 5~6 | 실패 | 고아 Chrome 12개가 프로필 잠금 → 시작 타임아웃+고아 정리 후 재시도 |
| 7~8 | 실패(정상 완주) | 같은 탭 재사용 시 멈춘 페이지가 후속 검색 차단 → 쿼리별 새 탭 격리. 도우인/콰이쇼우/샤오홍슈 전부 비로그인 게이트 실측 확인 |
| 9 | 실패 | **빌리빌리 4번째 폴백 추가**(비로그인 검색 가능) — 검색은 성공, yt-dlp 412 |
| 10 | **성공** | yt-dlp에 브라우저 쿠키 동봉 + 412 시 `__playinfo__` 브라우저 컨텍스트 다운로드 폴백 |
| 11 | **성공(다른 상품)** | 길이 검증(198s 스킵)·소스 중복 기록 동작 확인 |

최종 산출물: 1080×1920 H.264+AAC, 21s/재편집(크롭+1.03x+훅) — 업로드 큐 규격 그대로.

## 5. 2차 반복(같은 날) — 비로그인 완전 해결
"영상 보는 데 로그인 필요 없다"는 지적이 맞았다. 덤프 분석 결과 게이트는 **플랫폼 '자체 검색'만** 걸려 있었고(도우인=검색 셸만 렌더, 콰이쇼우=홈 리다이렉트), 영상 페이지는 비로그인 시청 가능. 그래서:

1. **외부검색 폴백**: 자체 검색 0건이면 DuckDuckGo html 검색(`키워드 site:douyin.com/video`)으로 영상 페이지 링크 확보 — 실측 도우인 10개/쿼리.
2. **브라우저 컨텍스트 다운로드**: yt-dlp가 거부하면(도우인 'Fresh cookies', 빌리빌리 412) 영상 페이지를 탭으로 열어 RENDER_DATA/playAddr에서 mp4를 뽑아 세션 쿠키로 직접 다운로드.
3. yt-dlp에는 쿠키를 헤더가 아닌 **Netscape cookiefile**로 전달(도우인 추출기 요구사항).

**결과: 로그인 0회로 도우인 소싱 성공 ×2** (모기퇴치기 35s, 팔토시 9.3MB), 빌리빌리 폴백 포함 5연속 실전 성공. `scripts/open_platform_login.py`는 선택 사항으로만 유지(로그인하면 자체 검색도 열려 후보 폭이 넓어질 뿐, 필수 아님).

## 6. 링크·키 정책 (정정)
- **쿠팡파트너스 API 키는 필수가 아니다.** 수동 파트너스 링크가 항상 최우선: 큐 아이템 `affiliate_url`(기존 동작 유지) / 앱 설정의 수동 상품 링크(`youtube_comment_manual_product_link`). platform 흐름도 이 우선순위(수동 > API > 원본)를 따르며, API 키 관련 안내 문구는 제거했다.
- **Gemini 403** = 코드 문제 아님. `Lightning dunning decision is deny for project 788761947073` — 해당 API 키가 속한 Google Cloud 프로젝트가 결제 연체/실패(dunning) 상태로 Google이 요청을 거부하는 것. 키워드 변환은 룰 사전 폴백으로 정상 동작 중(여름 카테고리 보강 완료). Google AI Studio에서 새 키(다른 프로젝트)로 교체하거나 해당 프로젝트 결제 수단을 복구하면 Gemini 변환이 다시 켜진다.
