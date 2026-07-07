# 고좋아요 쇼츠 기반 여름/생활템 업로드 분석

- 작성일: 2026-06-21 10:06:05 KST
- 목적: 좋아요 수가 수천 개 이상 붙은 상품형 Shorts를 우선 표본으로 다시 수집해, YouTube와 Instagram 업로드 규칙을 더 공격적으로 보정한다.
- 기준: YouTube 해시태그 Shorts 페이지에서 후보를 수집하고, 공개 상세 메타데이터에서 `like_count >= 1,000`, `duration <= 180초`, 상품/생활템 관련성 점수 통과 항목만 사용했다.
- 수집 규모: 해시태그 45개, 후보 912개, 상세 확인 220개, 고좋아요 통과 171개, 고유 채널 114개.
- 한계: Instagram Reels의 공개 좋아요/도달 데이터는 로그인/API 없이 안정적으로 수집하기 어렵기 때문에, 이번 정량 표본은 YouTube Shorts 공개 메타데이터를 주 기준으로 삼고 Instagram에는 패턴을 이식하는 방식으로 분석했다.

## Executive Summary

좋아요가 크게 붙은 상품 쇼츠는 상품명을 길게 나열하지 않는다. 첫 문장은 대부분 `상황 문제 -> 즉시 결과` 구조다. 예: 더러운 바닥, 모기, 더위, 욕실 청소, 물놀이, 누수, 주방 손질처럼 시청자가 바로 겪는 불편을 먼저 보여주고, 제품명은 뒤로 보낸다.

현재 자동 업로드 제목처럼 `[광고] [번호] 상품명...`으로 시작하면 추천 피드에서 첫 1초 후킹이 약하다. 번호와 광고 표기는 설명/고정댓글/캡션 안으로 내리고, 제목 첫 20자는 `문제/결과/상황`으로 써야 한다.

고좋아요 표본의 핵심은 `짧은 시연`, `강한 결과 문장`, `링크 행동 유도`, `카테고리 해시태그`다. 특히 한국어 쿠팡 계열은 `프로필 링크 n번`, `댓글 남기면 링크`, `쿠팡 파트너스 고지`를 제목이 아니라 설명에 배치한다.

## 1. 고좋아요 표본 요약

- 통과 표본 좋아요: 최소 1,344, 중앙값 23,171, 75퍼센타일 77,277, 최대 6,169,769
- 통과 표본 조회수: 중앙값 3,835,620, 최대 667,041,245
- 한국어/쿠팡 계열로 분류되는 통과 표본: 37개
- 많이 반복된 해시태그: `#shorts`(67), `#gadgets`(48), `#lifehacks`(36), `#trending`(35), `#viral`(32), `#smarthome`(26), `#newgadgets`(26), `#kitchengadgets`(26), `#amazonfinds`(26), `#musthave`(22), `#tech`(21), `#innovation`(20), `#youtubeshorts`(20), `#coolgadgets`(19), `#쿠팡꿀템`(18), `#techlover`(17), `#shortsfeed`(17)
- 한국어 표본 반복 해시태그: `#쿠팡꿀템`(18), `#생활꿀템`(15), `#살림꿀템`(13), `#자취꿀템`(12), `#쿠팡추천`(11), `#소개팁`(11), `#쿠팡추천템`(10), `#꿀템`(5), `#주방꿀템`(4), `#생활꿀팁`(4), `#살림템`(3), `#가성비템`(3), `#여름필수템`(3), `#살림추천`(2)

## 2. 좋아요 많은 채널/영상 표본

