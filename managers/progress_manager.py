"""
진행상태 관리 모듈

Model-View 패턴으로 분리:
- ProgressModel: 순수 상태 데이터 관리 + 옵저버 패턴
- ProgressManager: UI 업데이트 담당 (View 역할)
"""
import os
import threading
import random
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable
from urllib.parse import urlparse

from utils.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# 옵저버 패턴 인터페이스
# Observer Pattern Interface
# =============================================================================

class ProgressObserver(ABC):
    """
    진행상태 변경을 관찰하는 옵저버 인터페이스
    Observer interface for progress state changes
    """

    @abstractmethod
    def on_progress_changed(self, step: str, state: Dict[str, Any]) -> None:
        """
        진행상태 변경 시 호출되는 콜백
        Callback invoked when progress state changes

        Args:
            step: 변경된 단계 이름 (step name that changed)
            state: 해당 단계의 새로운 상태 (new state for the step)
        """
        pass

    @abstractmethod
    def on_all_reset(self) -> None:
        """
        모든 상태가 초기화될 때 호출
        Callback invoked when all states are reset
        """
        pass

    @abstractmethod
    def on_job_changed(self, job_info: Dict[str, Any]) -> None:
        """
        현재 작업 정보가 변경될 때 호출
        Callback invoked when current job info changes

        Args:
            job_info: 작업 정보 딕셔너리 (job information dictionary)
        """
        pass

    @abstractmethod
    def on_voice_changed(self, voice_info: Dict[str, Any]) -> None:
        """
        현재 음성 정보가 변경될 때 호출
        Callback invoked when current voice info changes

        Args:
            voice_info: 음성 정보 딕셔너리 (voice information dictionary)
        """
        pass


# =============================================================================
# 진행상태 모델 (순수 데이터 관리)
# Progress Model (Pure Data Management)
# =============================================================================

