"""
애니메이션 진행바 모듈
부드러운 애니메이션이 적용된 진행률 표시 컴포넌트
"""
import tkinter as tk
from typing import Optional, List, Dict, Callable
from .base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager
from ..animation import ProgressAnimation, ease_out_quad, PulseAnimation


class AnimatedProgressBar(tk.Canvas, ThemedMixin):
    """
    애니메이션 진행바
    부드러운 값 전환이 적용된 커스텀 진행바
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        width: int = 200,
        height: int = 8,
        show_text: bool = False,
        corner_radius: int = 4
    ):
        """
        Args:
            parent: 부모 위젯
            theme_manager: 테마 관리자
            width: 너비
            height: 높이
            show_text: 퍼센트 텍스트 표시 여부
            corner_radius: 모서리 둥글기
        """
        self._prog_width = width
        self._prog_height = height
        self._show_text = show_text
        self._corner_radius = corner_radius
        self._value = 0.0

        self.__init_themed__(theme_manager)

        canvas_height = height if not show_text else height + 20
        tk.Canvas.__init__(
            self, parent,
            width=width,
            height=canvas_height,
            highlightthickness=0,
            bg=self.get_color("bg_card")
        )

        # 애니메이션 관리
        self._animation = ProgressAnimation(self, self._set_value_internal)

        self._draw()

    def _set_value_internal(self, value: float) -> None:
        """내부 값 설정 (애니메이션용)"""
        self._value = value
        self._draw()

    def _draw(self) -> None:
        """진행바 그리기"""
        self.delete("all")

        y_offset = 16 if self._show_text else 0

        # 배경 트랙
        self._draw_rounded_rect(
            0, y_offset,
            self._prog_width, y_offset + self._prog_height,
            self._corner_radius,
            self.get_color("progress_bg")
        )

        # 진행 바
        if self._value > 0:
            fill_width = max(self._corner_radius * 2, (self._prog_width * self._value / 100))
            self._draw_rounded_rect(
                0, y_offset,
                fill_width, y_offset + self._prog_height,
                self._corner_radius,
                self.get_color("progress_fill")
            )

        # 퍼센트 텍스트
        if self._show_text:
            self.create_text(
                self._prog_width / 2, 8,
                text=f"{int(self._value)}%",
                font=("맑은 고딕", 10, "bold"),
                fill=self.get_color("text_primary"),
                anchor="center"
            )

    def _draw_rounded_rect(
        self,
        x1: float, y1: float,
        x2: float, y2: float,
        radius: int,
        color: str
    ) -> None:
        """둥근 사각형 그리기"""
        if radius <= 0:
            self.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
            return

        height = y2 - y1
        actual_radius = min(radius, height / 2)

        # 좌측 반원
        self.create_arc(
            x1, y1, x1 + actual_radius * 2, y2,
            start=90, extent=180,
            fill=color, outline=""
        )
        # 우측 반원
        self.create_arc(
            x2 - actual_radius * 2, y1, x2, y2,
            start=270, extent=180,
            fill=color, outline=""
        )
        # 중앙 사각형
        self.create_rectangle(
            x1 + actual_radius, y1, x2 - actual_radius, y2,
            fill=color, outline=""
        )

    def set_value(self, value: float, animate: bool = True) -> None:
        """
        진행률 값 설정

        Args:
            value: 진행률 (0-100)
            animate: 애니메이션 적용 여부
        """
        value = max(0, min(100, value))
        if animate:
            self._animation.animate_to(value, duration_ms=300)
        else:
            self._animation.set_instant(value)

    def get_value(self) -> float:
        """현재 진행률 반환"""
        return self._value

    def reset(self) -> None:
        """진행률 초기화"""
        self._animation.reset()

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_card"))
        self._draw()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class StepProgressIndicator(tk.Frame, ThemedMixin):
    """
    단계별 진행 인디케이터
    여러 단계의 진행 상황을 시각화
    """

    def __init__(
        self,
        parent: tk.Widget,
        steps: List[Dict[str, str]],
        theme_manager: Optional[ThemeManager] = None,
        orientation: str = "vertical"  # "vertical" or "horizontal"
    ):
        """
        Args:
            parent: 부모 위젯
            steps: 단계 목록 [{"id": "step1", "label": "단계 1", "icon": "📥"}, ...]
            theme_manager: 테마 관리자
            orientation: 방향
        """
        self._steps = steps
        self._orientation = orientation
        self._step_states: Dict[str, str] = {}  # "waiting", "progress", "completed"
        self._step_progress: Dict[str, float] = {}
        self._step_widgets: Dict[str, Dict] = {}

        for step in steps:
            self._step_states[step["id"]] = "waiting"
            self._step_progress[step["id"]] = 0.0

        self.__init_themed__(theme_manager)

        tk.Frame.__init__(self, parent, bg=self.get_color("bg_card"))

        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        for i, step in enumerate(self._steps):
            step_frame = self._create_step_widget(step, i)

            if self._orientation == "vertical":
                step_frame.pack(fill=tk.X, pady=2)
            else:
                step_frame.pack(side=tk.LEFT, padx=4)

    def _create_step_widget(self, step: Dict, index: int) -> tk.Frame:
        """단계 위젯 생성"""
        step_id = step["id"]
        label = step.get("label", f"Step {index + 1}")
        icon = step.get("icon", "")

        # 컨테이너
        container = tk.Frame(self, bg=self.get_color("bg_card"))

        if self._orientation == "vertical":
            # 수직 레이아웃: 아이콘 | 레이블 | 상태 | 진행바
            row_frame = tk.Frame(container, bg=self.get_color("bg_card"))
            row_frame.pack(fill=tk.X)

            # 아이콘 + 레이블
            left = tk.Frame(row_frame, bg=self.get_color("bg_card"))
            left.pack(side=tk.LEFT, fill=tk.X, expand=True)

            icon_label = tk.Label(
                left,
                text=icon,
                font=("맑은 고딕", 12),
                bg=self.get_color("bg_card"),
                fg=self.get_color("text_primary"),
                width=3
            )
            icon_label.pack(side=tk.LEFT)

            text_label = tk.Label(
                left,
                text=label,
                font=("맑은 고딕", 10),
                bg=self.get_color("bg_card"),
                fg=self.get_color("text_secondary"),
                anchor="w"
            )
            text_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # 상태 아이콘
            status_label = tk.Label(
                row_frame,
                text="⏸",  # 대기
                font=("맑은 고딕", 10),
                bg=self.get_color("bg_card"),
                fg=self.get_color("text_disabled"),
                width=3
            )
            status_label.pack(side=tk.RIGHT)

            # 진행바 (작은 버전)
            progress_bar = AnimatedProgressBar(
                container,
                theme_manager=self._theme_manager,
                width=200,
                height=4,
                show_text=False
            )
            progress_bar.pack(fill=tk.X, pady=(2, 0))

        else:
            # 수평 레이아웃: 아이콘 위, 진행 원 아래
            icon_label = tk.Label(
                container,
                text=icon,
                font=("맑은 고딕", 16),
                bg=self.get_color("bg_card"),
                fg=self.get_color("text_secondary")
            )
            icon_label.pack()

            text_label = tk.Label(
                container,
                text=label,
                font=("맑은 고딕", 8),
                bg=self.get_color("bg_card"),
                fg=self.get_color("text_secondary")
            )
            text_label.pack()

            status_label = None
            progress_bar = None

        self._step_widgets[step_id] = {
            "container": container,
            "icon": icon_label,
            "label": text_label,
            "status": status_label,
            "progress": progress_bar
        }

        return container

    def set_step_state(self, step_id: str, state: str) -> None:
        """
        단계 상태 설정

        Args:
            step_id: 단계 ID
            state: "waiting", "progress", "completed"
        """
        if step_id not in self._step_states:
            return

        self._step_states[step_id] = state
        self._update_step_visual(step_id)

    def set_step_progress(self, step_id: str, progress: float) -> None:
        """
        단계 진행률 설정

        Args:
            step_id: 단계 ID
            progress: 진행률 (0-100)
        """
        if step_id not in self._step_progress:
            return

        self._step_progress[step_id] = progress
        widgets = self._step_widgets.get(step_id)
        if widgets and widgets.get("progress"):
            widgets["progress"].set_value(progress)

    def _update_step_visual(self, step_id: str) -> None:
        """단계 시각 업데이트"""
        state = self._step_states[step_id]
        widgets = self._step_widgets.get(step_id)
        if not widgets:
            return

        # 상태별 아이콘과 색상
        if state == "waiting":
            status_text = "⏸"
            icon_color = self.get_color("text_disabled")
            label_color = self.get_color("text_secondary")
        elif state == "progress":
            status_text = "⏯"
            icon_color = self.get_color("primary")
            label_color = self.get_color("text_primary")
        else:  # completed
            status_text = "✓"
            icon_color = self.get_color("success")
            label_color = self.get_color("text_primary")

        # 위젯 업데이트
        if widgets.get("status"):
            widgets["status"].configure(text=status_text, fg=icon_color)
        if widgets.get("icon"):
            widgets["icon"].configure(fg=icon_color)
        if widgets.get("label"):
            widgets["label"].configure(fg=label_color)

    def reset_all(self) -> None:
        """모든 단계 초기화"""
        for step_id in self._step_states:
            self._step_states[step_id] = "waiting"
            self._step_progress[step_id] = 0.0
            self._update_step_visual(step_id)
            widgets = self._step_widgets.get(step_id)
            if widgets and widgets.get("progress"):
                widgets["progress"].reset()

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_card"))

        for step_id, widgets in self._step_widgets.items():
            if widgets.get("container"):
                widgets["container"].configure(bg=self.get_color("bg_card"))
            if widgets.get("icon"):
                widgets["icon"].configure(bg=self.get_color("bg_card"))
            if widgets.get("label"):
                widgets["label"].configure(bg=self.get_color("bg_card"))
            if widgets.get("status"):
                widgets["status"].configure(bg=self.get_color("bg_card"))
            if widgets.get("progress"):
                widgets["progress"].apply_theme()

            self._update_step_visual(step_id)

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class CircularProgress(tk.Canvas, ThemedMixin):
    """
    원형 진행 인디케이터
    로딩/진행 상태를 원형으로 표시
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        size: int = 40,
        thickness: int = 4,
        show_text: bool = True
    ):
        self._size = size
        self._thickness = thickness
        self._show_text = show_text
        self._value = 0.0

        self.__init_themed__(theme_manager)

        tk.Canvas.__init__(
            self, parent,
            width=size, height=size,
            highlightthickness=0,
            bg=self.get_color("bg_card")
        )

        self._animation = ProgressAnimation(self, self._set_value_internal)
        self._draw()

    def _set_value_internal(self, value: float) -> None:
        self._value = value
        self._draw()

    def _draw(self) -> None:
        """원형 진행바 그리기"""
        self.delete("all")

        padding = self._thickness
        diameter = self._size - padding * 2

        # 배경 원
        self.create_oval(
            padding, padding,
            padding + diameter, padding + diameter,
            outline=self.get_color("progress_bg"),
            width=self._thickness
        )

        # 진행 아크
        if self._value > 0:
            extent = -3.6 * self._value  # 360도 * (value/100)
            self.create_arc(
                padding, padding,
                padding + diameter, padding + diameter,
                start=90, extent=extent,
                outline=self.get_color("progress_fill"),
                width=self._thickness,
                style="arc"
            )

        # 중앙 텍스트
        if self._show_text:
            self.create_text(
                self._size / 2, self._size / 2,
                text=f"{int(self._value)}%",
                font=("맑은 고딕", int(self._size * 0.2), "bold"),
                fill=self.get_color("text_primary"),
                anchor="center"
            )

    def set_value(self, value: float, animate: bool = True) -> None:
        value = max(0, min(100, value))
        if animate:
            self._animation.animate_to(value)
        else:
            self._animation.set_instant(value)

    def reset(self) -> None:
        self._animation.reset()

    def apply_theme(self) -> None:
        self.configure(bg=self.get_color("bg_card"))
        self._draw()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class IndeterminateSpinner(tk.Canvas, ThemedMixin):
    """
    불확정 로딩 스피너
    진행률을 알 수 없을 때 사용하는 회전 애니메이션
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        size: int = 24,
        thickness: int = 3
    ):
        self._size = size
        self._thickness = thickness
        self._angle = 0
        self._running = False
        self._after_id = None

        self.__init_themed__(theme_manager)

        tk.Canvas.__init__(
            self, parent,
            width=size, height=size,
            highlightthickness=0,
            bg=self.get_color("bg_card")
        )

    def _draw(self) -> None:
        """스피너 그리기"""
        self.delete("all")

        padding = self._thickness
        diameter = self._size - padding * 2

        # 배경 원
        self.create_oval(
            padding, padding,
            padding + diameter, padding + diameter,
            outline=self.get_color("progress_bg"),
            width=self._thickness
        )

        # 회전 아크
        self.create_arc(
            padding, padding,
            padding + diameter, padding + diameter,
            start=self._angle, extent=90,
            outline=self.get_color("progress_fill"),
            width=self._thickness,
            style="arc"
        )

    def start(self) -> None:
        """스피너 시작"""
        if self._running:
            return

        self._running = True
        self._animate()

    def stop(self) -> None:
        """스피너 중지"""
        self._running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _animate(self) -> None:
        """회전 애니메이션"""
        if not self._running:
            return

        self._angle = (self._angle + 10) % 360
        self._draw()
        self._after_id = self.after(30, self._animate)

    def apply_theme(self) -> None:
        self.configure(bg=self.get_color("bg_card"))
        self._draw()

    def destroy(self) -> None:
        self.stop()
        self.cleanup_theme()
        super().destroy()
