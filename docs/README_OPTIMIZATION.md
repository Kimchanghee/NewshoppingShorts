# Shopping Shorts Maker - 시스템 최적화 가이드

## 새로운 기능: 자동 시스템 최적화

프로그램이 이제 사용자의 컴퓨터 사양을 자동으로 감지하고 최적의 설정으로 실행됩니다.

### 주요 개선사항

1. **CPU 코어 수 자동 감지 및 최적화**
   - 시스템의 CPU 코어 수를 감지하여 병렬 처리 워커 수를 자동 조정
   - 로우엔드 PC(4코어 이하) → 적은 워커 수 사용
   - 하이엔드 PC(8코어 이상) → 더 많은 워커 수 사용

2. **메모리 사용량 동적 제한**
   - 시스템의 총 메모리를 감지하여 사용량 제한 설정
   - 메모리 부족 시 자동으로 리소스 사용 감소

3. **Whisper 모델 자동 선택**
   - 시스템 사양에 따라 Whisper 모델 크기 자동 선택:
     - 로우엔드(4GB RAM 미만): `tiny` 모델
     - 미드레인지: `tiny` 모델
     - 하이엔드(16GB RAM 이상): `base` 모델

4. **OCR 처리 최적화**
   - 샘플링 간격 자동 조정 (0.3초 ~ 0.7초)
   - 분석 영역 최적화 (하단 30% ~ 35%)
   - 이미지 해상도 자동 다운스케일

### 설치 방법

1. **의존성 패키지 설치**
   ```bash
   python install_dependencies.py
   ```

2. **시스템 최적화 확인**
   프로그램을 실행하면 시작 시 시스템 정보와 최적화 설정이 출력됩니다.

### 시스템 요구사항

#### 최소 사양
- CPU: 2코어 이상
- RAM: 4GB 이상
- 저장공간: 2GB 이상
- OS: Windows 10/11, macOS, Linux

#### 권장 사양
- CPU: 4코어 이상
- RAM: 8GB 이상
- 저장공간: 5GB 이상
- GPU: NVIDIA GPU (선택사항, 가속용)

### 최적화 설정 예시

#### 로우엔드 PC (4GB RAM, 2코어)
```
OCR 샘플링 간격: 0.7초
병렬 워커: 1개
Whisper 모델: tiny
이미지 다운스케일: 720px
```

#### 미드레인지 PC (8GB RAM, 4코어)
```
OCR 샘플링 간격: 0.5초
병렬 워커: 2개
Whisper 모델: tiny
이미지 다운스케일: 960px
```

#### 하이엔드 PC (16GB RAM, 8코어)
```
OCR 샘플링 간격: 0.3초
병렬 워커: 4개
Whisper 모델: base
이미지 다운스케일: 1440px
```

### 문제 해결

#### 1. 패키지 설치 실패 시
```bash
# pip 업그레이드 후 재시도
python -m pip install --upgrade pip
python install_dependencies.py
```

#### 2. 시스템 감지 실패 시
- `psutil` 패키지가 설치되어 있는지 확인
- 관리자 권한으로 실행 시도 (Windows)

#### 3. 메모리 부족 시
- 다른 프로그램 종료
- 가상 메모리 증가 (Windows)
- `system_optimizer.py`에서 메모리 제한 수정

### 수동 설정 변경

`utils/system_optimizer.py` 파일에서 수동으로 설정을 변경할 수 있습니다:

```python
# 메모리 제한 변경 (GB 단위)
max_memory_usage_gb = 4.0  # 기본: 시스템 메모리의 50%

# OCR 샘플링 간격 강제 설정
ocr_sample_interval = 0.5  # 기본: 시스템에 따라 0.3-0.7초

# 병렬 워커 수 강제 설정
max_parallel_workers = 2   # 기본: CPU 코어 수에 따라
```

### 성능 모니터링

프로그램 실행 중 콘솔에서 시스템 최적화 리포트를 확인할 수 있습니다:
```
============================================================
SYSTEM OPTIMIZATION REPORT
============================================================
Platform: Windows (AMD64)
CPU Cores: 12 (Logical: 12)
Total Memory: 16.0 GB
Available Memory: 8.5 GB
System Type: Mid-range
Has GPU: True
GPU Memory: 6.0 GB

OPTIMIZATION SETTINGS:
  OCR Sample Interval: 0.5s
  Max Parallel Workers: 3
  Whisper Model: tiny
  Whisper Threads: 6
  Image Downscale: 1280px
  ROI Bottom Percent: 35%
  Max Memory Usage: 8.0 GB
  GPU Acceleration: True
  Caching Enabled: True
  Batch Size: 2
============================================================
```

### 주의사항

1. **GPU 가속**: NVIDIA GPU가 있는 경우 자동으로 감지되어 가속이 활성화됩니다.
2. **메모리 사용**: 대용량 영상 처리 시 메모리 사용량이 증가할 수 있습니다.
3. **처리 시간**: 로우엔드 PC에서는 처리 시간이 길어질 수 있습니다.
4. **품질**: 최적화로 인해 처리 품질이 약간 저하될 수 있지만, 대부분의 경우 눈에 띄지 않습니다.

### 지원

문제가 있으면 다음 정보와 함께 문의해주세요:
1. 시스템 최적화 리포트 전체 내용
2. 발생한 오류 메시지
3. 처리 중인 영상 정보
4. 시스템 사양 (CPU, RAM, GPU)