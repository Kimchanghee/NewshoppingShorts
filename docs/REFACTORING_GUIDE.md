# Refactoring Guide - File Splitting

이 문서는 대용량 파일들을 작은 모듈로 분할하는 가이드입니다.
This document guides splitting large files into smaller modules.

---

## 파일 분할이 필요한 이유 / Why Split Files

**문제점 / Problems**:
- 1000+ 줄 파일은 이해하기 어려움 / Hard to understand 1000+ line files
- 병합 충돌 빈번 / Frequent merge conflicts
- 테스트 작성 어려움 / Difficult to test
- 재사용 불가능 / Not reusable

**목표 / Goals**:
- 파일당 200-400 줄 (최대 800줄) / 200-400 lines per file (max 800)
- 높은 응집도, 낮은 결합도 / High cohesion, low coupling
- 기능별 분리 / Separate by function
- 테스트 가능 / Testable

---

## Phase 1: main.py 분할 (1837 lines → 5 modules)

### Current Structure

```python
# main.py (1837 lines)
- Imports (50 lines)
- Global variables (30 lines)
- MainWindow class (1700+ lines)
  - __init__()
  - UI setup methods
  - Event handlers
  - Business logic
  - Utility functions
```

### Target Structure

```
main.py (200 lines)
├── ui/
│   ├── main_window.py (400 lines)
│   │   └── MainWindow class (UI setup only)
│   ├── event_handlers.py (300 lines)
│   │   └── Event callbacks
│   └── ui_helpers.py (200 lines)
│       └── UI utility functions
├── core/
│   ├── application.py (400 lines)
│   │   └── Business logic
│   └── state_manager.py (200 lines)
│       └── Application state
```

### Migration Steps

#### Step 1: Extract Event Handlers

```python
# ui/event_handlers.py
"""Event handlers for MainWindow"""

class EventHandlers:
    def __init__(self, window):
        self.window = window

    def on_video_selected(self, path: str):
        """Handle video selection event"""
        # Move from MainWindow
        pass

    def on_process_clicked(self):
        """Handle process button click"""
        # Move from MainWindow
        pass

# main.py - Usage
from ui.event_handlers import EventHandlers

class MainWindow:
    def __init__(self):
        self.handlers = EventHandlers(self)
        self.process_button.clicked.connect(self.handlers.on_process_clicked)
```

#### Step 2: Extract Business Logic

```python
# core/application.py
"""Application business logic"""

class ApplicationCore:
    def __init__(self):
        self.state = StateManager()

    def process_video(self, video_path: str) -> bool:
        """Process video workflow"""
        # Move from MainWindow
        pass

# main.py - Usage
from core.application import ApplicationCore

class MainWindow:
    def __init__(self):
        self.core = ApplicationCore()
```

#### Step 3: Extract State Management

```python
# core/state_manager.py
"""Application state management"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class AppState:
    current_video: Optional[str] = None
    is_processing: bool = False
    ocr_reader: Optional[object] = None

class StateManager:
    def __init__(self):
        self.state = AppState()

    def set_current_video(self, path: str):
        self.state.current_video = path
```

---

## Phase 2: ssmaker.py 분할 (1512 lines → 3 modules)

### Current Structure

```python
# ssmaker.py (1512 lines)
- Package installation logic (600 lines)
- Dependency checking (400 lines)
- System validation (300 lines)
- Entry point (200 lines)
```

### Target Structure

```
ssmaker.py (200 lines)
└── core/
    ├── package_manager.py (500 lines)
    │   └── Package installation
    ├── dependency_checker.py (400 lines)
    │   └── Dependency validation
    └── system_validator.py (400 lines)
        └── System checks
```

### Migration Steps

#### Step 1: Extract Package Manager

```python
# core/package_manager.py
"""Package installation and management"""

class PackageManager:
    def install_package(self, package: str) -> bool:
        """Install Python package via pip"""
        pass

    def check_installed(self, package: str) -> bool:
        """Check if package is installed"""
        pass

# ssmaker.py - Usage
from core.package_manager import PackageManager

pm = PackageManager()
if not pm.check_installed("PyQt5"):
    pm.install_package("PyQt5")
```

---

## Phase 3: subtitle_detector.py 분할 (1464 lines → 4 modules)

### Current Structure

```python
# processors/subtitle_detector.py (1464 lines)
- SubtitleDetector class (1400+ lines)
  - OCR operations (400 lines)
  - Region filtering (300 lines)
  - Frame processing (400 lines)
  - Helper methods (300 lines)
```

### Target Structure