class ProgressModel:
    """
    진행상태 데이터를 관리하는 모델 클래스
    Model class that manages progress state data

    책임:
    - 각 단계별 진행상태 저장 (status, progress, message)
    - 현재 작업/음성 정보 저장
    - 상태 변경 시 등록된 옵저버에게 알림

    Responsibilities:
    - Store progress state per step (status, progress, message)
    - Store current job/voice information
    - Notify registered observers on state changes
    """

    # 단계별 기본 가중치 (전체 진행률 계산용)
    # Default weights per step (for overall progress calculation)
    DEFAULT_STEP_WEIGHTS: Dict[str, int] = {
        'download': 5,
        'analysis': 15,
        'ocr_analysis': 10,
        'translation': 10,
        'tts': 15,
        'subtitle': 10,
        'audio_analysis': 10,
        'subtitle_overlay': 10,
        'video': 10,
        'finalize': 5
    }

    def __init__(self):
        """
        모델 초기화
        Initialize model
        """
        # 단계별 진행상태 저장소
        # Progress states storage per step
        self._progress_states: Dict[str, Dict[str, Any]] = {}

        # 현재 작업 정보
        # Current job information
        self._current_job_index: Optional[int] = None
        self._current_job_total: Optional[int] = None
        self._current_job_header: Optional[str] = None

        # 현재 음성 정보
        # Current voice information
        self._current_voice_id: Optional[str] = None
        self._current_voice_index: Optional[int] = None
        self._current_voice_total: Optional[int] = None
        self._current_voice_label: Optional[str] = None

        # 스테이지 메시지 캐시 (동일 메시지 반복 방지)
        # Stage message cache (prevent same message repetition)
        self._stage_message_cache: Dict[str, str] = {}

        # 옵저버 목록
        # Observer list
        self._observers: List[ProgressObserver] = []

        # 스레드 안전을 위한 락
        # Lock for thread safety
        self._lock = threading.RLock()

    # -------------------------------------------------------------------------
    # 옵저버 관리 메서드
    # Observer Management Methods
    # -------------------------------------------------------------------------

    def add_observer(self, observer: ProgressObserver) -> None:
        """
        옵저버 등록
        Register an observer

        Args:
            observer: 등록할 옵저버 (observer to register)
        """
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)
                logger.debug(f"[ProgressModel] Observer added: {type(observer).__name__}")

    def remove_observer(self, observer: ProgressObserver) -> None:
        """
        옵저버 제거
        Remove an observer

        Args:
            observer: 제거할 옵저버 (observer to remove)
        """
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
                logger.debug(f"[ProgressModel] Observer removed: {type(observer).__name__}")

    def _notify_progress_changed(self, step: str, state: Dict[str, Any]) -> None:
        """
        진행상태 변경을 모든 옵저버에게 알림
        Notify all observers of progress state change

        Args:
            step: 변경된 단계 (changed step)
            state: 새로운 상태 (new state)
        """
        with self._lock:
            observers_copy = self._observers.copy()

        for observer in observers_copy:
            try:
                observer.on_progress_changed(step, state.copy())
            except Exception as e:
                logger.error(f"[ProgressModel] Observer notification error: {e}")

    def _notify_all_reset(self) -> None:
        """
        전체 초기화를 모든 옵저버에게 알림
        Notify all observers of full reset
        """
        with self._lock:
            observers_copy = self._observers.copy()

        for observer in observers_copy:
            try:
                observer.on_all_reset()
            except Exception as e:
                logger.error(f"[ProgressModel] Observer reset notification error: {e}")

    def _notify_job_changed(self) -> None:
        """
        작업 정보 변경을 모든 옵저버에게 알림
        Notify all observers of job info change
        """
        job_info = {
            'index': self._current_job_index,
            'total': self._current_job_total,
            'header': self._current_job_header
        }

        with self._lock:
            observers_copy = self._observers.copy()

        for observer in observers_copy:
            try:
                observer.on_job_changed(job_info)
            except Exception as e:
                logger.error(f"[ProgressModel] Observer job notification error: {e}")

    def _notify_voice_changed(self) -> None:
        """
        음성 정보 변경을 모든 옵저버에게 알림
        Notify all observers of voice info change
        """
        voice_info = {
            'id': self._current_voice_id,
            'index': self._current_voice_index,
            'total': self._current_voice_total,
            'label': self._current_voice_label
        }

        with self._lock:
            observers_copy = self._observers.copy()

        for observer in observers_copy:
            try:
                observer.on_voice_changed(voice_info)
            except Exception as e:
                logger.error(f"[ProgressModel] Observer voice notification error: {e}")

    # -------------------------------------------------------------------------
    # 상태 관리 메서드
    # State Management Methods
    # -------------------------------------------------------------------------

    def initialize_steps(self, steps: List[str]) -> None:
        """
        단계 목록 초기화
        Initialize step list

        Args:
            steps: 초기화할 단계 이름 목록 (list of step names to initialize)
        """
        with self._lock:
            for step in steps:
                if step not in self._progress_states:
                    self._progress_states[step] = {
                        'status': 'waiting',
                        'progress': 0,
                        'message': None
                    }

    def get_state(self, step: str) -> Dict[str, Any]:
        """
        특정 단계의 상태 조회
        Get state of a specific step

        Args:
            step: 조회할 단계 이름 (step name to query)

        Returns:
            상태 딕셔너리 복사본 (copy of state dictionary)
        """
        with self._lock:
            state = self._progress_states.get(step, {
                'status': 'waiting',
                'progress': 0,
                'message': None
            })
            return state.copy()

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """
        모든 단계의 상태 조회
        Get states of all steps

        Returns:
            전체 상태 딕셔너리의 깊은 복사본 (deep copy of all states)
        """
        with self._lock:
            return {
                step: state.copy()
                for step, state in self._progress_states.items()
            }

    def update_state(
        self,
        step: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None
    ) -> None:
        """
        단계 상태 업데이트
        Update step state

        Args:
            step: 업데이트할 단계 (step to update)
            status: 새로운 상태 (new status) - 'waiting', 'processing', 'completed', 'error'
            progress: 진행률 0-100 (progress percentage 0-100)
            message: 사용자 정의 메시지 (custom message)
        """
        with self._lock:
            if step not in self._progress_states:
                self._progress_states[step] = {
                    'status': 'waiting',
                    'progress': 0,
                    'message': None
                }

            state = self._progress_states[step]

            if status is not None:
                state['status'] = status
            if progress is not None:
                state['progress'] = max(0, min(100, progress))
            if message is not None:
                state['message'] = message

            state_copy = state.copy()

        # 락 밖에서 알림 (데드락 방지)
        # Notify outside lock (prevent deadlock)
        self._notify_progress_changed(step, state_copy)

    def reset_all(self) -> None:
        """
        모든 상태 초기화
        Reset all states
        """
        with self._lock:
            for state in self._progress_states.values():
                state['status'] = 'waiting'
                state['progress'] = 0
                state['message'] = None

            self._current_job_header = None
            self._current_job_index = None
            self._current_job_total = None
            self._current_voice_id = None
            self._current_voice_index = None
            self._current_voice_total = None
            self._current_voice_label = None
            self._stage_message_cache.clear()

        self._notify_all_reset()

    # -------------------------------------------------------------------------
    # 작업/음성 정보 관리
    # Job/Voice Information Management
    # -------------------------------------------------------------------------

    def set_job_info(
        self,
        index: Optional[int] = None,
        total: Optional[int] = None,
        header: Optional[str] = None
    ) -> None:
        """
        현재 작업 정보 설정
        Set current job information

        Args:
            index: 현재 작업 인덱스 (current job index)
            total: 전체 작업 수 (total job count)
            header: 작업 헤더/소스 (job header/source)
        """
        with self._lock:
            self._current_job_index = index
            self._current_job_total = total
            if header is not None:
                self._current_job_header = header
            # 작업 변경 시 음성 정보 초기화
            # Reset voice info on job change
            self._current_voice_label = None

        self._notify_job_changed()

    def get_job_info(self) -> Dict[str, Any]:
        """
        현재 작업 정보 조회
        Get current job information

        Returns:
            작업 정보 딕셔너리 (job info dictionary)
        """
        with self._lock:
            return {
                'index': self._current_job_index,
                'total': self._current_job_total,
                'header': self._current_job_header
            }

    def set_voice_info(
        self,
        voice_id: str,
        index: Optional[int] = None,
        total: Optional[int] = None,
        label: Optional[str] = None
    ) -> None:
        """
        현재 음성 정보 설정
        Set current voice information

        Args:
            voice_id: 음성 ID (voice ID)
            index: 현재 음성 인덱스 (current voice index)
            total: 전체 음성 수 (total voice count)
            label: 음성 라벨/이름 (voice label/name)
        """
        with self._lock:
            self._current_voice_id = voice_id
            self._current_voice_index = index
            self._current_voice_total = total
            self._current_voice_label = label

        self._notify_voice_changed()

    def get_voice_info(self) -> Dict[str, Any]:
        """
        현재 음성 정보 조회
        Get current voice information

        Returns:
            음성 정보 딕셔너리 (voice info dictionary)
        """
        with self._lock:
            return {
                'id': self._current_voice_id,
                'index': self._current_voice_index,
                'total': self._current_voice_total,
                'label': self._current_voice_label
            }

    # -------------------------------------------------------------------------
    # 진행률 계산 유틸리티
    # Progress Calculation Utilities
    # -------------------------------------------------------------------------

    def calculate_overall_progress(
        self,
        weights: Optional[Dict[str, int]] = None
    ) -> float:
        """
        전체 진행률 계산 (가중치 기반)
        Calculate overall progress (weight-based)

        Args:
            weights: 단계별 가중치 딕셔너리 (optional, 기본값 사용)
                     (step weights dictionary, uses defaults if not provided)

        Returns:
            전체 진행률 0-100 (overall progress 0-100)
        """
        if weights is None:
            weights = self.DEFAULT_STEP_WEIGHTS

        total_weight = sum(weights.values())
        if total_weight <= 0:
            return 0.0

        completed_weight = 0.0

        with self._lock:
            for step, weight in weights.items():
                state = self._progress_states.get(step, {})
                status = state.get('status', 'waiting')
                step_progress = state.get('progress') or 0

                if not isinstance(step_progress, (int, float)):
                    step_progress = 0

                if status == 'completed':
                    completed_weight += weight
                elif status == 'processing':
                    completed_weight += (weight * step_progress / 100)

        return (completed_weight / total_weight) * 100

    def get_current_processing_step(self) -> Optional[str]:
        """
        현재 진행 중인 단계 조회
        Get currently processing step

        Returns:
            진행 중인 단계 이름 또는 None (processing step name or None)
        """
        with self._lock:
            for step, state in self._progress_states.items():
                if state.get('status') == 'processing':
                    return step
        return None

    def cache_stage_message(self, step: str, message: str) -> None:
        """
        스테이지 메시지 캐시 저장
        Cache stage message

        Args:
            step: 단계 이름 (step name)
            message: 캐시할 메시지 (message to cache)
        """
        with self._lock:
            self._stage_message_cache[step] = message

    def get_cached_stage_message(self, step: str) -> Optional[str]:
        """
        캐시된 스테이지 메시지 조회
        Get cached stage message

        Args:
            step: 단계 이름 (step name)

        Returns:
            캐시된 메시지 또는 None (cached message or None)
        """
        with self._lock:
            return self._stage_message_cache.get(step)


