"""
애니메이션 헬퍼 모듈
Tkinter 기반 UI 애니메이션 유틸리티
"""
import tkinter as tk
from typing import Callable, Optional
import math


def ease_out_quad(t: float) -> float:
    """
    Ease-out quadratic 이징 함수
    빠르게 시작하고 천천히 감속

    Args:
        t: 0.0 ~ 1.0 사이의 진행률

    Returns:
        이징이 적용된 값
    """
    return 1 - (1 - t) * (1 - t)


def ease_in_out_quad(t: float) -> float:
    """
    Ease-in-out quadratic 이징 함수
    천천히 시작, 빠르게 진행, 천천히 감속

    Args:
        t: 0.0 ~ 1.0 사이의 진행률

    Returns:
        이징이 적용된 값
    """
    if t < 0.5:
        return 2 * t * t
    else:
        return 1 - pow(-2 * t + 2, 2) / 2


def ease_out_cubic(t: float) -> float:
    """
    Ease-out cubic 이징 함수
    더 부드러운 감속

    Args:
        t: 0.0 ~ 1.0 사이의 진행률

    Returns:
        이징이 적용된 값
    """
    return 1 - pow(1 - t, 3)


def ease_out_elastic(t: float) -> float:
    """
    Elastic 이징 함수 (튀는 효과)

    Args:
        t: 0.0 ~ 1.0 사이의 진행률

    Returns:
        이징이 적용된 값
    """
    if t == 0:
        return 0
    if t == 1:
        return 1

    c4 = (2 * math.pi) / 3
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