| 채널 | 제목/영상 | 좋아요 | 조회수 | 길이 | 핵심 해시태그 | 분석 포인트 |
|---|---|---:|---:|---:|---|---|
| Expertise Gadgets | [If the floor is dirty, use Sobon! #Handsfreemop #homegadg...](https://www.youtube.com/shorts/Qf3IKJWo2HQ) | 6,169,769 | 667,041,245 | 59s | #Handsfreemop, #homegadgets, #shorts | 더러운 바닥이라는 즉시 문제와 손 안 쓰는 해결책을 한 컷에 묶음. |
| GoGoods | [smart home gadgets #smarthome #home #homedecor #cleaning ...](https://www.youtube.com/shorts/DzQnxEFH0Kk) | 2,179,909 | 149,844,861 | 58s | #smarthome, #home, #homedecor, #cleaning, #gadgets | ASMR형 시연과 스마트홈 키워드 반복으로 제품 기능을 직관화. |
| Jiujiu Good Things | [小宝宝给姐姐安排蚊帐！再也不怕蚊子了！#实用好物#好物推荐 #funny](https://www.youtube.com/shorts/WUd691v4WE8) | 1,450,130 | 296,683,526 | 25s | #实用好物, #好物推荐, #funny | 중국어 `好物推荐` 계열. 모기/아이/여름 문제를 매우 짧게 처리. |
| Milyutka | [Weird home gadgets 😳 Which one did you like the most? #we...](https://www.youtube.com/shorts/XnM7YWgKSoA) | 908,493 | 145,031,162 | 25s | #weirdgadgets, #homegadgets, #gadgets | 이상한 도구/호기심 후킹. 제목에서 질문형 반응을 유도. |
| Unik Pranali | [😱Viral Life Saving Gadget~New Viral Gadgets Smart Applian...](https://www.youtube.com/shorts/tZ9ZyvMNPkw) | 735,249 | 162,375,305 | 16s | #gadgets, #shortvideo, #lifehacks, #shorts | 생존/안전형 도구로 과장 없이 강한 효용을 먼저 제시. |
| ASHRAF HERE | [SMART APPLIANCES & New Gadgets / Versatile Tools & Kitche...](https://www.youtube.com/shorts/RmrjgMB7688) | 630,629 | 21,122,860 | 31s | #shorts, #gadgets | 도구 모음형이지만 제목은 카테고리와 효용만 간결하게 배치. |
| Marusya Outdoors | [My Cool Outdoor Finds on @temu  🌿](https://www.youtube.com/shorts/QzBLRpcTt_Q) | 469,638 | 67,318,596 | 46s | #temu, #temureview, #temufinds, #temuhaul, #temucode | Temu/야외 finds. 상품보다 사용 장면을 먼저 보여줌. |
| DAD's Channel | [Cheap Folding Electric Bike #electricbike](https://www.youtube.com/shorts/CFGKW1YjpuE) | 319,937 | 43,438,331 | 29s | #electricbike, #AliExpress, #AliExpressFinds, #Ebike | 한 제품을 `cheap + category`로 즉시 포지셔닝. |
| Suyel Toy | [Mini fan Vs big cooling fan unboxing and review 🔥](https://www.youtube.com/shorts/8QhXz8x9JG4) | 228,040 | 29,654,905 | 16s | #shorts, #fan, #minifan, #rcfan, #coolingfan | 미니팬 vs 큰 냉각팬 비교형. 여름템에 바로 적용 가능. |
| David | [The Perfect Mother’s Day Gift for Mom 💖 #amazonfinds](https://www.youtube.com/shorts/XEyqS0A_yRI) | 207,731 | 23,504,896 | 34s | #amazonfinds, #kpopdemonhunters, #amazonmusthaves, #amazongadgets | 선물 상황형 제목. 구매 이유가 명확함. |
| VIKAS MISHRA | [This Charging Dock Feels Like The Future ⚡ 3-in-1 Magneti...](https://www.youtube.com/shorts/Y83oHNWSXBE) | 195,282 | 20,396,444 | 16s | #shorts, #tech, #gadgets, #wirelesscharger, #desksetup | 무선충전 도크를 미래감/데스크셋업 키워드로 포장. |
| Worldwide Gadgets | [🔗 Link in Bio Effective Cleaning Tablets  One Wipe, Spotl...](https://www.youtube.com/shorts/62IPdLKaL5w) | 136,441 | 23,545,171 | 38s | #shorts, #homecleaning, #cleaninghacks, #tiktokmademebuyit | 제목 맨 앞에 Link in Bio를 두되, 바로 뒤에 청소 결과를 넣음. |
| Sam Shan Shops | [Inflatable outdoor tanning pool restock 👙☀️ #tanningpool ...](https://www.youtube.com/shorts/tm7tFuvJjoY) | 136,265 | 10,131,875 | 11s | #tanningpool, #summerdrink, #summeressentials, #outdoor | 여름 야외/태닝 풀. 계절성과 사용 장면이 한 번에 보임. |
| BabyVK | [Is Your Baby Too Hot During Outdoor Activities? Use the M...](https://www.youtube.com/shorts/Hxy-lCZX-gg) | 132,279 | 19,382,646 | 7s | #Shorts, #MustHaves, #BabyVK, #BabyCare, #Tiktok | 아기가 더운 상황을 질문형으로 시작해 휴대용 팬으로 해결. |
| RumiRumiR | [Amazon Finds: we fought a whole crowd just to grab this w...](https://www.youtube.com/shorts/ZGzuPtoX2yM) | 86,329 | 13,429,310 | 30s | #amazonfinds, #amazonmusthaves | 사람들이 몰려 잡는다는 사회적 증거 + Amazon Finds 조합. |
| Linyi’s Finds | [Rumi is LOSING IT because of mosquitoes… any ideas?](https://www.youtube.com/shorts/gIskBY1HqVg) | 31,992 | 3,703,914 | 24s | #amazonfinds, #amazonmusthaves, #amazongadgets, #mosquito, #summergadgets | 모기 문제와 여름 가젯 해시태그가 정확히 맞음. |
| Linyi’s Finds | [Hiking in the Heat… But Rumi’s Fine? 🥵🤔 #amazonfinds](https://www.youtube.com/shorts/plUgk8jW2NU) | 4,589 | 635,795 | 38s | #amazonfinds, #amazonmusthaves, #amazongadgets, #neckfan, #portablefan | 더위 속 하이킹 상황 + 넥팬. 여름 손풍기/넥밴드에 직접 참고. |
| 소개팁 IntroTip | [✨욕실이 스마트해지는 꿀템Top3🛁](https://www.youtube.com/shorts/nwl8ewmbEN0) | 58,707 | 4,042,866 | 29s | #쿠팡꿀템, #쿠팡추천, #살림꿀템, #살림추천, #자취꿀템 | 한국어 Top3 구조. 욕실/스마트/꿀템이 선명함. |
| 살룸연구소 | [술자리 미친템ㅋㅋ 한 번 하면 멈출 수 없음 스릴팡 #꿀템](https://www.youtube.com/shorts/FSViOS4Kp8A) | 57,309 | 14,874,072 | 18s | #꿀템, #생활용품, #쿠팡추천템, #쿠팡꿀템, #꿀템추천 | “미친템ㅋㅋ”처럼 감정 반응을 먼저 걸고 상품은 뒤에서 설명. |
| 홈픽 / 쿠팡추천템 ' 인테리어템 ' 집꾸미기 | [더러운 발톱케어 잘때 붙이기만하면 끝_304.손발톱 나이트타임 패치 #꿀템](https://www.youtube.com/shorts/8p2BGAz1sWI) | 51,201 | 15,638,736 | 15s | #꿀템, #손톱영양, #발톱패치, #발톱무좀, #살림템 | 쿠팡 파트너스 고지와 번호 검색을 설명에 배치한 좋은 예. |
| 소개팁 IntroTip | [맛집 사장님들이 꼭 쓴다는 발명템ㅋㅋ](https://www.youtube.com/shorts/-YS6JwI5LBo) | 50,416 | 7,179,817 | 30s | #소개팁, #쿠팡꿀템, #쿠팡추천, #생활꿀템, #자취꿀템 | 댓글/DM/프로필 링크 CTA가 설명 첫 부분에 있음. |
| 오늘의발견 | [네일샵 가지마세요 #내성발톱 #내성발톱교정 #발톱교정 #발톱관리 #발톱통증 #셀프네일 #생활꿀템 #쿠팡...](https://www.youtube.com/shorts/AljupqGz3hY) | 48,487 | 19,932,327 | 16s | #내성발톱, #내성발톱교정, #발톱교정, #발톱관리, #발톱통증 | “네일샵 가지마세요”처럼 대체효과를 제목 앞에 둠. |
| 소개팁 IntroTip | [모기랑 전쟁해서 이기는법](https://www.youtube.com/shorts/EtsjI3u62rQ) | 18,699 | 1,794,313 | 30s | #소개팁, #쿠팡꿀템, #쿠팡추천, #생활꿀템, #살림꿀템 | 모기와 전쟁한다는 여름 문제형 후킹. |
| 생활에꿀팁 | [독일기술몰빵된5세대채칼 독일채칼에위력이거쓰면다른거못씀한달동안1000개이상판매됐데요~집에 있는 채칼 싹다...](https://www.youtube.com/shorts/j5xlOBPKeFM) | 9,825 | 1,150,129 | 11s | #채칼, #꿀템, #쿠팡꿀템, #생활꿀템 | 독일기술/판매량/댓글 CTA를 짧은 본문에 결합. |
| 아이템훗 | [300만 원 날릴 뻔했던 역대급 천장 누수, 이거 하나로 10년 방수 끝!](https://www.youtube.com/shorts/eDptN6I7Zqs) | 6,409 | 1,286,058 | 25s | #방수테이프, #누수차단, #살림꿀템 | 누수/300만원 손실 회피. 방수 제품은 손실 회피 문장이 강함. |
| Home_Design_Note | [손으로 만질 필요 없어졌어요! #꿀템 #배수구](https://www.youtube.com/shorts/usgzHg_zH9I) | 2,859 | 1,041,066 | 24s | #꿀템, #배수구, #욕실꿀템, #욕실청소, #살림템 | 욕실 청소 귀찮음에서 시작해 배수구 제품으로 해결. |
| 숏템 | [차광막 이렇게 묶지마세요](https://www.youtube.com/shorts/ZfgFGuaiww0) | 2,090 | 1,130,930 | 17s | #생활꿀팁, #살림템, #가성비템, #야외생활, #꿀템추천 | 차광막 묶는 문제를 야외생활/가성비템으로 묶음. |

## 3. 제목 패턴

고좋아요 영상은 제목에서 제품명 전체를 설명하지 않고, 시청자가 멈출 이유를 먼저 만든다.

| 패턴 | 구조 | 바로 쓸 제목 예시 |
|---|---|---|
| 문제 해결형 | `{불편} + {이거 하나로 해결}` | `차 안 더위, 손풍기 하나로 버티는 법 #여름꿀템` |
| 손실 회피형 | `{큰 손해/귀찮음} + 막는 제품` | `장마철 누수 300만원 날리기 전, 방수테이프 체크` |
| 비교형 | `{A vs B} + 체감 차이` | `미니 선풍기 vs 냉각팬, 더운 날 뭐가 나을까` |
| 상황형 | `{장소/순간} + 필수템` | `물놀이 갈 때 폰 살리는 방수팩 체크포인트` |
| 반응형 | `{미친템/환장/이상한데 유용}` | `자취생 환장하는 여름 청소 꿀템 3개` |
| 사회적 증거형 | `{사장님/전문가/많이 팔린}` | `맛집 사장님들이 쓰는 주방 발명템` |

자동 생성 제목 규칙은 아래처럼 바꾸는 게 맞다.

```text
기존: [광고] [043] 제품명 전체 - 카테고리 #shorts
변경: {문제/상황 후킹} + {짧은 카테고리} + #shorts 또는 #여름꿀템
번호/광고/파트너스 고지: 설명 첫 3줄 또는 고정댓글로 이동
```

## 4. YouTube 업로드 규칙

1. 제목 첫 20자는 무조건 문제/결과로 시작한다. `[광고]`, `[번호]`, 긴 제품명은 앞에 두지 않는다.
2. 제목 해시태그는 1-2개만 둔다. YouTube 공식 문서상 해시태그는 제목/설명에서 연결되며, 설명의 해시태그 중 일부가 제목 주변에 노출된다. 과다 해시태그는 관련성이 떨어진다.
3. 설명 첫 줄은 제품 번호와 CTA다. 예: `구매 링크는 프로필/Linktree에서 [043] 검색` 또는 `댓글에 링크 남겨드림` 같은 행동 문장을 먼저 둔다.
4. 쿠팡 파트너스 고지는 설명 초반에 명확히 넣는다. 제목 첫머리에는 넣지 않는다.
5. 고정댓글은 `번호 + 한 줄 효용 + 링크 안내`로 통일한다.
6. 태그 필드는 보조다. YouTube 공식 문서도 제목/썸네일/설명이 발견성에 더 중요하고, tags는 오타 보정 정도의 역할이라고 설명한다.

### YouTube 설명 템플릿

```text
[{번호}] {한 줄 효용}
구매 링크는 프로필 Linktree에서 [{번호}] 검색하면 바로 확인할 수 있습니다.

쿠팡 파트너스 활동의 일환으로 일정액의 수수료를 제공받을 수 있습니다.

{상황 설명 2문장: 언제 쓰는지 / 왜 필요한지}

#shorts #{제품군} #여름꿀템 #생활꿀템 #쿠팡추천 #가성비템
```

## 5. Instagram Reels 업로드 규칙

Instagram은 링크 클릭 동선이 YouTube보다 약하므로, 캡션 첫 줄과 프로필 링크 번호가 중요하다.

1. 릴스 화면 첫 자막은 `문제 + 결과` 2줄 이내로 쓴다.
2. 캡션 첫 줄에 제품 번호를 넣는다. 예: `[043] 물놀이 폰 방수팩`
3. 링크는 `프로필 링크에서 043 검색` 방식으로 고정한다. 캡션 URL 클릭을 기대하지 않는다.
4. 해시태그는 6-10개 정도로 섞는다. `#여름꿀템 #생활꿀템 #쿠팡추천 #가성비템` 같은 넓은 태그와 `#방수팩 #손풍기 #양산추천` 같은 제품군 태그를 같이 쓴다.
5. 댓글 유도는 링크 요청형으로 간단히 쓴다. 예: `필요하면 댓글에 번호 남겨주세요.`
6. 광고/제휴 고지는 캡션 초반에 명확히 넣는다.

### Instagram 캡션 템플릿

```text
[{번호}] {문제 해결 한 줄}
{상황 설명 1-2문장}

구매 링크는 프로필 링크에서 [{번호}] 검색하세요.
쿠팡 파트너스 활동으로 수수료를 제공받을 수 있습니다.

#여름꿀템 #생활꿀템 #쿠팡추천 #가성비템 #{제품군} #{상황키워드}
```

## 6. 여름 상품군별 바로 쓸 문장

| 상품군 | YouTube 제목 | Instagram 첫 줄 | 해시태그 세트 |
|---|---|---|---|
| 손풍기/넥팬 | `출근길 땀 식히는 손풍기, 이 정도면 충분함 #shorts` | `[043] 차 안/출근길 더위 버티는 손풍기` | `#손풍기 #휴대용선풍기 #여름꿀템 #출근템 #쿠팡추천` |
| 냉풍기 | `에어컨 틀기 전 10초 쿨링템, 미니냉풍기 체감` | `[044] 방 안 더울 때 바로 쓰는 냉풍기` | `#냉풍기 #쿨링템 #여름가전 #자취템 #가성비템` |
| 방수팩 | `물놀이 갈 때 폰 살리는 방수팩 체크포인트` | `[045] 물놀이 전에 폰 방수부터` | `#방수팩 #물놀이 #여름휴가 #여름필수템 #생활꿀템` |
| 양산 | `햇빛 강한 날 얼굴 온도 줄이는 초경량 양산` | `[046] 햇빛 강한 날 가방에 넣는 양산` | `#양산추천 #자외선차단 #여름필수템 #출근템 #쿠팡추천` |
| 쿨토시 | `운전할 때 팔 타는 사람, 냉감 쿨토시 써야 하는 이유` | `[047] 운전할 때 팔 타면 이거` | `#쿨토시 #냉감토시 #운전템 #자외선차단 #여름꿀템` |
| 쿨타올 | `목에 두르면 바로 시원한 여름 쿨타올` | `[048] 야외에서 바로 식히는 쿨타올` | `#쿨타올 #캠핑템 #운동템 #여름필수템 #생활꿀템` |
| 방수테이프/장마템 | `장마철 누수 300만원 날리기 전, 방수테이프 체크` | `[049] 장마철 누수 전에 붙이는 방수템` | `#방수테이프 #장마템 #살림꿀템 #생활꿀템 #가성비템` |
| 모기/벌레템 | `모기랑 전쟁하는 사람, 여름 벌레템 하나는 필요함` | `[050] 모기 때문에 잠 못 자면 이거` | `#모기퇴치 #여름꿀템 #캠핑템 #자취꿀템 #쿠팡추천` |

## 7. 자동화에 반영할 변경점

- 제목 생성기에서 `광고/번호/제품명` 우선순위를 낮추고 `상황 후킹` 우선순위를 최상단으로 둔다.
- 제품군별 후킹 사전을 만든다: 더위, 물놀이, 장마, 모기, 출근길, 차 안, 캠핑, 자취방, 욕실, 주방.
- 설명 템플릿은 `번호 -> 링크 안내 -> 광고 고지 -> 상황 설명 -> 해시태그` 순서로 고정한다.
- Linktree 번호 검색 문구를 YouTube 설명과 Instagram 캡션에 동일하게 넣는다.
- 해시태그는 상품군 2개, 상황 2개, 플랫폼/카테고리 2개로 제한한다.
- 업로드 후 24시간/72시간에 좋아요와 조회수를 다시 저장해 다음 제목 생성에 피드백으로 사용한다.

## 8. 검토한 링크형/제휴형 설명 예시

| 채널 | 영상 | 좋아요 | 설명/CTA 패턴 |
|---|---|---:|---|
| Worldwide Gadgets | [🔗 Link in Bio Effective Cleaning Tablets  One Wipe, Spot](https://www.youtube.com/shorts/62IPdLKaL5w) | 136,441 | 🔗 Link in Bio Effective Cleaning Tablets  One Wipe, Spotless Surfaces Safe for Every Home #shorts #homecleaning #cleaninghacks #tiktokmademebuyit |
| RumiRumiR | [Amazon Finds: we fought a whole crowd just to grab this](https://www.youtube.com/shorts/ZGzuPtoX2yM) | 86,329 | 🔗 You can find this product in my title option — 🔥 LAST 3 LEFT 👈  and check it out! 🙌  These Amazon finds are practical, smart, and perfect for upgrading your everyday life. From h |
| RumiRumiR | [Amazon Finds That Make My Kitchen Smell Fresh #amazonfin](https://www.youtube.com/shorts/1fHj4neYWq4) | 67,942 | 🔗 You can find this product in my title option — BUY PRODUCTS NOW 👈 and check it out! 🙌  These Amazon finds are practical, smart, and perfect for upgrading your everyday life. From |
| 홈픽 / 쿠팡추천템 ' 인테리어템 ' 집꾸미기 | [더러운 발톱케어 잘때 붙이기만하면 끝_304.손발톱 나이트타임 패치 #꿀템](https://www.youtube.com/shorts/8p2BGAz1sWI) | 51,201 | [304.손발톱 나이트타임 패치] 이 포스팅은 쿠팡 파트너스 활동의 일환으로 이에 따른 일정액의 수수료를 제공받습니다.   구매원하시면 프로필링크에 “304” 검색하시거나 아래 링크클릭!! 👇 https://link.coupang.com/a/ejm8Ps  다양한 추천템을 더 보고싶으시면 구독⚡️ 필요할것 같은 친구한테도 |
| 소개팁 IntroTip | [맛집 사장님들이 꼭 쓴다는 발명템ㅋㅋ](https://www.youtube.com/shorts/-YS6JwI5LBo) | 50,416 | 💡맛집 사장님들이 꼭 쓴다는 발명템 Top4  ▫️아무댓글이나 남겨도 최저가링크 로켓DM 드려요🚀 ▫️ ( @intro_tip ) 프로필링크에서 검색해도 다 뜹니다!  🥕 야채 손질은 이제 이걸로 끝!ㅋㅋㅋ 여러 가지 채소를 모아서 이 기계에 넣고 뺑뺑 돌려주면 순식간에 채썰립니다! 청양고추랑 파는 기본이고 오이 양파 딱 |
| RumiRumiR | [Amazon Finds We Can't Stop Snacking On #amazonfinds #ama](https://www.youtube.com/shorts/VAl8wkmv-JQ) | 33,493 | 🔗 You can find this product in my title option — BUY PRODUCTS NOW 👈 and check it out! 🙌  These Amazon finds are practical, smart, and perfect for upgrading your everyday life. From |
| Linyi’s Finds | [Rumi is LOSING IT because of mosquitoes… any ideas?](https://www.youtube.com/shorts/gIskBY1HqVg) | 31,992 | 👇 SHOP THE VIDEO: Tap the 🔗BUY PRODUCTS NOW 👈（Limited-time offer） link at the bottom to get this exact product! Follow Rumi & Jinu’s adventures with the KPOP Demon Hunters to disco |
| 생활에꿀팁 | [독일기술몰빵된5세대채칼 독일채칼에위력이거쓰면다른거못씀한달동안1000개이상판매됐데요~집에 있는 채칼 싹](https://www.youtube.com/shorts/j5xlOBPKeFM) | 9,825 | 독일기술 몰빵된 5세대 채칼 독일채칼릐 위력 이거쓰면 다른거 못씀 한단동안 1000개 이상 판매됐데요~ 집에 있는 채칼 싹다 버리고 이걸로 주문해버림 쓱쓱  썰리는 느낌이 쾌감이 미쳤는데 댓글에 "나도" 남겨주세요 ✨ 프로필 링크에서  85 번검색도 가능해요 ✨ 프로필 바로가기  https://link.inpock.co. |

## 9. 데이터/출처

- 수집 데이터 JSON: `docs/shorts_high_like_analysis_2026-06-21_data.json`
- YouTube 공개 메타데이터: `yt-dlp`로 YouTube 해시태그 Shorts 페이지와 개별 영상 상세 메타데이터를 수집했다.
- YouTube 해시태그 공식 설명: https://support.google.com/youtube/answer/6390658
- YouTube tags 공식 설명: https://support.google.com/youtube/answer/146402
- 이전 노출 분석 보고서: `docs/shorts_exposure_analysis_2026-06-21.md`