# =============================================================================
# 진행상태 매니저 (UI 업데이트 담당)
# Progress Manager (UI Update Handler)
# =============================================================================

class ProgressManager(ProgressObserver):
    """
    진행상태 UI 업데이트를 담당하는 매니저 클래스
    Manager class responsible for progress UI updates

    책임:
    - ProgressModel의 상태 변경 감지 (옵저버)
    - GUI 위젯 업데이트
    - 상태별 메시지/색상/아이콘 결정
    - 스레드 안전한 UI 업데이트

    Responsibilities:
    - Observe ProgressModel state changes
    - Update GUI widgets
    - Determine status-specific messages/colors/icons
    - Thread-safe UI updates
    """

    def __init__(self, gui, model: Optional[ProgressModel] = None):
        """
        매니저 초기화
        Initialize manager

        Args:
            gui: VideoAnalyzerGUI 인스턴스 (parent GUI)
            model: ProgressModel 인스턴스 (optional, 자동 생성)
                   (optional, auto-created if not provided)
        """
        self.gui = gui

        # 모델 설정 (없으면 새로 생성)
        # Set up model (create new if not provided)
        if model is not None:
            self._model = model
        else:
            self._model = ProgressModel()

        # 옵저버로 등록
        # Register as observer
        self._model.add_observer(self)

        # GUI의 progress_states를 모델과 동기화 (하위 호환성)
        # Sync GUI's progress_states with model (backward compatibility)
        self._sync_gui_states()

    @property
    def model(self) -> ProgressModel:
        """
        진행상태 모델 접근자
        Progress model accessor

        Returns:
            ProgressModel 인스턴스
        """
        return self._model

    def _sync_gui_states(self) -> None:
        """
        GUI의 progress_states를 모델에 동기화
        Sync GUI's progress_states to model
        """
        if hasattr(self.gui, 'progress_states') and self.gui.progress_states:
            self._model.initialize_steps(list(self.gui.progress_states.keys()))

    # -------------------------------------------------------------------------
    # ProgressObserver 인터페이스 구현
    # ProgressObserver Interface Implementation
    # -------------------------------------------------------------------------

    def on_progress_changed(self, step: str, state: Dict[str, Any]) -> None:
        """
        진행상태 변경 시 UI 업데이트
        Update UI when progress state changes

        Args:
            step: 변경된 단계 (changed step)
            state: 새로운 상태 (new state)
        """
        status = state.get('status', 'waiting')
        progress = state.get('progress')
        message = state.get('message')

        # GUI progress_states 동기화 (하위 호환성)
        # Sync GUI progress_states (backward compatibility)
        if hasattr(self.gui, 'progress_states') and step in self.gui.progress_states:
            self.gui.progress_states[step] = state.copy()

        stage_message = self.get_stage_message(step, status)
        highlight_message = self._build_current_task_message(stage_message, status)

        def _apply_updates():
            self.update_all_progress_displays()
            self.refresh_stage_indicator(step, status, progress)

            # Update current task display (PyQt6 / State)
            if hasattr(self.gui, 'current_task_label'):
                self.gui.current_task_label.setText(highlight_message)
            
            # Update state for heartbeat
            if hasattr(self.gui, 'state'):
                self.gui.state.current_task_var = highlight_message
            elif hasattr(self.gui, 'current_task_var'):
                # Backward compatibility for StringVar or other types
                var = self.gui.current_task_var
                if hasattr(var, 'set'):
                    var.set(highlight_message)
                else:
                    self.gui.current_task_var = highlight_message

            # Status bar update (PyQt6 / Tkinter compatible)
            status_bar = getattr(self.gui, 'status_bar', None)
            if status_bar is not None:
                if hasattr(status_bar, 'showMessage'):
                    status_bar.showMessage(stage_message)
                elif hasattr(status_bar, 'setText'):
                    status_bar.setText(stage_message)
                elif hasattr(status_bar, 'config'):
                    status_bar.config(text=stage_message)

            # 깜빡임 효과 처리
            # Handle blink effect
            progress_panel = getattr(self.gui, 'progress_panel', None)
            if progress_panel is not None:
                if status == 'processing':
                    progress_panel.start_blink(step)
                else:
                    progress_panel.stop_blink()

            # 사이드바 미니 진행 패널 업데이트
            # Update sidebar mini progress panel
            self._update_sidebar_mini_progress(step, status)

        self._run_on_ui_thread(_apply_updates)

    def on_all_reset(self) -> None:
        """
        전체 초기화 시 UI 업데이트
        Update UI when all states reset
        """
        # GUI progress_states 초기화 (하위 호환성)
        # Reset GUI progress_states (backward compatibility)
        if hasattr(self.gui, 'progress_states'):
            for state in self.gui.progress_states.values():
                state['status'] = 'waiting'
                state['progress'] = 0
                state['message'] = None

        if hasattr(self.gui, '_stage_message_cache'):
            self.gui._stage_message_cache.clear()

        def _apply():
            for indicator in getattr(self.gui, 'step_indicators', {}).values():
                indicator['status_label'].config(text="⏸", fg=self.gui.secondary_text)
                progress_label = indicator.get('progress_label')
                if progress_label:
                    progress_label.config(text="0%", fg=self.gui.secondary_text)

            current_task_var = getattr(self.gui, 'current_task_var', None)
            if current_task_var is not None:
                current_task_var.set("대기 중")

            status_bar = getattr(self.gui, 'status_bar', None)
            if status_bar is not None:
                status_bar.config(text="준비 완료")

            self.update_all_progress_displays()

            # 사이드바 미니 진행 패널 초기화
            # Reset sidebar mini progress panel
            sidebar = getattr(self.gui, 'sidebar_container', None)
            if sidebar is not None:
                mini_progress = getattr(sidebar, 'progress_mini', None)
                if mini_progress is not None:
                    mini_progress.reset_steps()

        self._run_on_ui_thread(_apply)

    def on_job_changed(self, job_info: Dict[str, Any]) -> None:
        """
        작업 정보 변경 시 UI 업데이트
        Update UI when job info changes

        Args:
            job_info: 작업 정보 (job information)
        """
        # GUI 변수 동기화 (하위 호환성)
        # Sync GUI variables (backward compatibility)
        self.gui._current_job_index = job_info.get('index')
        self.gui._current_job_total = job_info.get('total')
        if job_info.get('header') is not None:
            self.gui._current_job_header = job_info.get('header')

        index = job_info.get('index')
        total = job_info.get('total')

        def _apply():
            if index and total:
                message = f"📹 {total}개 중 {index}번째 영상 준비 중"
            elif total:
                message = f"📹 총 {total}개 영상 준비 중"
            else:
                message = "📹 영상을 준비하고 있습니다"

            current_task_var = getattr(self.gui, 'current_task_var', None)
            if current_task_var is not None:
                current_task_var.set(message)

            status_bar = getattr(self.gui, 'status_bar', None)
            if status_bar is not None:
                status_bar.config(text=message)

            self.update_overall_progress_display()

        self._run_on_ui_thread(_apply)

    def on_voice_changed(self, voice_info: Dict[str, Any]) -> None:
        """
        음성 정보 변경 시 UI 업데이트
        Update UI when voice info changes

        Args:
            voice_info: 음성 정보 (voice information)
        """
        # GUI 변수 동기화 (하위 호환성)
        # Sync GUI variables (backward compatibility)
        self.gui._current_voice_id = voice_info.get('id')
        self.gui._current_voice_index = voice_info.get('index')
        self.gui._current_voice_total = voice_info.get('total')
        self.gui._current_voice_label = voice_info.get('label')

        voice_label = voice_info.get('label') or voice_info.get('id') or "알 수 없음"
        voice_index = voice_info.get('index')
        voice_total = voice_info.get('total')

        def _apply():
            job_index = getattr(self.gui, '_current_job_index', None)
            job_total = getattr(self.gui, '_current_job_total', None)

            parts = [f"🎤 {voice_label} 음성"]
            if voice_index and voice_total:
                parts.append(f"({voice_index}/{voice_total})")

            if job_index and job_total:
                parts.append(f"📹 {job_total}개 중 {job_index}번째 영상")
            elif job_total:
                parts.append(f"📹 총 {job_total}개 영상")

            parts.append("제작 중")

            if len(parts) > 2:
                message = " · ".join(parts[:2]) + " · " + " ".join(parts[2:])
            else:
                message = " · ".join(parts)

            current_task_var = getattr(self.gui, 'current_task_var', None)
            if current_task_var is not None:
                current_task_var.set(message)

            status_bar = getattr(self.gui, 'status_bar', None)
            if status_bar is not None:
                status_bar.config(text=message)

            self.update_overall_progress_display()

        self._run_on_ui_thread(_apply)

    # -------------------------------------------------------------------------
    # 공개 API 메서드 (기존 인터페이스 유지)
    # Public API Methods (Maintain Existing Interface)
    # -------------------------------------------------------------------------

    def update_progress_state(
        self,
        step: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None
    ) -> None:
        """
        진행상황 상태 업데이트
        Update progress state

        Args:
            step: 단계 이름 (step name)
            status: 상태 문자열 (status string)
            progress: 진행률 (progress percentage)
            message: 사용자 정의 메시지 (custom message)
        """
        # 모델에 상태 업데이트 -> 옵저버 패턴으로 UI 자동 업데이트
        # Update model state -> UI auto-updates via observer pattern
        self._model.update_state(step, status, progress, message)

    def reset_progress_states(self) -> None:
        """
        모든 단계 진행상황을 초기화
        Reset all step progress states
        """
        self._model.reset_all()

    def set_active_voice(
        self,
        voice_id: str,
        voice_index: Optional[int] = None,
        voice_total: Optional[int] = None
    ) -> None:
        """
        현재 처리 중인 음성 정보를 진행 카드에 반영
        Reflect current processing voice info in progress card

        Args:
            voice_id: 음성 ID (voice ID)
            voice_index: 현재 음성 인덱스 (current voice index)
            voice_total: 전체 음성 수 (total voice count)
        """
        voice_label = self.get_voice_label(voice_id)
        self._model.set_voice_info(voice_id, voice_index, voice_total, voice_label)

    def set_active_job(
        self,
        source: str,
        index: Optional[int] = None,
        total: Optional[int] = None
    ) -> None:
        """
        현재 처리 중인 작업 정보를 진행 카드에 반영
        Reflect current processing job info in progress card

        Args:
            source: 작업 소스 URL 또는 파일 경로 (job source URL or file path)
            index: 현재 작업 인덱스 (current job index)
            total: 전체 작업 수 (total job count)
        """
        formatted_source = self._format_job_source(source)
        self._model.set_job_info(index, total, formatted_source)

    def update_step_progress(self, step: str, value: float) -> None:
        """
        단계 진행률 갱신
        Update step progress

        Args:
            step: 단계 이름 (step name)
            value: 진행률 0-100 (progress 0-100)
        """
        value = max(0, min(100, int(value)))
        if value >= 100:
            status = 'completed'
        elif value > 0:
            status = 'processing'
        else:
            status = 'waiting'

        self._model.update_state(step, status, value)

    def update_overall_progress(
        self,
        step: str,
        status: str,
        progress: Optional[float] = None
    ) -> None:
        """
        전체 진행현황 표시 업데이트
        Update overall progress display

        Args:
            step: 단계 이름 (step name)
            status: 상태 문자열 (status string)
            progress: 진행률 (progress percentage)
        """
        self.refresh_stage_indicator(step, status, progress)

    # -------------------------------------------------------------------------
    # UI 업데이트 헬퍼 메서드
    # UI Update Helper Methods
    # -------------------------------------------------------------------------

    def _run_on_ui_thread(self, func: Callable[[], None]) -> None:
        """
        UI 스레드에서 함수 실행
        Run function on UI thread

        Args:
            func: 실행할 함수 (function to execute)
        """
        if threading.current_thread() is threading.main_thread():
            func()
        else:
            self.gui.root.after(0, func)

    def _update_sidebar_mini_progress(self, step: str, status: str) -> None:
        """
        사이드바 미니 진행 패널 업데이트
        Update sidebar mini progress panel

        Args:
            step: 단계 이름 (step name)
            status: 상태 문자열 (status string)
        """
        try:
            sidebar = getattr(self.gui, 'sidebar_container', None)
            if sidebar is None:
                return

            mini_panel = getattr(sidebar, 'progress_mini', None)
            if mini_panel is None:
                return

            # 스텝 상태 업데이트
            # Update step status
            mini_panel.update_step(step, status)

            # 상태 텍스트 업데이트
            # Update status text
            status_text = self.get_stage_message(step, status)
            if len(status_text) > 20:
                status_text = status_text[:18] + "..."
            mini_panel.update_status(status_text)

            # 전체 진행률 계산
            # Calculate overall progress
            total_progress = self._model.calculate_overall_progress()
            mini_panel.update_progress(int(total_progress))

        except Exception as e:
            logger.debug(f"[Mini progress] Update error: {e}")

    def update_all_progress_displays(self) -> None:
        """
        모든 탭의 진행상황 표시 업데이트
        Update progress displays in all tabs
        """
        self.update_script_progress()
        self.update_translation_progress()
        self.update_tts_progress()
        self.update_overall_progress_display()

    def refresh_stage_indicator(
        self,
        step: str,
        status: str,
        progress: Optional[float] = None
    ) -> None:
        """
        진행현황 카드 단계 라벨/게이지 업데이트 - 시각적으로 강조
        Update progress card step label/gauge - visually emphasized

        Args:
            step: 단계 이름 (step name)
            status: 상태 문자열 (status string)
            progress: 진행률 (progress percentage)
        """
        indicator = getattr(self.gui, "step_indicators", {}).get(step)
        if not indicator:
            return

        status_color = self.get_status_color(status)

        # 상태별 아이콘 - 더 눈에 띄는 이모지
        # Status icons - more visible emojis
        status_icons = {
            'waiting': '⏸',
            'processing': '🔄',
            'completed': '✅',
            'error': '❌'
        }
        icon = status_icons.get(status, '⏸')

        # 테마 매니저에서 배경색 가져오기
        # Get background color from theme manager
        theme_manager = getattr(self.gui, '_theme_manager', None)
        is_dark = theme_manager.is_dark_mode if theme_manager else True
        bg_card = "#1E1E1E" if is_dark else "#FFFFFF"
        bg_secondary = "#2D2D2D" if is_dark else "#F3F4F6"
        processing_bg = "#3B1A1A" if is_dark else "#FEE2E2"  # 진행 중 배경

        def _apply():
            # 상태 아이콘 업데이트
            # Update status icon
            indicator['status_label'].config(text=icon, fg=status_color)

            # 제목 레이블 - 진행 중일 때 강조
            # Title label - emphasized when processing
            title_label = indicator.get('title_label')
            if title_label:
                if status == 'processing':
                    title_label.config(fg=status_color, font=("맑은 고딕", 9, "bold"))
                else:
                    title_label.config(fg=self.gui.primary_text, font=("맑은 고딕", 9))

            # 진행률 텍스트
            # Progress text
            progress_label = indicator.get('progress_label')
            if progress_label:
                if progress is not None:
                    value = max(0, min(100, int(progress)))
                    progress_label.config(text=f"{value}%", fg=status_color)
                elif status == 'completed':
                    progress_label.config(text="완료", fg=status_color)
                elif status == 'processing':
                    progress_label.config(text="진행중", fg=status_color)
                else:
                    progress_label.config(text="", fg=self.gui.secondary_text)

            # 행 배경색 - 진행 중일 때 강조
            # Row background - emphasized when processing
            row_frame = indicator.get('row_frame')
            if row_frame:
                idx = indicator.get('index', 0)
                if status == 'processing':
                    row_bg = processing_bg
                else:
                    row_bg = bg_secondary if idx % 2 == 0 else bg_card

                row_frame.config(bg=row_bg)
                # 자식 위젯들도 배경색 업데이트
                # Update child widgets background too
                for child in row_frame.winfo_children():
                    try:
                        child.config(bg=row_bg)
                    except Exception:
                        pass

        self._run_on_ui_thread(_apply)

    # -------------------------------------------------------------------------
    # 상태 표시 관련 유틸리티
    # Status Display Utilities
    # -------------------------------------------------------------------------

    def get_status_color(self, status: str) -> str:
        """
        상태에 따른 색상 반환 - 더 선명한 색상
        Return color based on status - more vivid colors

        Args:
            status: 상태 문자열 (status string)

        Returns:
            색상 코드 (color code)
        """
        theme_manager = getattr(self.gui, '_theme_manager', None)
        is_dark = theme_manager.is_dark_mode if theme_manager else True

        if is_dark:
            colors = {
                'waiting': '#6B7280',    # 회색
                'processing': '#F87171', # 밝은 빨강 (눈에 확 띔)
                'completed': '#34D399',  # 밝은 초록
                'error': '#F87171'       # 밝은 빨강
            }
        else:
            colors = {
                'waiting': '#9CA3AF',    # 연한 회색
                'processing': '#DC2626', # 진한 빨강
                'completed': '#059669',  # 진한 초록
                'error': '#DC2626'       # 진한 빨강
            }
        return colors.get(status, colors['waiting'])

    def get_status_text(self, status: str) -> str:
        """
        상태에 따른 텍스트 반환
        Return text based on status

        Args:
            status: 상태 문자열 (status string)

        Returns:
            상태 텍스트 (status text)
        """
        texts = {
            'waiting': "대기 중...",
            'processing': "진행 중...",
            'completed': "완료",
            'error': "오류 발생"
        }
        return texts.get(status, "알 수 없음")

    def get_stage_message(self, step: str, status: str) -> str:
        """
        단계별 UX 메시지 생성
        Generate UX message for each step

        Args:
            step: 단계 이름 (step name)
            status: 상태 문자열 (status string)

        Returns:
            표시할 메시지 (message to display)
        """
        titles = getattr(self.gui, "step_titles", {})
        default_title = titles.get(step, step.capitalize())

        # 모델에서 커스텀 메시지 확인
        # Check custom message from model
        state = self._model.get_state(step)
        custom_message = state.get('message')
        if custom_message:
            return custom_message

        if status == 'processing':
            messages = getattr(self.gui, 'stage_messages', {}).get(step)
            if messages:
                previous = self._model.get_cached_stage_message(step)
                candidates = [m for m in messages if m != previous] or messages
                chosen = random.choice(candidates)
                self._model.cache_stage_message(step, chosen)
                return chosen
            return f"{default_title} 진행 중이에요."

        if status == 'completed':
            return f"{default_title} 완료!"
        if status == 'error':
            return f"{default_title} 중 오류가 발생했어요."
        return f"{default_title} 대기 중"

    def get_voice_label(self, voice_id: str) -> str:
        """
        음성 ID를 한글 이름으로 변환
        Convert voice ID to Korean name

        Args:
            voice_id: 음성 ID (voice ID)

        Returns:
            음성 라벨 (voice label)
        """
        if not voice_id:
            return "알 수 없음"

        profile = self.gui.get_voice_profile(voice_id)
        if profile:
            return profile.get('label', voice_id)
        return voice_id

    # -------------------------------------------------------------------------
    # 메시지 빌더 메서드
    # Message Builder Methods
    # -------------------------------------------------------------------------

    def _format_job_source(self, source: str) -> str:
        """
        사용자에게 보여줄 작업 식별 텍스트를 생성
        Generate job identification text for display

        Args:
            source: 작업 소스 (job source)

        Returns:
            포맷된 소스 문자열 (formatted source string)
        """
        if not source:
            return "알 수 없는 작업"

        try:
            parsed = urlparse(source)
            netloc = parsed.netloc or ""
            if parsed.scheme in ("http", "https") or netloc:
                segments = [segment for segment in parsed.path.split('/') if segment]
                display_host = netloc or (segments[0] if segments else "")
                tail = segments[-1] if segments else parsed.query
                tail = (tail or "").strip()
                if tail and len(tail) > 28:
                    tail = tail[:25] + "..."
                if display_host and tail:
                    return f"{display_host} / {tail}"
                return display_host or tail or source[:28]
        except Exception as e:
            logger.debug(f"[ProgressManager] URL 파싱 실패: {e}")

        filename = os.path.basename(source.rstrip('/\\')) or source
        if len(filename) > 28:
            filename = filename[:25] + "..."
        return filename

    def _get_selected_audio_name(self) -> Optional[str]:
        """
        현재 선택된 오디오(음성) 이름을 표시용으로 반환
        Return currently selected audio (voice) name for display

        Returns:
            음성 이름 또는 None (voice name or None)
        """
        # 1) 모델에서 현재 처리 중인 음성 라벨 우선
        # 1) Priority: current voice label from model
        voice_info = self._model.get_voice_info()
        if voice_info.get('label'):
            return voice_info['label']

        # 2) 최근 사용한 음성 ID
        # 2) Recently used voice ID
        recent_voice = getattr(self.gui, 'last_voice_used', None)
        if recent_voice:
            return self.get_voice_label(recent_voice)

        # 3) 단일/기본 음성 선택값
        # 3) Single/default voice selection
        for attr in ('selected_single_voice', 'selected_tts_voice'):
            var = getattr(self.gui, attr, None)
            if hasattr(var, 'get'):
                try:
                    voice_id = var.get()
                except Exception as e:
                    logger.debug(f"[ProgressManager] 음성 변수 가져오기 실패: {e}")
                    voice_id = None
                if voice_id:
                    return self.get_voice_label(voice_id)

        # 4) 다중 음성 프리셋 또는 사용 가능 음성 목록
        # 4) Multi-voice presets or available voice list
        voices = getattr(self.gui, 'multi_voice_presets', None) or getattr(self.gui, 'available_tts_voices', [])
        if voices:
            return self.get_voice_label(voices[0])

        return None

    def _build_current_task_message(self, stage_message: str, status: str) -> str:
        """
        보라색 진행 텍스트에 표시할 메시지 생성
        Generate message for purple progress text

        Args:
            stage_message: 단계 메시지 (stage message)
            status: 상태 문자열 (status string)

        Returns:
            표시할 메시지 (message to display)
        """
        if status == 'processing':
            audio_name = self._get_selected_audio_name()
            if audio_name:
                return f"{audio_name}의 영상을 제작 하고 있습니다"
        return stage_message

    def _get_current_step_text(self, step: Optional[str]) -> str:
        """
        현재 작업 단계에 대한 텍스트 반환
        Return text for current work step

        Args:
            step: 단계 이름 (step name)

        Returns:
            단계 텍스트 (step text)
        """
        step_names = {
            'download': '📥 다운로드 중...',
            'analysis': '🤖 AI 영상 분석 중...',
            'ocr_analysis': '🔍 중국어 자막 분석 중...',
            'translation': '🌐 번역 중...',
            'tts': '🎤 TTS 음성 생성 중...',
            'subtitle': '🎨 블러 처리 중...',
            'audio_analysis': '🔊 음성 싱크 분석 중...',
            'subtitle_overlay': '📝 자막 적용 중...',
            'video': '🎵 영상 합성 중...',
            'finalize': '✨ 마무리 중...'
        }

        if step and step in step_names:
            return step_names[step]
        return "대기 중..."

    # -------------------------------------------------------------------------
    # 탭별 진행상황 업데이트
    # Tab-specific Progress Updates
    # -------------------------------------------------------------------------

    def update_script_progress(self) -> None:
        """
        대본 탭 진행상황 업데이트
        Update script tab progress
        """
        script_progress = getattr(self.gui, 'script_progress', None)
        if script_progress is None:
            return

        state = self._model.get_state('analysis')
        status = state.get('status', 'waiting')
        progress = state.get('progress', 0)

        progress_bar = script_progress.get('progress_bar')
        if progress_bar is not None:
            progress_bar['value'] = progress

        status_label = script_progress.get('status_label')
        if status_label is not None:
            status_label.config(
                text=f"{self.get_status_text(status)} ({progress}%)",
                fg=self.get_status_color(status)
            )

    def update_translation_progress(self) -> None:
        """
        번역 탭 진행상황 업데이트
        Update translation tab progress
        """
        translation_progress = getattr(self.gui, 'translation_progress', None)
        if translation_progress is None:
            return

        state = self._model.get_state('translation')
        status = state.get('status', 'waiting')
        progress = state.get('progress', 0)

        progress_bar = translation_progress.get('progress_bar')
        if progress_bar is not None:
            progress_bar['value'] = progress

        status_label = translation_progress.get('status_label')
        if status_label is not None:
            status_label.config(
                text=f"{self.get_status_text(status)} ({progress}%)",
                fg=self.get_status_color(status)
            )

    def update_tts_progress(self) -> None:
        """
        TTS 탭 진행상황 업데이트
        Update TTS tab progress
        """
        tts_progress = getattr(self.gui, 'tts_progress', None)
        if tts_progress is None:
            return

        state = self._model.get_state('tts')
        status = state.get('status', 'waiting')
        progress = state.get('progress', 0)

        progress_bar = tts_progress.get('progress_bar')
        if progress_bar is not None:
            progress_bar['value'] = progress

        status_label = tts_progress.get('status_label')
        if status_label is not None:
            status_label.config(
                text=f"{self.get_status_text(status)} ({progress}%)",
                fg=self.get_status_color(status)
            )

    def update_overall_progress_display(self) -> None:
        """
        현재 영상 진행률 표시 업데이트 (단계별 가중치 기반)
        Update current video progress display (weight-based)
        """
        overall_numeric_label = getattr(self.gui, 'overall_numeric_label', None)
        if overall_numeric_label is None:
            return

        # 모델에서 전체 진행률 계산
        # Calculate overall progress from model
        total_progress = self._model.calculate_overall_progress()
        progress = max(0, min(100, int(total_progress)))

        # 현재 진행 중인 단계 찾기
        # Find currently processing step
        current_step = self._model.get_current_processing_step()

        # 진행률 숫자 표시
        # Display progress percentage
        numeric_text = f"{progress}%"
        if overall_numeric_label is not None:
            overall_numeric_label.config(text=numeric_text)

        # 회색 라벨: 현재 작업 단계 표시
        # Gray label: display current work step
        overall_witty_label = getattr(self.gui, 'overall_witty_label', None)
        if overall_witty_label is not None:
            step_text = self._get_current_step_text(current_step)
            overall_witty_label.config(text=step_text)

    # -------------------------------------------------------------------------
    # 레거시 호환 메서드 (위트 메시지)
    # Legacy Compatibility Methods (Witty Messages)
    # -------------------------------------------------------------------------

    def _build_current_video_message(self, progress: float) -> str:
        """
        현재 영상 진행률에 대한 상태 메시지
        Status message for current video progress

        Args:
            progress: 진행률 (progress percentage)

        Returns:
            상태 메시지 (status message)
        """
        if progress <= 0:
            return "영상 처리 준비 중..."
        if progress < 20:
            return "다운로드 및 분석 준비 중"
        if progress < 40:
            return "AI 분석 및 번역 진행 중"
        if progress < 60:
            return "TTS 음성 생성 중"
        if progress < 80:
            return "자막 싱크 및 블러 처리 중"
        if progress < 100:
            return "영상 합성 마무리 중"
        return "현재 영상 완료!"

    def _build_overall_witty_message(
        self,
        progress: float,
        completed: int,
        total: int
    ) -> str:
        """
        전체 진행률에 대한 위트 메시지 (레거시 호환)
        Witty message for overall progress (legacy compatibility)

        Args:
            progress: 진행률 (progress percentage)
            completed: 완료된 작업 수 (completed job count)
            total: 전체 작업 수 (total job count)

        Returns:
            위트 메시지 (witty message)
        """
        if total <= 0:
            return "큐를 채우면 신나는 제작 퍼레이드가 시작됩니다!"
        if progress <= 0:
            return "첫 스타트만 끊으면 자막 싱크 맞추는 여정이 곧 시작돼요."
        if progress < 40:
            return "초반 워밍업 중! 싱크 계산에 필요한 재료들을 정리하고 있어요."
        if progress < 80:
            return "절반을 훌쩍 넘겼어요. 오디오 분석으로 자막 싱크를 쫙 맞추는 중!"
        if progress < 100:
            return "거의 다 왔습니다. 계산한 타이밍으로 자막을 얹고 마지막 광택을 내는 중이에요."
        return "모든 단계 완료! 싱크가 착 붙은 영상을 확인해 보세요."

    def _calculate_overall_progress(self) -> float:
        """
        전체 진행률 계산 (레거시 호환 - 모델 위임)
        Calculate overall progress (legacy compatibility - delegates to model)

        Returns:
            전체 진행률 0-100 (overall progress 0-100)
        """
        # 사이드바 미니 패널용 가중치
        # Weights for sidebar mini panel
        weights = {
            'download': 10,
            'analysis': 15,
            'ocr_analysis': 10,
            'translation': 15,
            'tts': 20,
            'subtitle': 10,
            'video': 20,
        }
        return self._model.calculate_overall_progress(weights)
