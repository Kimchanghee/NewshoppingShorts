# 쇼핑 쇼츠 노출/메타데이터 분석 리포트

- 작성일: 2026-06-21 KST
- 분석 대상: 현재 Summer Coupang 자동 업로드 영상 15개, YouTube 공개 검색 유사 쇼츠 후보 184개, 관련 쇼츠 후보 118개, 상세 분석 영상 24개, 고유 경쟁 채널 23개
- 한계: YouTube Studio/Analytics의 실제 노출수, CTR, 평균 시청 지속시간은 이 보고서에서 접근하지 못했다. 여기서는 공개 조회수, 공개 제목/설명/해시태그, 큐에 저장된 검증 메타데이터를 노출 proxy로 사용했다.

## 1. 결론

현재 노출이 약한 가장 큰 구조적 이유는 업로드 privacy가 `unlisted`로 기록된 점이다. 큐 검증 메타데이터 기준으로 완료 영상은 모두 `unlisted`라서 Shorts 피드/검색 추천 노출을 기대하기 어렵다. 노출 실험을 하려면 품질/고지/링크 검증 후 `public` 업로드 또는 public 전환이 필요하다.

두 번째 문제는 제목 첫 20자다. 현재 제목은 대부분 `[광고] [번호] 상품명...`으로 시작한다. 경쟁 쇼츠는 문제상황/반전/가격/사용 장면을 먼저 제시한다. 예: `선 안 꽂았는데 돌아간다고?`, `장마철 비에도 끄떡없는 여름휴가 필수템`, `물놀이 필수템 8가지`. 쇼츠 피드에서는 첫 문장이 정지 여부를 가르므로, 번호와 긴 상품명보다 후킹 문장을 앞에 둬야 한다.

세 번째 문제는 카테고리/상황 키워드가 약하다. 제품명은 들어가지만 `출근길`, `캠핑`, `물놀이`, `자취방`, `전기세`, `장마`, `햇빛차단`, `쿨링` 같은 사용 맥락이 부족하다. YouTube 설명과 Instagram 캡션에는 제품군 키워드와 상황 키워드를 같이 넣는 편이 낫다.

## 2. 현재 업로드 영상 노출 상태

- 완료 영상: 15개
- 공개 조회수 합계: 1
- 공개 조회수 중앙값: 0
- 공개 조회수 최대값: 1
- 큐 privacy: {'unlisted': 15}

