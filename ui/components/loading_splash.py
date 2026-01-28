"""
로딩 스플래시 화면 - 초기화 중 표시
"""
import logging
import tkinter as tk
from tkinter import ttk
import threading

logger = logging.getLogger(__name__)


class LoadingSplash:
    """로딩 스플래시 화면"""

    def __init__(self):
        """로딩 스플래시 초기화"""
        self.window = tk.Toplevel()
        self.window.title("초기화 중...")
        self.window.overrideredirect(True)  # 타이틀바 제거

        # 화면 중앙 배치
        window_width = 500
        window_height = 350
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 항상 위에 표시
        self.window.attributes('-topmost', True)

        # 컬러 테마 (STITCH 디자인 - 레드 테마)
        self.bg_color = "#f8f6f6"
        self.header_bg = "#fce8eb"
        self.primary_color = "#e31639"
        self.accent_color = "#e31639"
        self.text_color = "#1b0e10"
        self.secondary_text = "#64748b"

        self.window.configure(bg=self.bg_color)

        self.create_widgets()

    def create_widgets(self):
        """위젯 생성"""
        # 메인 컨테이너
        main_frame = tk.Frame(self.window, bg=self.bg_color, bd=2, relief=tk.RAISED)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # 헤더
        header = tk.Frame(main_frame, bg=self.header_bg, height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🚀 쇼핑 숏폼 메이커",
            font=("맑은 고딕", 20, "bold"),
            bg=self.header_bg,
            fg=self.primary_color
        ).pack(pady=(20, 5))

        tk.Label(
            header,
            text="초기화 중입니다...",
            font=("맑은 고딕", 10),
            bg=self.header_bg,
            fg=self.secondary_text
        ).pack()

        # 본문
        content = tk.Frame(main_frame, bg=self.bg_color)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # 현재 작업 라벨
        self.status_label = tk.Label(
            content,
            text="시작 중...",
            font=("맑은 고딕", 11),
            bg=self.bg_color,
            fg=self.text_color,
            wraplength=420,
            justify=tk.LEFT
        )
        self.status_label.pack(anchor=tk.W, pady=(0, 15))

        # 프로그레스 바
        style = ttk.Style()
        style.theme_use('default')
        style.configure(
            "Splash.Horizontal.TProgressbar",
            troughcolor=self.bg_color,
            bordercolor=self.bg_color,
            background=self.accent_color,
            lightcolor=self.accent_color,
            darkcolor=self.accent_color,
            thickness=8
        )

        self.progress = ttk.Progressbar(
            content,
            mode='indeterminate',
            style="Splash.Horizontal.TProgressbar",
            length=440
        )
        self.progress.pack(pady=(0, 20))
        self.progress.start(10)

        # 설명 섹션
        info_frame = tk.Frame(content, bg="#ffffff", bd=1, relief=tk.SOLID)
        info_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            info_frame,
            text="💡 잠시만 기다려주세요",
            font=("맑은 고딕", 10, "bold"),
            bg="#ffffff",
            fg=self.primary_color
        ).pack(anchor=tk.W, padx=15, pady=(12, 5))

        info_text = """다음 작업을 수행하고 있습니다:

• GPU 가속 확인 (CUDA/CuPy)
• TTS 음성 샘플 디렉토리 준비
• OCR 모델 로딩 (첫 실행시 다운로드, 1-2분 소요)
• API 키 설정 확인

처음 실행하시는 경우 OCR 모델 다운로드로 인해
시간이 다소 걸릴 수 있습니다."""

        tk.Label(
            info_frame,
            text=info_text,
            font=("맑은 고딕", 9),
            bg="#ffffff",
            fg=self.text_color,
            justify=tk.LEFT
        ).pack(anchor=tk.W, padx=15, pady=(0, 12))

        # 하단 팁
        tk.Label(
            main_frame,
            text="Tip: API 키는 상단 메뉴에서 설정할 수 있습니다",
            font=("맑은 고딕", 8),
            bg=self.bg_color,
            fg=self.secondary_text
        ).pack(pady=(0, 10))

    def update_status(self, message):
        """상태 메시지 업데이트"""
        if self.window.winfo_exists():
            self.status_label.config(text=message)
            self.window.update()

    def close(self):
        """스플래시 닫기"""
        try:
            if self.window.winfo_exists():
                self.progress.stop()
                self.window.destroy()
        except Exception as e:
            logger.debug(f"스플래시 닫기 중 오류 (무시됨): {e}")


def show_loading_splash():
    """로딩 스플래시 표시 (테스트용)"""
    root = tk.Tk()
    root.withdraw()  # 메인 윈도우 숨김

    splash = LoadingSplash()

    # 테스트: 2초 후 닫기
    def close_after_delay():
        import time
        time.sleep(2)
        splash.close()
        root.quit()

    threading.Thread(target=close_after_delay, daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    show_loading_splash()
