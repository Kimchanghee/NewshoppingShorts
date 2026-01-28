# Progress Reporting Guide

진행 상황 보고 가이드

---

## 목적 / Purpose

**Why Progress Reporting?**
- 사용자 경험 개선 / Improve user experience
- 작업 진행 상황 가시화 / Visualize task progress
- 예상 완료 시간 제공 / Provide estimated completion time
- UI 프리징 방지 / Prevent UI freezing

---

## 구현 방법 / Implementation Methods

### 1. GUI Update Method

MainWindow에 `update_progress_state` 메서드가 있다고 가정합니다.
Assume MainWindow has `update_progress_state` method.

```python
def update_progress_state(
    self,
    task_name: str,
    status: str,
    progress: int,
    message: str = ""
):
    """
    진행 상황 업데이트 / Update progress state

    Args:
        task_name: 작업 이름 (예: "subtitle_detection")
        status: 상태 ("processing", "completed", "error")
        progress: 진행률 0-100
        message: 상태 메시지
    """
    pass
```

---

## 적용 위치 / Application Points

### 1. Subtitle Detection

```python
# processors/subtitle_detector.py

def detect_subtitles_with_opencv(self):
    """OCR 기반 자막 감지"""

    # 초기화 / Initialization
    self.gui.update_progress_state(
        task_name="subtitle_detection",
        status="processing",
        progress=0,
        message="비디오 로딩 중... / Loading video..."
    )

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    # 세그먼트별 진행 상황 / Progress per segment
    segment_duration = 10  # seconds
    total_segments = int((total_frames / fps) / segment_duration) + 1

    for segment_idx in range(total_segments):
        # 세그먼트 시작 / Segment start
        progress = int((segment_idx / total_segments) * 100)
        self.gui.update_progress_state(
            task_name="subtitle_detection",
            status="processing",
            progress=progress,
            message=f"세그먼트 {segment_idx + 1}/{total_segments} 처리 중... / Processing segment {segment_idx + 1}/{total_segments}..."
        )

        # 세그먼트 처리 / Process segment
        segment_results = self._analyze_video_segment(...)

    # 완료 / Completion
    self.gui.update_progress_state(
        task_name="subtitle_detection",
        status="completed",
        progress=100,
        message=f"{len(regions)}개 자막 영역 감지 완료 / Detected {len(regions)} subtitle regions"
    )

    return regions
```

### 2. Subtitle Processing (Blur)

```python
# processors/subtitle_processor.py

def process_blur_subtitles(self, regions):
    """자막 블러 처리"""

    total_frames = len(regions)

    for idx, region in enumerate(regions):
        # 10프레임마다 진행 상황 업데이트 / Update every 10 frames
        if idx % 10 == 0:
            progress = int((idx / total_frames) * 100)
            self.gui.update_progress_state(
                task_name="subtitle_blur",
                status="processing",
                progress=progress,
                message=f"프레임 {idx}/{total_frames} 블러 처리 중... / Blurring frame {idx}/{total_frames}..."
            )

        # 블러 처리 / Apply blur
        blurred_frame = self._apply_blur(region)

    # 완료 / Completion
    self.gui.update_progress_state(
        task_name="subtitle_blur",
        status="completed",
        progress=100,
        message="블러 처리 완료 / Blur processing completed"
    )
```

### 3. TTS Generation

```python
# processors/tts_processor.py

def generate_tts_for_segments(self, segments):
    """세그먼트별 TTS 생성"""

    total_segments = len(segments)

    for idx, segment in enumerate(segments):
        progress = int((idx / total_segments) * 100)
        self.gui.update_progress_state(
            task_name="tts_generation",
            status="processing",
            progress=progress,
            message=f"세그먼트 {idx + 1}/{total_segments} 음성 생성 중... / Generating voice for segment {idx + 1}/{total_segments}..."
        )

        # TTS 생성 / Generate TTS
        audio = self._generate_audio(segment)

    self.gui.update_progress_state(
        task_name="tts_generation",
        status="completed",
        progress=100,
        message="음성 생성 완료 / Voice generation completed"
    )
```

### 4. Video Composition

```python
# core/video/CreateFinalVideo.py

def create_final_video(self, video_path, audio_path, output_path):
    """최종 비디오 합성"""

    self.gui.update_progress_state(
        task_name="video_composition",
        status="processing",
        progress=0,
        message="비디오 합성 시작... / Starting video composition..."
    )

    # 비디오 로딩 / Load video
    self.gui.update_progress_state(
        task_name="video_composition",
        status="processing",
        progress=20,
        message="비디오 로딩... / Loading video..."
    )

    # 오디오 합성 / Merge audio
    self.gui.update_progress_state(
        task_name="video_composition",
        status="processing",
        progress=50,
        message="오디오 합성 중... / Merging audio..."
    )

    # 인코딩 / Encoding
    self.gui.update_progress_state(
        task_name="video_composition",
        status="processing",
        progress=75,
        message="비디오 인코딩 중... / Encoding video..."
    )

    # 완료 / Completion
    self.gui.update_progress_state(
        task_name="video_composition",
        status="completed",
        progress=100,
        message=f"비디오 저장 완료: {output_path} / Video saved: {output_path}"
    )
```