| 번호 | 제목 요약 | 조회수 | privacy | YouTube | 검증 |
|---|---|---:|---|---|---|
| [030] | [광고] [030] Apnoo 대용량 미니냉풍기 휴대용에어컨 에어쿨러 얼음선풍기 - 냉풍기 #shorts | 1 | unlisted | [link](https://youtu.be/6Wf5_Dj-WQo) | YT True / LT True |
| [031] | [광고] [031] 제이파크 미니냉풍기 휴대용에어컨 에어쿨러 냉선풍기 에어컨선풍기 얼음선풍기 휴대용 캠핑 - 냉풍기 #shor | 0 | unlisted | [link](https://youtu.be/kFJ6rCBn-DI) | YT True / LT True |
| [033] | [광고] [033] 소가 휴대용 손선풍기 냉각 에어컨 선풍기 - USB/휴대용 #shorts | 0 | unlisted | [link](https://youtu.be/lZeHd-jVj3c) | YT True / LT True |
| [035] | [광고] [035] KINSCOTER ???? ??? ??? ??? neck fan #shorts | 0 | unlisted | [link](https://youtu.be/bT6dDMu60to) | YT True / LT True |
| [036] | [광고] [036] 휴대용 무선선풍기 저소음 탁상용 캠핑선풍기 충전식 - 탁상용 #shorts | 0 | unlisted | [link](https://youtu.be/xdCgxfelhwc) | YT True / LT True |
| [037] | [광고] [037] iya 무선 캠핑선풍기 - USB/휴대용 #shorts | 0 | unlisted | [link](https://youtu.be/7IMZ3oIRG0Y) | YT True / LT True |
| [038] | [광고] [038] 펠코스 양우산 uv차단 초경량 자외선차단 양산 - 양산 #shorts | 0 | unlisted | [link](https://youtu.be/EXTIJyxqjI0) | YT True / LT True |
| [039] | [광고] [039] 로열스테디 튼튼한 초경량 UV 자외선차단 접이식우산 양산 - 양산 #shorts | 0 | unlisted | [link](https://youtu.be/Bg8qaXjWfMI) | YT True / LT True |
| [040] | [광고] [040] [로지온]스포츠타올 수건 타월 냉감 시원한 쿨링 여름 헬스 등산 테니스 땀수건 쿨타월 아이스 - 스포츠/비 | 0 | unlisted | [link](https://youtu.be/8fxDE4D8pN8) | YT True / LT True |
| [041] | [광고] [041] 1+1 여름수건 냉감 쿨타올 타월 냉타올 스포츠타올 냉수건 쿨수건 아이스타올 땀수건 쿨링 - 스카프/넥워머 | 0 | unlisted | [link](https://youtu.be/P-A6REAelrc) | YT True / LT True |
| [042] | [광고] [042] [어베이브] 셀론사 솔리드 냉감 쿨토시 팔토시 자외선차단 골프 등산 자전거 운전 파크골프 - 쿨토시/토시  | 0 | unlisted | [link](https://youtu.be/TNlTyNRnTO4) | YT True / LT True |
| [044] | [광고] [044] [10p]TOP 탑 쿨토시 자외선차단 냉감 아이스 팔토시 - 팔토시/다리토시 #shorts | 0 | unlisted | [link](https://youtu.be/eSuGhZ9aiE8) | YT True / LT True |
| [045] | [광고] [045] 구스페리 컬러 물놀이 휴대폰 방수팩 - 방수팩/방수케이스 #shorts | 0 | unlisted | [link](https://youtu.be/JqOuac5ckCo) | YT True / LT True |
| [046] | [광고] [046] 프레소 휴대폰 방수팩 휴대폰방수팩 - 방수팩/방수케이스 #shorts | 0 | unlisted | [link](https://youtu.be/UuEcp754mPQ) | YT True / LT True |
| [051] | [광고] [051] 디스퍼 프리미엄 3세대 미스트 휴대용 선풍기 - USB/휴대용 #shorts | 0 | unlisted | [link](https://youtu.be/y34QZtGY-Kw) | YT True / LT True |

### 판정

- 조회수만 보면 외부 노출은 매우 약하다. 다만 `unlisted` 상태라면 알고리즘 노출이 거의 없는 것이 정상이다.
- `[광고] [번호]`가 제목 앞을 차지해 검색/피드 후킹이 약하다. 번호는 설명/댓글/Linktree 매칭에는 좋지만 제목 앞자리에는 손해가 크다.
- 상품명 자동 수집 문자열이 길고 중복 단어가 많다. 쇼츠 제목은 상품명 전체가 아니라 사용자가 겪는 문제와 결과를 압축해야 한다.

## 3. 유사 쇼츠/경쟁 채널 표본

- 관련 쇼츠 표본 공개 조회수 중앙값: 250
- 관련 쇼츠 표본 공개 조회수 최대값: 4,636

| 채널 | 표본 제목 | 조회수 | 길이 | 해시태그/키워드 | URL |
|---|---|---:|---:|---|---|
| 만전김[전만한 하루] | 장마철 비에도 끄떡없는 여름휴가 필수템?!🎒 | 4,636 | 32s | #EVENT, #월리드라이백, #물놀이, #필수템, #구독이벤트, #이벤트 | [link](https://www.youtube.com/watch?v=14xm0nfUjuc) |
| order reversepalm | 아이스 냉풍기 영상 | 4,519 | 30s | - | [link](https://www.youtube.com/watch?v=YxEZ89n5en8) |
| dadream | 피부 온도 내려주는 여름 꿀템 #쿨토시 #uv차단 #팔토시 | 2,793 | 34s | #쿨토시, #uv차단, #팔토시 | [link](https://www.youtube.com/watch?v=h9HX61kHa58) |
| 아이템솔루션 | 남자 양산 추천 순위 Best5 남성용 암막 UV 양산 | 1,264 | 75s | 남자양산, WPC양산, 양산, 스텐반찬통, 우양산, 아치서포트 | [link](https://www.youtube.com/watch?v=_yoZ0BX_HAw) |
| BOX SEND | 센드박스 화장실 스마트폰 거치대 방수거치대 방수팩 욕실 샤워실 | 1,180 | 64s | - | [link](https://www.youtube.com/watch?v=fxPmJboNTqI) |
| 딜팩토리 | [딜팩토리 하이퍼 냉풍기] 30평형 냉방력을 한달 전기세 1,000원대로 시원하게 즐겨보세요 | 799 | 34s | 딜팩토리, 냉풍기, 에어쿨러, 냉방기, 에어컨, 선풍기 | [link](https://www.youtube.com/watch?v=LR8Wkl3kBVE) |
| 해피한스토리 | 에어냉풍기 제품 소개영상 | 568 | 27s | - | [link](https://www.youtube.com/watch?v=ytW1D2LpIEc) |
| 쇼핑홀릭 | 물놀이 필수템 8가지 추천 / 여름철 휴가 바다,강,해수욕장,물놀이를 간다면 꼭 챙겨가세요! | 505 | 148s | #물놀이, #여름철, #여름, #휴가, #물놀이필수템, #바다 | [link](https://www.youtube.com/watch?v=hU-AEJ1MNo4) |
| 추천연구소 | 선풍기 우산 추천! 지금까지의 것은 잊어라! 역대급 안믿기면 안보셔도 되요! 가성비 인기 끝판왕 모음! | 391 | 87s | #추천연구소, #쿠팡최저가, #쿠팡추천템, #쿠팡살림템, #오늘의특가, #선풍기우산추천 | [link](https://www.youtube.com/watch?v=4udNyWpdtZI) |
| 알뜰살뜰 | 쿨스카프 추천 2023년 7월 꿀템 소개해요 추천순위 TOP10 | 380 | 59s | #다비즈, #아이스, #슬로비, #여름필수템, #K2, #제이앤씨 | [link](https://www.youtube.com/watch?v=ijgZGUQHubA) |
| 어바웃쇼핑 | [광고]여성팔토시 추천 판매순위 Top10 \|\| 가격 평점 후기 비교 | 310 | 57s | #여성팔토시, #여성팔토시추천, #여성팔토시가격, #여성팔토시후기, #가성비여성팔토시, #여성팔토시순위 | [link](https://www.youtube.com/watch?v=zRkO7Ulyf1g) |
| 쇼츠킹 | 이동식 에어컨이 '도서관'보다 조용하다고? | 305 | 29s | #이동식에어컨, #에어컨, #실외기없는에어컨, #저소음에어컨, #듀얼인버터, #파센느 | [link](https://www.youtube.com/watch?v=7kMXY28zk9I) |
| 어바웃쇼핑 | 방수파우치 추천 판매순위 Top10 \|\| 가격 평점 후기 비교 | 195 | 56s | #방수파우치추천, #방수파우치가격, #방수파우치후기, #가성비방수파우치, #방수파우치순위, #펀타스틱 | [link](https://www.youtube.com/watch?v=PSykRxYZCcs) |
| 러키비키TV | 여름 필수템! UV 차단 완벽 방어하는 대형 자동 양산 3종 비교 리뷰 | 167 | 147s | 쿠팡리뷰, 유튜브쇼츠, 리뷰채널, 유튜브 업로드, 태그, 뉴스 | [link](https://www.youtube.com/watch?v=8X0LwdOPO20) |

### 경쟁 표본에서 반복되는 패턴

- 반복 해시태그: #여름필수템(6), #쿠팡추천템(4), #쇼츠(4), #여름가전(3), #물놀이(2), #여름휴가(2), #여름(2), #휴가(2), #살림템(2), #폭염(2), #쿠팡꿀템(2), #무선선풍기(2), #shorts(2), #EVENT(1), #월리드라이백(1), #필수템(1)
- 제목 반복어: 추천(11), 필수템(6), 여름(6), 냉풍기(4), 양산(3), 선풍기(3), Top10(3), 비교(3), 차량용(3), 아이스(2), 영상(2), 꿀템(2), 남자(2), UV(2), 시원하게(2), 가성비(2), 2023년(2), 판매순위(2), 가격(2), 평점(2)
- 관련 쇼츠 표본도 대부분 조회수가 높지는 않다. 즉, 쿠팡/제휴 쇼츠는 단순 상품 나열만으로는 노출이 약하고, 공개 상태 + 강한 첫 2초 후킹 + 저장/공유를 부르는 문제상황이 필요하다.
- 상대적으로 조회수가 높은 표본은 긴 상품명보다 `장마철`, `피부 온도`, `물놀이`, `남자 양산`, `전기세`, `조용함` 같은 구체 상황을 앞세운다.
- 제목에 해시태그를 너무 많이 붙인 영상은 정보는 많지만 문장 후킹이 약해진다. 해시태그는 설명/캡션으로 보내고 제목은 한 문장으로 유지하는 편이 낫다.

## 4. YouTube 업로드 방식 제안

### 4.1 공개 설정

1. 자동화 검증용 1차 업로드는 `unlisted`로 유지해도 된다.
2. 노출을 원하는 영상은 검증 완료 후 `public`로 전환하거나 처음부터 public로 업로드해야 한다.
3. public 전환 전 체크: 세로 9:16, 60초 이하, 제목/설명/댓글의 광고 고지, 구매 링크, Linktree 번호 매칭, 제품 오인 가능성 없는 영상.

### 4.2 제목 공식

현재: `[광고] [042] [어베이브] 셀론사 솔리드 냉감 쿨토시... #shorts`

권장: `후킹 문장 + 제품군 키워드 + 번호/고지 최소화`

| 제품군 | 권장 제목 예시 |
|---|---|
| 휴대용 선풍기 | `출근길 땀 식히는 손풍기, 이 정도면 충분함 #shorts` |
| 냉풍기 | `에어컨 틀기 전 10초 쿨링템, 미니냉풍기 체감` |
| 양산 | `햇빛 강한 날 얼굴 온도 줄이는 초경량 양산` |
| 쿨토시 | `운전할 때 팔 타는 사람, 냉감 쿨토시 써야 하는 이유` |
| 방수팩 | `물놀이 갈 때 폰 살리는 방수팩 체크포인트` |
| 쿨타올 | `목에 두르면 바로 시원한 여름 쿨타올` |

운영 규칙:
- 제목 35~55자 안쪽. 첫 15자 안에 문제/결과를 넣는다.
- `[번호]`는 제목 뒤쪽 또는 설명 첫 줄에 둔다. Linktree 매칭용 번호는 설명/댓글에서 유지한다.
- `#shorts`는 제목 또는 설명에 넣되, 제목에는 1개만 두고 나머지는 설명으로 보낸다.
- 같은 제품군을 연속 업로드할 때 제목 첫 문장을 바꾼다. 예: `캠핑`, `출근길`, `자취방`, `차량`, `물놀이` 맥락 순환.

### 4.3 설명/댓글 템플릿

```text
[043] 더운 날 바로 쓰는 여름 필수템: {짧은 제품군/상황 설명}
구매 링크: {purchase_url}
링크 모음: https://linktr.ee/studio.idol

이 게시물은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.

#shorts #여름필수템 #{제품군} #쿠팡추천 #가성비템
```

고정 댓글은 현재처럼 구매 링크와 고지를 포함하되, 첫 줄을 `영상 속 제품 [043] 구매 링크`처럼 검색/매칭 가능하게 둔다.

### 4.4 해시태그 세트

| 카테고리 | YouTube 설명 해시태그 |
|---|---|
| 공통 | `#shorts #여름필수템 #쿠팡추천 #가성비템` |
| 선풍기/냉풍기 | `#휴대용선풍기 #미니선풍기 #냉풍기 #여름가전` |
| 양산/자외선 | `#양산 #자외선차단 #초경량양산 #장마템` |
| 쿨토시/쿨타올 | `#냉감토시 #쿨토시 #쿨타올 #운동템` |
| 물놀이 | `#방수팩 #물놀이준비물 #여름휴가 #여행준비물` |

## 5. Instagram Reels 업로드 방식

Instagram은 YouTube보다 검색 제목보다 캡션/화면 텍스트/저장·공유 반응이 중요하다. 링크는 캡션에서 클릭되지 않으므로 `프로필 링크(Linktree) + 번호` 방식이 필요하다.

권장 캡션 템플릿:

```text
더운 날 바로 쓰는 여름템 [043]
제품명: {짧은 제품명}
구매 링크는 프로필 링크에서 [043] 번호로 확인하세요.

쿠팡 파트너스 활동으로 수수료를 제공받을 수 있습니다.

#여름필수템 #쿠팡추천 #{제품군} #가성비템 #살림템 #자취템 #캠핑템 #릴스추천
```

Instagram 운영 규칙:
- 첫 화면 텍스트는 2줄 이하: `물놀이 갈 때 폰 젖는 사람`, `에어컨 전기세 무서우면`처럼 문제부터 시작.
- 캡션 첫 줄에 제품 번호를 둬서 Linktree 카드와 매칭한다.
- 해시태그는 8~12개 범위로, 공통 4개 + 제품군 4개 + 상황 2개 정도만 사용한다.
- 가능하면 Trial Reels로 후킹 문장 A/B 테스트를 한다. 같은 영상이라도 첫 2초 문구만 바꿔 테스트한다.
- 쇼핑 태그 자격이 있으면 Reels에도 쇼핑 태그를 붙인다. 없으면 프로필 Linktree 방식으로 일원화한다.

## 6. 자동화 코드에 반영할 업로드 규칙

1. `youtube_privacy`를 운영 모드별로 분리한다: `검증 모드=unlisted`, `노출 모드=public`.
2. 제목 생성기를 `상품명 요약형`에서 `후킹형`으로 바꾼다.
3. 제목 앞 `[광고] [번호]` 고정은 노출 실험에서는 불리하므로, 법적 고지/플랫폼 정책 확인 후 설명·댓글 중심으로 옮기거나 제목 뒤쪽으로 최소화한다.
4. 제품군별 해시태그 프리셋을 추가한다.
5. Instagram 업로드용 캡션은 YouTube 설명을 그대로 복사하지 말고 `프로필 링크 + 번호` 구조로 별도 생성한다.
6. 업로드 후 24시간/72시간 공개 조회수, 좋아요, 댓글 수를 큐에 다시 저장해서 다음 제목/해시태그 선택에 반영한다.

## 7. 근거/출처

- YouTube Help: hashtags can be added in titles/descriptions and up to three may appear by the title: https://support.google.com/youtube/answer/6390658
- YouTube Help: title, thumbnail, and description are more important than tags for discovery: https://support.google.com/youtube/answer/146402
- YouTube Help: descriptions with keywords help viewers find videos through search: https://support.google.com/youtube/answer/12948449
- Instagram Help: hashtags can be added in captions or comments: https://help.instagram.com/351460621611097
- Instagram Creators: use relevant keywords in content, caption, bio, and hashtags: https://creators.instagram.com/blog/tips-for-improving-your-reach
- Instagram Creators: recommendations/Search guidance mentions relevant keywords and hashtags in captions: https://creators.instagram.com/blog/instagram-recommendations-eligibility-tips-creators
- Instagram Help: shopping tags can be added to Reels/Stories/posts when eligible: https://help.instagram.com/1135563777270082/
- YouTube public sample metadata collected with yt-dlp on 2026-06-21 from the queries listed in the raw data JSON.
