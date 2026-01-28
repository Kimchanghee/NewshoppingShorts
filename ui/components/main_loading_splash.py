"""
메인 앱 로딩 스플래시 화면
Tkinter 기반 로딩 창 (ProcessWindow 디자인과 통일)
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Dict, Any


class MainLoadingSplash:
    """
    메인 앱 초기화 중 표시되는 로딩 스플래시 화면
    ProcessWindow(PyQt5)와 동일한 디자인으로 구현
    """

    # 체크리스트 항목 정의
    CHECK_ITEMS = [
        ("ui", "UI 초기화", "사용자 인터페이스 구성"),
        ("theme", "테마 적용", "라이트/다크 테마 설정"),
        ("voice", "음성 샘플", "TTS 음성 샘플 확인"),
        ("settings", "설정 로드", "사용자 설정 불러오기"),
        ("api", "API 연결", "서비스 연결 준비"),
    ]

    def __init__(self, root: tk.Tk, on_complete: Optional[Callable] = None):
        """
        Args:
            root: Tkinter 루트 윈도우
            on_complete: 로딩 완료 시 콜백
        """
        self.root = root
        self.on_complete = on_complete
        self._progress = 0
        self._check_items: Dict[str, Dict[str, Any]] = {}

        # 테마 색상 (STITCH 디자인 - 레드 테마)
        self.primary_gradient_start = "#e31639"
        self.primary_gradient_end = "#ff4d6a"
        self.bg_color = "#f8f6f6"
        self.card_bg = "#ffffff"
        self.text_primary = "#1b0e10"
        self.text_secondary = "#64748b"
        self.text_muted = "#94a3b8"
        self.border_color = "#e2e8f0"
        self.success_color = "#16a34a"
        self.warning_color = "#d97706"
        self.error_color = "#dc2626"

        self._create_window()
        self._create_widgets()

    def _create_window(self) -> None:
        """로딩 창 생성"""
        self.window = tk.Toplevel(self.root)
        self.window.title("")
        self.window.overrideredirect(True)  # 타이틀바 제거
        self.window.attributes('-topmost', True)

        # 창 크기 및 위치 (ProcessWindow와 동일: 600x520)
        width = 600
        height = 520
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.window.geometry(f"{width}x{height}+{x}+{y}")

        # 배경색
        self.window.configure(bg=self.bg_color)

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 메인 프레임
        self.main_frame = tk.Frame(self.window, bg=self.bg_color)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 헤더 (보라색 그라데이션 효과)
        self._create_header()

        # 체크리스트 카드
        self._create_checklist()

        # 프로그레스 영역
        self._create_progress_area()

    def _create_header(self) -> None:
        """헤더 영역 생성"""
        self.header_frame = tk.Frame(
            self.main_frame,
            bg=self.primary_gradient_start,
            height=80
        )
        self.header_frame.pack(fill=tk.X)
        self.header_frame.pack_propagate(False)

        # 제목
        self.title_label = tk.Label(
            self.header_frame,
            text="쇼핑 숏폼 메이커",
            font=("맑은 고딕", 18, "bold"),
            bg=self.primary_gradient_start,
            fg="#ffffff"
        )
        self.title_label.pack(pady=(15, 5))

        # 상태 메시지
        self.status_label = tk.Label(
            self.header_frame,
            text="시스템을 초기화하고 있습니다...",
            font=("맑은 고딕", 11),
            bg=self.primary_gradient_start,
            fg="rgba(255,255,255,0.9)"
        )
        self.status_label.pack()

    def _create_checklist(self) -> None:
        """체크리스트 카드 생성"""
        # 카드 프레임
        self.checklist_frame = tk.Frame(
            self.main_frame,
            bg=self.card_bg,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        self.checklist_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=(15, 10))

        # 카드 제목
        title_label = tk.Label(
            self.checklist_frame,
            text="초기화 항목",
            font=("맑은 고딕", 12, "bold"),
            bg=self.card_bg,
            fg=self.text_primary
        )
        title_label.pack(anchor=tk.W, padx=20, pady=(15, 10))

        # 체크리스트 항목들
        for item_id, item_title, item_desc in self.CHECK_ITEMS:
            self._create_check_item(item_id, item_title, item_desc)

    def _create_check_item(self, item_id: str, title: str, description: str) -> None:
        """체크리스트 항목 생성"""
        # 항목 프레임
        item_frame = tk.Frame(
            self.checklist_frame,
            bg="#f9fafb",
            highlightbackground=self.border_color,
            highlightthickness=0
        )
        item_frame.pack(fill=tk.X, padx=12, pady=3)

        # 내부 패딩
        inner_frame = tk.Frame(item_frame, bg="#f9fafb")
        inner_frame.pack(fill=tk.X, padx=10, pady=8)

        # 아이콘
        icon_label = tk.Label(
            inner_frame,
            text="⏳",
            font=("맑은 고딕", 12),
            bg="#f9fafb",
            fg=self.text_muted
        )
        icon_label.pack(side=tk.LEFT)

        # 제목
        title_label = tk.Label(
            inner_frame,
            text=title,
            font=("맑은 고딕", 10, "bold"),
            bg="#f9fafb",
            fg=self.text_secondary
        )
        title_label.pack(side=tk.LEFT, padx=(8, 0))

        # 설명
        desc_label = tk.Label(
            inner_frame,
            text=description,
            font=("맑은 고딕", 9),
            bg="#f9fafb",
            fg=self.text_muted
        )
        desc_label.pack(side=tk.LEFT, padx=(15, 0))

        # 상태
        status_label = tk.Label(
            inner_frame,
            text="대기",
            font=("맑은 고딕", 9),
            bg="#f9fafb",
            fg=self.text_muted
        )
        status_label.pack(side=tk.RIGHT)

        # 저장
        self._check_items[item_id] = {
            'frame': item_frame,
            'inner': inner_frame,
            'icon': icon_label,
            'title': title_label,
            'desc': desc_label,
            'status': status_label
        }

    def _create_progress_area(self) -> None:
        """프로그레스 영역 생성"""
        # 프로그레스 프레임
        self.progress_frame = tk.Frame(
            self.main_frame,
            bg=self.card_bg,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        self.progress_frame.pack(fill=tk.X, padx=25, pady=(5, 20))

        # 내부 패딩
        inner = tk.Frame(self.progress_frame, bg=self.card_bg)
        inner.pack(fill=tk.X, padx=20, pady=15)

        # 라벨 프레임 (진행률 + 퍼센트)
        label_frame = tk.Frame(inner, bg=self.card_bg)
        label_frame.pack(fill=tk.X)

        tk.Label(
            label_frame,
            text="진행률",
            font=("맑은 고딕", 10, "bold"),
            bg=self.card_bg,
            fg=self.text_primary
        ).pack(side=tk.LEFT)

        self.percent_label = tk.Label(
            label_frame,
            text="0%",
            font=("맑은 고딕", 11, "bold"),
            bg=self.card_bg,
            fg=self.primary_gradient_start
        )
        self.percent_label.pack(side=tk.RIGHT)

        # 프로그레스 바 스타일
        style = ttk.Style()
        style.theme_use('default')
        style.configure(
            "MainLoading.Horizontal.TProgressbar",
            troughcolor="#fce8eb",
            bordercolor="#fce8eb",
            background=self.primary_gradient_start,
            lightcolor=self.primary_gradient_end,
            darkcolor=self.primary_gradient_start,
            thickness=12
        )

        # 프로그레스 바
        self.progress_bar = ttk.Progressbar(
            inner,
            mode='determinate',
            style="MainLoading.Horizontal.TProgressbar",
            length=510,
            maximum=100
        )
        self.progress_bar.pack(fill=tk.X, pady=(10, 0))

    def update_status(self, message: str) -> None:
        """상태 메시지 업데이트"""
        if self.window.winfo_exists():
            self.status_label.configure(text=message)
            self.window.update()

    def update_progress(self, value: int) -> None:
        """프로그레스 바 업데이트"""
        if self.window.winfo_exists():
            self._progress = min(100, max(0, value))
            self.progress_bar['value'] = self._progress
            self.percent_label.configure(text=f"{self._progress}%")
            self.window.update()

    def update_check_item(self, item_id: str, status: str, message: str = None) -> None:
        """
        체크리스트 항목 상태 업데이트

        Args:
            item_id: 항목 ID
            status: 'checking', 'success', 'warning', 'error'
            message: 상태 메시지 (선택)
        """
        if item_id not in self._check_items:
            return

        if not self.window.winfo_exists():
            return

        item = self._check_items[item_id]

        if status == 'checking':
            item['icon'].configure(text="🔄")
            item['frame'].configure(bg="#fce8eb")
            item['inner'].configure(bg="#fce8eb")
            item['icon'].configure(bg="#fce8eb")
            item['title'].configure(bg="#fce8eb", fg=self.primary_gradient_start)
            item['desc'].configure(bg="#fce8eb", fg="#ff6b84")
            item['status'].configure(bg="#fce8eb", text="확인 중...", fg=self.primary_gradient_start)
        elif status == 'success':
            item['icon'].configure(text="✅")
            item['frame'].configure(bg="#f0fdf4")
            item['inner'].configure(bg="#f0fdf4")
            item['icon'].configure(bg="#f0fdf4")
            item['title'].configure(bg="#f0fdf4", fg="#166534")
            item['desc'].configure(bg="#f0fdf4", fg="#22c55e")
            item['status'].configure(bg="#f0fdf4", text=message or "완료", fg=self.success_color)
        elif status == 'warning':
            item['icon'].configure(text="⚠️")
            item['frame'].configure(bg="#fffbeb")
            item['inner'].configure(bg="#fffbeb")
            item['icon'].configure(bg="#fffbeb")
            item['title'].configure(bg="#fffbeb", fg="#92400e")
            item['desc'].configure(bg="#fffbeb", fg="#f59e0b")
            item['status'].configure(bg="#fffbeb", text=message or "경고", fg=self.warning_color)
        elif status == 'error':
            item['icon'].configure(text="❌")
            item['frame'].configure(bg="#fef2f2")
            item['inner'].configure(bg="#fef2f2")
            item['icon'].configure(bg="#fef2f2")
            item['title'].configure(bg="#fef2f2", fg="#991b1b")
            item['desc'].configure(bg="#fef2f2", fg="#ef4444")
            item['status'].configure(bg="#fef2f2", text=message or "실패", fg=self.error_color)

        self.window.update()

    def close(self) -> None:
        """스플래시 닫기"""
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except tk.TclError:
            pass

        if self.on_complete:
            self.on_complete()

    def show(self) -> None:
        """스플래시 표시"""
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self.window.update()


def test_loading_splash():
    """테스트용 함수"""
    import time
    import threading

    root = tk.Tk()
    root.withdraw()

    splash = MainLoadingSplash(root)
    splash.show()

    def simulate_loading():
        items = [
            ("ui", 20),
            ("theme", 40),
            ("voice", 60),
            ("settings", 80),
            ("api", 100),
        ]

        for item_id, progress in items:
            splash.update_check_item(item_id, "checking")
            splash.update_status(f"{item_id} 초기화 중...")
            time.sleep(0.5)

            splash.update_check_item(item_id, "success")
            splash.update_progress(progress)
            time.sleep(0.3)

        splash.update_status("초기화 완료!")
        time.sleep(1)
        splash.close()
        root.quit()

    threading.Thread(target=simulate_loading, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    test_loading_splash()