class TkAnimation:
    """Tkinter 기반 애니메이션 헬퍼 클래스"""

    @staticmethod
    def animate_value(
        widget: tk.Widget,
        start_value: float,
        end_value: float,
        duration_ms: int,
        update_callback: Callable[[float], None],
        easing: Callable[[float], float] = ease_out_quad,
        complete_callback: Optional[Callable[[], None]] = None
    ) -> str:
        """
        값 애니메이션
        start_value에서 end_value까지 부드럽게 변경

        Args:
            widget: 애니메이션을 실행할 Tkinter 위젯 (after 메소드 사용)
            start_value: 시작 값
            end_value: 끝 값
            duration_ms: 애니메이션 지속 시간 (밀리초)
            update_callback: 값이 업데이트될 때 호출될 콜백 (인자: 현재 값)
            easing: 이징 함수
            complete_callback: 애니메이션 완료 시 호출될 콜백

        Returns:
            취소용 after_id
        """
        frame_duration = 16  # 약 60fps
        total_frames = max(1, duration_ms // frame_duration)
        current_frame = [0]  # 리스트로 감싸서 클로저에서 수정 가능하게
        after_id = [None]

        def animate():
            if current_frame[0] >= total_frames:
                update_callback(end_value)
                if complete_callback:
                    complete_callback()
                return

            progress = current_frame[0] / total_frames
            eased_progress = easing(progress)
            current_value = start_value + (end_value - start_value) * eased_progress

            update_callback(current_value)

            current_frame[0] += 1
            after_id[0] = widget.after(frame_duration, animate)

        animate()
        return after_id[0]

    @staticmethod
    def slide_horizontal(
        widget: tk.Widget,
        start_x: int,
        end_x: int,
        duration_ms: int = 300,
        easing: Callable[[float], float] = ease_out_quad,
        callback: Optional[Callable[[], None]] = None
    ) -> None:
        """
        수평 슬라이드 애니메이션

        Args:
            widget: 애니메이션할 위젯
            start_x: 시작 X 좌표
            end_x: 끝 X 좌표
            duration_ms: 지속 시간 (밀리초)
            easing: 이징 함수
            callback: 완료 콜백
        """
        def update_position(x: float):
            widget.place(x=int(x))

        TkAnimation.animate_value(
            widget,
            start_x,
            end_x,
            duration_ms,
            update_position,
            easing,
            callback
        )

    @staticmethod
    def slide_vertical(
        widget: tk.Widget,
        start_y: int,
        end_y: int,
        duration_ms: int = 300,
        easing: Callable[[float], float] = ease_out_quad,
        callback: Optional[Callable[[], None]] = None
    ) -> None:
        """
        수직 슬라이드 애니메이션

        Args:
            widget: 애니메이션할 위젯
            start_y: 시작 Y 좌표
            end_y: 끝 Y 좌표
            duration_ms: 지속 시간 (밀리초)
            easing: 이징 함수
            callback: 완료 콜백
        """
        def update_position(y: float):
            widget.place(y=int(y))

        TkAnimation.animate_value(
            widget,
            start_y,
            end_y,
            duration_ms,
            update_position,
            easing,
            callback
        )

    @staticmethod
    def fade_background(
        widget: tk.Widget,
        start_color: str,
        end_color: str,
        duration_ms: int = 200,
        easing: Callable[[float], float] = ease_out_quad,
        callback: Optional[Callable[[], None]] = None
    ) -> None:
        """
        배경색 페이드 애니메이션

        Args:
            widget: 애니메이션할 위젯
            start_color: 시작 색상 (hex)
            end_color: 끝 색상 (hex)
            duration_ms: 지속 시간 (밀리초)
            easing: 이징 함수
            callback: 완료 콜백
        """
        def hex_to_rgb(hex_color: str) -> tuple:
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        def rgb_to_hex(rgb: tuple) -> str:
            return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

        start_rgb = hex_to_rgb(start_color)
        end_rgb = hex_to_rgb(end_color)

        def update_color(progress: float):
            current_rgb = tuple(
                start_rgb[i] + (end_rgb[i] - start_rgb[i]) * progress
                for i in range(3)
            )
            try:
                widget.configure(bg=rgb_to_hex(current_rgb))
            except tk.TclError:
                pass  # 위젯이 파괴된 경우

        TkAnimation.animate_value(
            widget,
            0.0,
            1.0,
            duration_ms,
            update_color,
            easing,
            callback
        )


class TabTransition:
    """탭 전환 애니메이션 관리 클래스"""

    def __init__(self, container: tk.Widget, duration_ms: int = 250):
        """
        Args:
            container: 탭 컨텐츠를 담는 컨테이너
            duration_ms: 전환 애니메이션 지속 시간
        """
        self.container = container
        self.duration = duration_ms
        self._animating = False

    @property
    def is_animating(self) -> bool:
        """애니메이션 진행 중 여부"""
        return self._animating

    def switch_tab(
        self,
        old_frame: Optional[tk.Frame],
        new_frame: tk.Frame,
        direction: str = "left"
    ) -> None:
        """
        탭 전환 애니메이션 실행

        Args:
            old_frame: 이전 탭 프레임 (None이면 새 프레임만 표시)
            new_frame: 새 탭 프레임
            direction: 전환 방향 ("left" 또는 "right")
        """
        if self._animating:
            return

        self._animating = True
        self.container.update_idletasks()
        width = self.container.winfo_width()

        if width <= 1:
            # 컨테이너 크기가 아직 정해지지 않은 경우
            if old_frame:
                old_frame.place_forget()
            new_frame.place(x=0, y=0, relwidth=1, relheight=1)
            self._animating = False
            return

        # 새 프레임 시작 위치 결정
        start_x = width if direction == "left" else -width

        def on_complete():
            self._animating = False

        # 이전 프레임 슬라이드 아웃
        if old_frame:
            end_x = -width if direction == "left" else width
            TkAnimation.slide_horizontal(
                old_frame,
                0,
                end_x,
                self.duration,
                ease_out_quad,
                lambda: old_frame.place_forget()
            )

        # 새 프레임 슬라이드 인
        new_frame.place(x=start_x, y=0, relwidth=1, relheight=1)
        new_frame.lift()
        TkAnimation.slide_horizontal(
            new_frame,
            start_x,
            0,
            self.duration,
            ease_out_quad,
            on_complete
        )

    def instant_switch(self, old_frame: Optional[tk.Frame], new_frame: tk.Frame) -> None:
        """
        애니메이션 없이 즉시 탭 전환

        Args:
            old_frame: 이전 탭 프레임
            new_frame: 새 탭 프레임
        """
        if old_frame:
            old_frame.place_forget()
        new_frame.place(x=0, y=0, relwidth=1, relheight=1)


class ProgressAnimation:
    """진행률 바 애니메이션 클래스"""

    def __init__(self, widget: tk.Widget, set_value_callback: Callable[[float], None]):
        """
        Args:
            widget: 애니메이션용 위젯 (after 메소드 사용)
            set_value_callback: 값 설정 콜백
        """
        self.widget = widget
        self.set_value = set_value_callback
        self._current_value = 0.0
        self._animating = False
        self._after_id: Optional[str] = None

    @property
    def current_value(self) -> float:
        """현재 진행률 값"""
        return self._current_value

    def animate_to(
        self,
        target_value: float,
        duration_ms: int = 500,
        easing: Callable[[float], float] = ease_out_quad
    ) -> None:
        """
        부드러운 진행률 변경

        Args:
            target_value: 목표 값 (0.0 ~ 100.0)
            duration_ms: 애니메이션 지속 시간
            easing: 이징 함수
        """
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass

        start_value = self._current_value
        frame_duration = 16
        total_frames = max(1, duration_ms // frame_duration)
        current_frame = [0]

        def animate():
            if current_frame[0] >= total_frames:
                self._current_value = target_value
                self.set_value(target_value)
                self._animating = False
                return

            progress = current_frame[0] / total_frames
            eased_progress = easing(progress)
            self._current_value = start_value + (target_value - start_value) * eased_progress
            self.set_value(self._current_value)

            current_frame[0] += 1
            self._after_id = self.widget.after(frame_duration, animate)

        self._animating = True
        animate()

    def set_instant(self, value: float) -> None:
        """
        애니메이션 없이 즉시 값 설정

        Args:
            value: 설정할 값
        """
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass

        self._current_value = value
        self.set_value(value)
        self._animating = False

    def reset(self) -> None:
        """진행률 초기화"""
        self.set_instant(0.0)


class PulseAnimation:
    """펄스(강조) 애니메이션 클래스"""

    def __init__(
        self,
        widget: tk.Widget,
        normal_color: str,
        pulse_color: str,
        duration_ms: int = 1000
    ):
        """
        Args:
            widget: 애니메이션할 위젯
            normal_color: 기본 색상
            pulse_color: 펄스 색상
            duration_ms: 펄스 주기 (밀리초)
        """
        self.widget = widget
        self.normal_color = normal_color
        self.pulse_color = pulse_color
        self.duration = duration_ms
        self._running = False
        self._after_id: Optional[str] = None

    def start(self) -> None:
        """펄스 애니메이션 시작"""
        if self._running:
            return

        self._running = True
        self._pulse_in()

    def stop(self) -> None:
        """펄스 애니메이션 중지"""
        self._running = False
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
        try:
            self.widget.configure(bg=self.normal_color)
        except tk.TclError:
            pass

    def _pulse_in(self) -> None:
        if not self._running:
            return

        TkAnimation.fade_background(
            self.widget,
            self.normal_color,
            self.pulse_color,
            self.duration // 2,
            ease_in_out_quad,
            self._pulse_out
        )

    def _pulse_out(self) -> None:
        if not self._running:
            return

        TkAnimation.fade_background(
            self.widget,
            self.pulse_color,
            self.normal_color,
            self.duration // 2,
            ease_in_out_quad,
            lambda: self.widget.after(100, self._pulse_in) if self._running else None
        )