---

## UI 컴포넌트 / UI Components

### Progress Bar (PyQt5)

```python
from PyQt5.QtWidgets import QProgressBar, QLabel

class MainWindow:
    def __init__(self):
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)

        # Status label
        self.status_label = QLabel("준비 중... / Ready...")

    def update_progress_state(self, task_name, status, progress, message):
        """진행 상황 UI 업데이트"""

        # Progress bar 업데이트
        self.progress_bar.setValue(progress)

        # Status label 업데이트
        self.status_label.setText(message)

        # Status에 따라 색상 변경 / Change color based on status
        if status == "processing":
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
        elif status == "completed":
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #2196F3; }")
        elif status == "error":
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #F44336; }")

        # UI 업데이트 강제 / Force UI update
        QApplication.processEvents()
```

---

## 멀티스레드 환경 / Multi-threading

작업이 백그라운드 스레드에서 실행되는 경우:
When tasks run in background threads:

```python
from PyQt5.QtCore import QThread, pyqtSignal

class ProcessingThread(QThread):
    """백그라운드 처리 스레드 / Background processing thread"""

    # 진행 상황 시그널 / Progress signal
    progress_signal = pyqtSignal(str, str, int, str)  # task, status, progress, message

    def run(self):
        """스레드 실행 / Thread execution"""
        # 진행 상황 전송 / Emit progress
        self.progress_signal.emit(
            "subtitle_detection",
            "processing",
            50,
            "처리 중... / Processing..."
        )

# MainWindow에서 사용 / Usage in MainWindow
class MainWindow:
    def start_processing(self):
        self.thread = ProcessingThread()
        self.thread.progress_signal.connect(self.update_progress_state)
        self.thread.start()
```

---

## 예상 완료 시간 (ETA) / Estimated Time of Arrival

```python
import time
from datetime import datetime, timedelta

class ProgressTracker:
    """진행 상황 추적 및 ETA 계산 / Track progress and calculate ETA"""

    def __init__(self, total_items: int):
        self.total_items = total_items
        self.completed_items = 0
        self.start_time = time.time()

    def update(self, completed: int) -> dict:
        """
        진행 상황 업데이트 및 ETA 계산
        Update progress and calculate ETA

        Returns:
            {
                'progress': int,  # 0-100
                'eta_seconds': float,
                'eta_str': str  # "2m 30s"
            }
        """
        self.completed_items = completed

        if completed == 0:
            return {'progress': 0, 'eta_seconds': 0, 'eta_str': 'N/A'}

        elapsed = time.time() - self.start_time
        progress = int((completed / self.total_items) * 100)

        # ETA 계산 / Calculate ETA
        items_per_second = completed / elapsed
        remaining_items = self.total_items - completed
        eta_seconds = remaining_items / items_per_second if items_per_second > 0 else 0

        # 시간 형식 변환 / Format time
        eta_str = self._format_time(eta_seconds)

        return {
            'progress': progress,
            'eta_seconds': eta_seconds,
            'eta_str': eta_str
        }

    def _format_time(self, seconds: float) -> str:
        """시간을 "1h 23m 45s" 형식으로 변환 / Format time as "1h 23m 45s" """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

# 사용 예시 / Usage example
tracker = ProgressTracker(total_items=100)

for i in range(100):
    # 작업 수행 / Do work
    process_item(i)

    # 진행 상황 업데이트 / Update progress
    if i % 10 == 0:
        info = tracker.update(i)
        gui.update_progress_state(
            "task",
            "processing",
            info['progress'],
            f"진행 중... 남은 시간: {info['eta_str']} / Processing... ETA: {info['eta_str']}"
        )
```

---

## 에러 처리 / Error Handling

```python
def process_with_progress(self):
    """에러가 발생해도 진행 상황 표시 / Show progress even on errors"""

    try:
        self.gui.update_progress_state(
            "task",
            "processing",
            0,
            "작업 시작... / Starting task..."
        )

        # 작업 수행 / Do work
        result = perform_task()

        # 성공 / Success
        self.gui.update_progress_state(
            "task",
            "completed",
            100,
            "작업 완료 / Task completed"
        )

    except Exception as e:
        # 실패 / Failure
        self.gui.update_progress_state(
            "task",
            "error",
            -1,  # -1 indicates error
            f"에러 발생: {str(e)} / Error occurred: {str(e)}"
        )

        # 에러 로깅 / Log error
        logger.error(f"Task failed: {e}", exc_info=True)

        raise
```

---

## 완료 기준 / Completion Criteria

- [ ] 모든 주요 작업에 진행 상황 보고 추가
  - [ ] Subtitle detection
  - [ ] Subtitle processing (blur)
  - [ ] TTS generation
  - [ ] Video composition
- [ ] ETA 계산 구현
- [ ] 에러 발생 시 UI 업데이트
- [ ] 멀티스레드 환경에서 안전한 UI 업데이트

---

**Last Updated**: 2026-01-25