```
processors/subtitle_detector/
├── __init__.py (50 lines)
├── detector.py (400 lines)
│   └── SubtitleDetector (main class)
├── ocr_processor.py (300 lines)
│   └── OCR operations
├── region_filter.py (300 lines)
│   └── Region filtering
└── frame_processor.py (300 lines)
    └── Frame processing
```

### Migration Steps

#### Step 1: Extract OCR Processor

```python
# processors/subtitle_detector/ocr_processor.py
"""OCR processing operations"""

class OCRProcessor:
    def __init__(self, ocr_reader):
        self.ocr_reader = ocr_reader

    def process_frame(self, frame):
        """Run OCR on frame"""
        pass

# processors/subtitle_detector/detector.py
from .ocr_processor import OCRProcessor

class SubtitleDetector:
    def __init__(self, gui):
        self.ocr = OCRProcessor(gui.ocr_reader)
```

#### Step 2: Extract Region Filter

```python
# processors/subtitle_detector/region_filter.py
"""Subtitle region filtering"""

class RegionFilter:
    @staticmethod
    def filter_by_position(regions, y_threshold=0.5):
        """Filter regions by vertical position"""
        pass

    @staticmethod
    def merge_overlapping(regions, iou_threshold=0.3):
        """Merge overlapping regions"""
        pass
```

#### Step 3: Public API (Backward Compatibility)

```python
# processors/subtitle_detector/__init__.py
"""
Subtitle detector package

Backward compatibility: Import SubtitleDetector from main module
"""

from .detector import SubtitleDetector

__all__ = ['SubtitleDetector']

# Old code still works:
# from processors.subtitle_detector import SubtitleDetector
```

---

## 분할 시 주의사항 / Cautions

### ✅ DO

1. **한 번에 하나씩 / One at a time**
   - 파일 하나씩 분할 / Split one file at a time
   - 각 단계마다 테스트 / Test after each step

2. **Backward Compatibility 유지**
   ```python
   # __init__.py
   from .new_module import OldClass
   ```

3. **순환 의존성 방지 / Avoid Circular Imports**
   - 의존성 방향 확인 / Check dependency direction
   - 필요시 인터페이스 분리 / Separate interfaces if needed

4. **테스트 작성 / Write Tests**
   ```python
   # tests/test_refactored_module.py
   def test_backward_compatibility():
       # Old import still works
       from processors.subtitle_detector import SubtitleDetector
       detector = SubtitleDetector(mock_gui)
       assert detector is not None
   ```

### ❌ DON'T

1. **여러 파일 동시 분할 / Don't split multiple files at once**
   - 디버깅 어려움 / Hard to debug

2. **기능 변경 / Don't change functionality**
   - 리팩터링과 기능 추가 분리 / Separate refactoring from feature addition

3. **테스트 없이 진행 / Don't proceed without tests**
   - 회귀 버그 발생 가능 / Risk of regression bugs

---

## 검증 체크리스트 / Verification Checklist

분할 후 다음을 확인하세요 / Verify after splitting:

- [ ] 모든 import 문이 작동함 / All imports work
- [ ] 기존 테스트가 통과함 / Existing tests pass
- [ ] 새 구조로 import 가능 / New structure imports work
- [ ] 이전 구조로도 import 가능 (backward compatibility) / Old imports still work
- [ ] 순환 의존성 없음 / No circular dependencies
- [ ] 각 파일이 800줄 미만 / Each file < 800 lines

---

## 실행 순서 / Execution Order

1. **main.py 분할**
   ```bash
   # 1. 테스트 작성
   pytest tests/test_main_window.py

   # 2. EventHandlers 추출
   # 3. ApplicationCore 추출
   # 4. StateManager 추출
   # 5. 테스트 확인
   pytest tests/
   ```

2. **ssmaker.py 분할**
   ```bash
   # Similar process
   ```

3. **subtitle_detector.py 분할**
   ```bash
   # Similar process
   ```

---

## 도구 / Tools

### Import 분석 / Import Analysis
```bash
# Find all imports of a module
grep -r "from processors.subtitle_detector import" --include="*.py"
```

### 의존성 그래프 / Dependency Graph
```bash
# Install pydeps
pip install pydeps

# Generate dependency graph
pydeps processors/subtitle_detector.py --max-bacon=2
```

### 파일 크기 확인 / Check File Sizes
```bash
# Find large files
find . -name "*.py" -exec wc -l {} + | sort -rn | head -20
```

---

## 참고 자료 / References

- [Clean Code by Robert C. Martin](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350882)
- [Refactoring by Martin Fowler](https://refactoring.com/)
- Python Module Best Practices: https://docs.python.org/3/tutorial/modules.html

---

**Last Updated**: 2026-01-25
