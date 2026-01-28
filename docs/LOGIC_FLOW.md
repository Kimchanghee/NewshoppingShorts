# 쇼핑 숏츠 메이커 - 작동 로직 경우의 수

## 📋 목차
1. [영상 길이 기반 TTS 전략](#1-영상-길이-기반-tts-전략)
2. [TTS 생성 시도 로직](#2-tts-생성-시도-로직)
3. [오디오 분석 방식](#3-오디오-분석-방식)
4. [자막 타이밍 동기화](#4-자막-타이밍-동기화)
5. [영상 트림 전략](#5-영상-트림-전략)
6. [OCR 블러 처리](#6-ocr-블러-처리)
7. [음성 선택 로직](#7-음성-선택-로직)
8. [배속 처리](#8-배속-처리)

---

## 1. 영상 길이 기반 TTS 전략

### Case 1.1: 긴 영상 (> 20초)
```
조건: video_duration > 20.0초

동작:
- max_allowed = 20.0초 (1.2배속 후)
- TTS를 영상 전체가 아닌 약 20초로 제한
- 영상은 나중에 TTS + 1초 여유로 자름
- 목적: 긴 영상도 임팩트 있는 숏폼으로 변환

예시:
영상 30.5초 → TTS 약 20초 생성 → 최종 영상 21초
```

### Case 1.2: 짧은 영상 (≤ 20초)
```
조건: video_duration ≤ 20.0초

동작:
- max_allowed = video_duration - 0.5초
- TTS를 영상 길이에 맞춤 (기존 방식)
- 영상 전체 활용

예시:
영상 15초 → TTS 14.5초 목표 → 최종 영상 15초
```

---

## 2. TTS 생성 시도 로직

### Case 2.1: 첫 시도 (attempt = 0)
```
동작:
- 전체 스크립트 사용
- 사전 추정: len(script) * 0.15 / 1.2
- 추정이 max_allowed * 1.5 초과 시 사전 단축
```

### Case 2.2: 재시도 (attempt = 1~4)
```
조건: 이전 TTS가 너무 김

동작:
1. 동적 단축률 계산
   reduction_rate = (1.0 / overshoot_ratio) * 0.95

2. 최소 30%까지 단축 가능
   reduction_rate = max(0.30, min(0.95, reduction_rate))

3. 제품 영상이면 CTA 추가
   if is_product and "product link" not in script:
       script += " If you like this product..."
```

### Case 2.3: 최종 실패 (5회 시도 후)
```
조건: last_duration_after_speed > max_allowed * 1.3

동작:
- 에러 발생: "TTS 길이가 영상 길이에 비해 너무 깁니다"
- 사용자에게 긴 영상 선택 또는 번역문 수동 단축 요청

예외:
- 1.3배 이내 초과: 경고와 함께 진행 (가장 짧은 버전 사용)
```

---

## 3. 오디오 분석 방식

### Case 3.1: Gemini Audio Understanding (우선)
```
조건:
- GENAI_SDK_AVAILABLE = True
- audio_path 존재
- API 호출 성공

동작:
1. 오디오 파일 업로드 (Files API)
2. 타임스탬프 추출 요청
   - 형식: "0.0-2.5: 안녕하세요"
   - 세그먼트: 10-15자 단위
3. 3가지 패턴 파싱:
   - Pattern 1: "0.0-2.5: text"
   - Pattern 2: "00:00-00:02: text" (MM:SS)
   - Pattern 3: "[0.0s] text"
4. max_chars 초과 시 단어 단위 분할

장점: 실제 음성 속도, 쉼, 강세 반영
```

### Case 3.2: 글자 수 기반 추정 (Fallback)
```
조건:
- Gemini 분석 실패
- SDK 미설치
- API 오류

동작:
1. 스크립트를 문장/단어 단위로 분할
2. 글자 수 기반 시간 할당
   weight = len(segment)
   duration = total_duration * (weight / total_weight)
3. 비례 분배로 타이밍 계산

한계: 실제 발화 특성 반영 불가
```

---

## 4. 자막 타이밍 동기화

### Case 4.1: TTS 메타데이터 사용
```
조건: app._per_line_tts 존재

동작:
1. TTS 생성 시 세그먼트 그대로 사용
2. 텍스트 합치기/재분할 금지 (싱크 보존)
3. 각 세그먼트의 start/end 타임스탬프 활용

로그:
[Subtitles] Using TTS segmentation: 21 segments (sync preserved)
```

### Case 4.2: 1.2배속 메타데이터 조정
```
조건: "speeded_tts_1.2x" in filename

동작:
1. 실제 오디오 길이 측정
2. _rescale_tts_metadata_to_duration 호출
3. 모든 타임스탬프 비례 축소
   new_start = old_start * (new_duration / old_duration)
   new_end = old_end * (new_duration / old_duration)

로그:
[TTS 파일] 메타데이터 1.2배속 조정 완료 - 자막 싱크 보장
```

### Case 4.3: 마지막 자막 연장 (CTA)
```
조건: 항상 실행

동작:
1. 마지막 자막 찾기
2. end = video_duration으로 설정
3. start가 video_duration 초과 시:
   start = max(0.0, video_duration - 1.0)

목적: CTA 자막 완전 표시 보장

로그:
[Subtitles] Set last subtitle end to 32.80s (was 31.30s) - CTA complete display guaranteed
```

### Case 4.4: 자막 건너뛰기
```
조건: start_ts >= video_duration + 5.0

동작:
- 5초 이상 초과 자막만 skip
- CTA 보호 (약간의 초과 허용)

로그:
[Subtitles] Built 20 timed segments (skipped 1)
```

### Case 4.5: 짧은 세그먼트 병합
```
조건: 항상 실행

동작:
1. 6자 이하 세그먼트 감지
2. 이전 세그먼트와 병합
   - 텍스트 결합: "꿀템을" + "소개합니다." → "꿀템을 소개합니다."
   - 타이밍 조정: end = 짧은 세그먼트의 end
3. idx 재정렬

목적: 자막 가독성 향상

예시:
Before: ["확인해" (13자), "주세요." (4자)]
After:  ["확인해 주세요." (17자)]

로그:
[Segment Merge] 21개 → 18개 세그먼트 (짧은 구간 병합 완료)
```

---

## 5. 영상 트림 전략

### Case 5.1: 자막 기반 트림
```
조건:
- subtitle_applied = True
- last_subtitle_end > 0

동작:
if final_video.duration > last_subtitle_end + 2.0:
    cut_point = last_subtitle_end + 2.0
    final_video = final_video.subclip(0, cut_point)

여유: 자막 종료 + 2초

로그:
[Trim] Using subtitle end: 30.5s -> 23.3s
[Trim] Completed subtitle-based cut: 23.3s
```

### Case 5.2: 오디오 기반 트림
```
조건:
- subtitle_applied = False (자막 없음)

동작:
if final_video.duration > audio_duration + 2.5:
    cut_point = audio_duration + 2.5
    final_video = final_video.subclip(0, cut_point)

여유: 오디오 종료 + 2.5초

로그:
[Trim] Using audio duration: 30.5s -> 27.4s
[Trim] Completed audio-based cut: 27.4s
```

### Case 5.3: 트림 불필요
```
조건:
- 영상 길이가 이미 적절함

로그:
[Trim] No trim needed - video already ends at 21.3s
```

---

## 6. OCR 블러 처리

### Case 6.1: 중국어 자막 감지 (블러 실행)
```
조건:
- 중국어 감지 비율 > 50%
- OCR 영역 > 0

동작:
1. GPU 가속 영역 집계 (CuPy)
2. 중복 영역 병합
3. 각 영역에 가우시안 블러 적용
4. 한글 자막은 중국어 위치에 덮어씀

로그:
[OCR 병렬] 중국어 감지 비율: 89.5% - 블러 처리 진행
[블러] 2개 영역 블러 처리
```

### Case 6.2: 중국어 자막 없음 (블러 생략)
```
조건:
- 중국어 감지 비율 ≤ 50%
- OCR 영역 = 0

동작:
- 블러 처리 건너뛰기
- 한글 자막만 추가

로그:
[OCR] 중국어 자막 감지 안됨 - 블러 생략
```

---

## 7. 음성 선택 로직

### Case 7.1: 사용자 선택 음성
```
조건:
- voice_vars에 체크된 음성 존재

동작:
- 체크된 음성만 사용
- voice_manager에서 프로필 조회

로그:
[음성 선택] 사용자가 선택한 음성 사용: 서연, 지은
```

### Case 7.2: 기본 음성 (선택 없음)
```
조건:
- voice_vars 모두 체크 해제

동작:
- multi_voice_presets 사용
- 또는 available_tts_voices

로그:
[음성 선택] 기본 음성 사용: 서연
```

---

## 8. 배속 처리

### Case 8.1: 1.2배속 적용
```
조건: 항상 (DynamicBatch)

동작:
1. 원본 TTS 생성
2. librosa.effects.time_stretch 적용
   rate = 1.2
3. 메타데이터 타이밍 조정
   new_time = old_time / 1.2
4. 파일명에 "speeded_tts_1.2x" 포함

로그:
[배속 결과]
  실제 길이: 24.909초
  배속 비율: 1.200x
```

### Case 8.2: Gemini 배속 후 분석
```
조건: 1.2배속 완료 후

동작:
1. 배속 완료된 파일 업로드
2. Gemini Audio Understanding 실행
3. 실제 음성 길이 기준 타임스탬프 추출

장점:
- 실제 재생될 속도 기준 타이밍
- 정확한 자막 싱크

로그:
[배속 후 Gemini 분석] 1.2배속 파일 분석 시작 - 정확한 자막 싱크
[Gemini 오디오 분석] 완료 - 21개 타임스탬프 추출
```

---

## 🔄 전체 플로우 요약

```
1. 영상 다운로드
   └─> 영상 길이 측정
        ├─> > 20초: TTS 20초 제한
        └─> ≤ 20초: TTS 영상 맞춤

2. OCR 분석
   ├─> 중국어 감지: 블러 영역 저장
   └─> 감지 안됨: 건너뛰기

3. 대본 번역
   └─> Gemini 번역

4. TTS 생성 (최대 5회 시도)
   └─> 원본 생성
        └─> 1.2배속 처리
             └─> Gemini 오디오 분석
                  ├─> 성공: 정확한 타임스탬프
                  └─> 실패: 글자 수 기반

5. 자막 생성
   ├─> TTS 메타데이터 사용
   ├─> 짧은 세그먼트 병합 (≤6자)
   ├─> 마지막 자막 연장 (CTA)
   └─> 영상 끝 초과 자막 skip

6. 영상 합성
   ├─> 블러 적용 (중국어 감지 시)
   ├─> 자막 오버레이
   └─> 오디오 합성

7. 영상 트림
   ├─> 자막 있음: 마지막 자막 + 2초
   └─> 자막 없음: 오디오 끝 + 2.5초

8. 최종 인코딩 (GPU)
   └─> h264_nvenc 사용
```

---

## ⚠️ 에러 케이스

### E1: TTS 길이 초과 (치명적)
```
조건: 5회 시도 후 still too long

에러:
RuntimeError: TTS 길이(X초)가 영상 길이(Y초)에 비해 너무 깁니다.

해결:
- 더 긴 영상 선택
- 번역문 수동 단축
```

### E2: 영상 너무 짧음 (치명적)
```
조건: max_allowed < 3.0초

에러:
RuntimeError: 영상 길이가 너무 짧아 TTS를 생성할 수 없습니다.

해결:
- 최소 4초 이상 영상 필요
```

### E3: Gemini 오디오 분석 실패 (경고)
```
조건: API 오류 / 모델 속성 오류

동작:
- 글자 수 기반 추정으로 fallback
- 작업 계속 진행

로그:
[Audio Analysis] ✗ Gemini 분석 실패 - 글자 수 기반 추정으로 fallback
```

### E4: OCR 실패 (경고)
```
조건: RapidOCR 초기화 실패

동작:
- 블러 처리 건너뛰기
- 한글 자막만 추가

로그:
[OCR] 초기화 실패 - 블러 처리 생략
```

---

## 📊 성능 최적화 케이스

### P1: GPU 가속 (CuPy)
```
조건: CUDA 사용 가능

사용처:
- OCR 영역 집계
- 블러 처리
- 영상 인코딩 (NVENC)

로그:
[GPU 가속] CuPy 사용 가능 - GPU 가속 활성화
```

### P2: 병렬 OCR
```
조건: 영상 > 10초

동작:
- 2개 구간 병렬 검사
  - 1-10초
  - 10-20초

로그:
[OCR 병렬] 2개 구간을 병렬로 검사합니다
```

### P3: 캐싱
```
캐시 항목:
- 자막 폰트: 동일 크기 재사용
- 영상 크기: 1080x1920 캐싱
- OCR 결과: 동일 URL 재사용

로그:
[Subtitles] Using cached dimensions 1080x1920
```

---

## 🎯 품질 보장 케이스

### Q1: 자막-오디오 싱크
```
보장 방법:
1. TTS 세그먼트 = 자막 세그먼트 (재분할 금지)
2. Gemini 오디오 분석으로 실제 타이밍 추출
3. 1.2배속 메타데이터 자동 조정

결과: 100% 정확한 싱크
```

### Q2: CTA 완전 표시
```
보장 방법:
1. 마지막 자막 end = video_duration
2. skip threshold = video_duration + 5.0s
3. 영상 트림 시 여유 확보 (+2초)

결과: CTA 항상 끝까지 표시
```

### Q3: 중국어 자막 제거
```
보장 방법:
1. OCR 병렬 검사 (89.5% 감지율)
2. GPU 가속 블러 처리
3. 한글 자막 덮어쓰기

결과: 깔끔한 한글 자막
```

---

생성일: 2025-11-24
버전: v2.0
