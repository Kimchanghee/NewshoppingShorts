"""
설정 모달 다이얼로그
API 키 관리 + 저장 폴더 설정 + 유튜브 채널 연결
"""
import logging
import shutil
import tkinter as tk
from tkinter import ttk, filedialog
import os
import subprocess
import sys
from typing import Optional
from .base_widget import ThemedMixin
from .rounded_widgets import create_rounded_button, RoundedEntry, ModernScrollbar, StatusBadge
from ..theme_manager import ThemeManager, get_theme_manager
from managers.youtube_manager import get_youtube_manager

logger = logging.getLogger(__name__)


class SettingsModal(tk.Toplevel, ThemedMixin):
    """설정 모달 윈도우"""

    def __init__(
        self,
        parent: tk.Widget,
        gui,  # VideoAnalyzerGUI 인스턴스
        theme_manager: Optional[ThemeManager] = None
    ):
        self.gui = gui
        self.__init_themed__(theme_manager)

        tk.Toplevel.__init__(self, parent)

        # 모달 설정
        self.title("설정")
        self.configure(bg=self.get_color("bg_main"))
        self.resizable(False, False)

        # YouTube 매니저 초기화
        self._youtube_manager = get_youtube_manager(gui=gui)

        # 윈도우 크기 및 위치
        width = 560
        height = 680
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        # 모달 동작 (부모 윈도우 차단)
        self.transient(parent)
        self.grab_set()

        # 닫기 버튼 처리
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._create_widgets()

        # ESC로 닫기
        self.bind("<Escape>", lambda e: self._on_close())

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 헤더
        header = tk.Frame(self, bg=self.get_color("bg_header"), height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="설정",
            font=("맑은 고딕", 14, "bold"),
            bg=self.get_color("bg_header"),
            fg=self.get_color("text_primary"),
            padx=20
        ).pack(side=tk.LEFT, pady=12)

        # 닫기 버튼
        close_btn = tk.Label(
            header,
            text="X",
            font=("맑은 고딕", 14),
            bg=self.get_color("bg_header"),
            fg=self.get_color("text_secondary"),
            cursor="hand2"
        )
        close_btn.pack(side=tk.RIGHT, padx=16, pady=12)
        close_btn.bind("<Button-1>", lambda e: self._on_close())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=self.get_color("error")))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=self.get_color("text_secondary")))

        # 구분선
        tk.Frame(self, bg=self.get_color("border_light"), height=1).pack(fill=tk.X)

        # 스크롤 가능한 컨텐츠 영역
        canvas = tk.Canvas(self, bg=self.get_color("bg_main"), highlightthickness=0)
        scrollbar = ModernScrollbar(
            self,
            command=canvas.yview,
            width=8,
            theme_manager=self._theme_manager
        )
        scrollable_frame = tk.Frame(canvas, bg=self.get_color("bg_main"))

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=520)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=16)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=16, padx=(0, 4))

        # 마우스 휠 스크롤
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # API 설정 섹션
        self._create_api_section(scrollable_frame)

        # 구분선
        tk.Frame(scrollable_frame, bg=self.get_color("border_light"), height=1).pack(fill=tk.X, pady=16)

        # 저장 폴더 섹션
        self._create_folder_section(scrollable_frame)

        # 구분선
        tk.Frame(scrollable_frame, bg=self.get_color("border_light"), height=1).pack(fill=tk.X, pady=16)

        # 유튜브 채널 연결 섹션
        self._create_youtube_section(scrollable_frame)

        # 구분선
        tk.Frame(scrollable_frame, bg=self.get_color("border_light"), height=1).pack(fill=tk.X, pady=16)

        # 튜토리얼 섹션
        self._create_tutorial_section(scrollable_frame)

    def _create_api_section(self, parent: tk.Frame) -> None:
        """API 관리 섹션"""
        # 섹션 헤더
        tk.Label(
            parent,
            text="API 설정",
            font=("맑은 고딕", 12, "bold"),
            bg=self.get_color("bg_main"),
            fg=self.get_color("text_primary"),
            anchor="w"
        ).pack(fill=tk.X)

        # 설명
        tk.Label(
            parent,
            text="Google Gemini API 키가 필요합니다. 여러 개의 API 키를 등록하면 부하가 분산됩니다.",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_main"),
            fg=self.get_color("text_secondary"),
            anchor="w",
            wraplength=440
        ).pack(fill=tk.X, pady=(4, 12))

        # 버튼 영역
        btn_frame = tk.Frame(parent, bg=self.get_color("bg_main"))
        btn_frame.pack(fill=tk.X)

        # API 키 관리 버튼
        api_btn = create_rounded_button(
            btn_frame,
            text="API 키 관리",
            command=self._open_api_manager,
            style="primary",
            theme_manager=self._theme_manager
        )
        api_btn.pack(side=tk.LEFT)

        # API 상태 확인 버튼
        status_btn = create_rounded_button(
            btn_frame,
            text="API 상태 확인",
            command=self._check_api_status,
            style="outline",
            theme_manager=self._theme_manager
        )
        status_btn.pack(side=tk.LEFT, padx=(8, 0))

        # API 상태 배지
        self._api_status_badge = StatusBadge(
            btn_frame,
            text="확인 중...",
            status="default",
            theme_manager=self._theme_manager
        )
        self._api_status_badge.pack(side=tk.RIGHT)

        # 초기 API 상태 표시
        self._update_api_status()

    def _create_folder_section(self, parent: tk.Frame) -> None:
        """저장 폴더 섹션"""
        # 섹션 헤더
        tk.Label(
            parent,
            text="저장 위치",
            font=("맑은 고딕", 12, "bold"),
            bg=self.get_color("bg_main"),
            fg=self.get_color("text_primary"),
            anchor="w"
        ).pack(fill=tk.X)

        # 현재 경로 표시
        path_frame = tk.Frame(parent, bg=self.get_color("bg_main"))
        path_frame.pack(fill=tk.X, pady=(8, 12))

        tk.Label(
            path_frame,
            text="현재 저장 폴더:",
            font=("맑은 고딕", 9, "bold"),
            bg=self.get_color("bg_main"),
            fg=self.get_color("text_primary")
        ).pack(side=tk.LEFT)

        self._folder_path_label = tk.Label(
            path_frame,
            text=self._get_output_folder(),
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_main"),
            fg=self.get_color("text_secondary"),
            anchor="w"
        )
        self._folder_path_label.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

        # 버튼 영역
        btn_frame = tk.Frame(parent, bg=self.get_color("bg_main"))
        btn_frame.pack(fill=tk.X)

        # 폴더 선택 버튼
        folder_btn = create_rounded_button(
            btn_frame,
            text="폴더 선택",
            command=self._select_folder,
            style="primary",
            theme_manager=self._theme_manager
        )
        folder_btn.pack(side=tk.LEFT)

        # 폴더 열기 버튼
        open_btn = create_rounded_button(
            btn_frame,
            text="폴더 열기",
            command=self._open_folder,
            style="secondary",
            theme_manager=self._theme_manager
        )
        open_btn.pack(side=tk.LEFT, padx=(8, 0))

    def _get_output_folder(self) -> str:
        """현재 출력 폴더 경로 반환"""
        return getattr(self.gui, 'output_folder_path', os.path.join(os.getcwd(), "outputs"))

    def _open_api_manager(self) -> None:
        """API 키 관리 창 열기"""
        show_api_key_manager = getattr(self.gui, 'show_api_key_manager', None)
        if show_api_key_manager is not None:
            show_api_key_manager()

    def _check_api_status(self) -> None:
        """API 상태 확인"""
        show_api_status = getattr(self.gui, 'show_api_status', None)
        if show_api_status is not None:
            show_api_status()

    def _update_api_status(self) -> None:
        """API 상태 배지 업데이트"""
        try:
            import config
            key_count = len(getattr(config, 'GEMINI_API_KEYS', []))
            if key_count > 0:
                self._api_status_badge.set_text(f"{key_count}개 등록됨")
                self._api_status_badge.set_status("success")
            else:
                self._api_status_badge.set_text("키 없음")
                self._api_status_badge.set_status("error")
        except Exception as e:
            logger.debug("Failed to check API status: %s", e)
            self._api_status_badge.set_text("확인 불가")
            self._api_status_badge.set_status("warning")

    def _select_folder(self) -> None:
        """저장 폴더 선택"""
        select_output_folder = getattr(self.gui, 'select_output_folder', None)
        if select_output_folder is not None:
            select_output_folder()
            # 라벨 업데이트
            self._folder_path_label.configure(text=self._get_output_folder())

    def _open_folder(self) -> None:
        """저장 폴더 열기"""
        output_path = self._get_output_folder()
        os.makedirs(output_path, exist_ok=True)

        try:
            if sys.platform == 'win32':
                os.startfile(output_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', output_path], timeout=10)
            else:
                subprocess.run(['xdg-open', output_path], timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("Folder open command timed out")
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")

    def _create_youtube_section(self, parent: tk.Frame) -> None:
        """유튜브 채널 연결 섹션"""
        bg_main = self.get_color("bg_main")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        primary = self.get_color("primary")
        success = self.get_color("success")
        bg_input = self.get_color("bg_input")
        border_light = self.get_color("border_light")

        # 섹션 헤더
        tk.Label(
            parent,
            text="유튜브 채널 연결",
            font=("맑은 고딕", 12, "bold"),
            bg=bg_main,
            fg=text_primary,
            anchor="w"
        ).pack(fill=tk.X)

        # 설명
        tk.Label(
            parent,
            text="유튜브 채널을 연결하면 완성된 영상을 자동으로 업로드할 수 있습니다.",
            font=("맑은 고딕", 9),
            bg=bg_main,
            fg=text_secondary,
            anchor="w",
            wraplength=480
        ).pack(fill=tk.X, pady=(4, 12))

        # OAuth 클라이언트 설정 파일 섹션
        oauth_frame = tk.Frame(parent, bg=bg_main)
        oauth_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            oauth_frame,
            text="OAuth 클라이언트 파일:",
            font=("맑은 고딕", 9, "bold"),
            bg=bg_main,
            fg=text_primary
        ).pack(side=tk.LEFT)

        # 파일 경로 표시
        self._client_secrets_path = self._youtube_manager._get_client_secrets_path()
        file_exists = os.path.exists(self._client_secrets_path)

        self._oauth_file_label = tk.Label(
            oauth_frame,
            text=os.path.basename(self._client_secrets_path) if file_exists else "파일 없음",
            font=("맑은 고딕", 9),
            bg=bg_main,
            fg=success if file_exists else self.get_color("error")
        )
        self._oauth_file_label.pack(side=tk.LEFT, padx=(8, 0))

        # 파일 찾기 버튼
        browse_btn = create_rounded_button(
            oauth_frame,
            text="파일 찾기",
            command=self._browse_client_secrets,
            style="outline",
            theme_manager=self._theme_manager
        )
        browse_btn.pack(side=tk.RIGHT)

        # OAuth 도움말
        oauth_help_frame = tk.Frame(parent, bg=self.get_color("info_bg"))
        oauth_help_frame.pack(fill=tk.X, pady=(0, 12))

        help_text = (
            "1. Google Cloud Console에서 프로젝트 생성\n"
            "2. YouTube Data API v3 활성화\n"
            "3. OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱)\n"
            "4. client_secrets.json 다운로드 후 파일 찾기"
        )
        tk.Label(
            oauth_help_frame,
            text=help_text,
            font=("맑은 고딕", 8),
            bg=self.get_color("info_bg"),
            fg=self.get_color("info"),
            justify=tk.LEFT,
            anchor="w",
            padx=12,
            pady=8
        ).pack(fill=tk.X)

        # 채널 연결 상태
        status_frame = tk.Frame(parent, bg=bg_main)
        status_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            status_frame,
            text="연결 상태:",
            font=("맑은 고딕", 9, "bold"),
            bg=bg_main,
            fg=text_primary
        ).pack(side=tk.LEFT)

        # 연결 상태 배지
        self._youtube_status_badge = StatusBadge(
            status_frame,
            text="연결 안됨",
            status="default",
            theme_manager=self._theme_manager
        )
        self._youtube_status_badge.pack(side=tk.LEFT, padx=(8, 0))

        # 채널 이름 표시
        self._youtube_channel_label = tk.Label(
            status_frame,
            text="",
            font=("맑은 고딕", 9),
            bg=bg_main,
            fg=success
        )
        self._youtube_channel_label.pack(side=tk.LEFT, padx=(8, 0))

        # 연결/해제 버튼
        btn_frame = tk.Frame(parent, bg=bg_main)
        btn_frame.pack(fill=tk.X, pady=(0, 16))

        self._connect_btn = create_rounded_button(
            btn_frame,
            text="채널 연결",
            command=self._connect_youtube,
            style="primary",
            theme_manager=self._theme_manager
        )
        self._connect_btn.pack(side=tk.LEFT)

        self._disconnect_btn = create_rounded_button(
            btn_frame,
            text="연결 해제",
            command=self._disconnect_youtube,
            style="danger",
            theme_manager=self._theme_manager
        )
        self._disconnect_btn.pack(side=tk.LEFT, padx=(8, 0))

        # 자동 업로드 설정
        upload_header = tk.Frame(parent, bg=bg_main)
        upload_header.pack(fill=tk.X, pady=(8, 4))

        tk.Label(
            upload_header,
            text="자동 업로드 설정",
            font=("맑은 고딕", 11, "bold"),
            bg=bg_main,
            fg=text_primary
        ).pack(side=tk.LEFT)

        # 자동 업로드 토글
        toggle_frame = tk.Frame(parent, bg=bg_main)
        toggle_frame.pack(fill=tk.X, pady=(4, 8))

        self._auto_upload_var = tk.BooleanVar(value=self._youtube_manager.get_upload_settings().enabled)

        tk.Label(
            toggle_frame,
            text="자동 업로드",
            font=("맑은 고딕", 10),
            bg=bg_main,
            fg=text_primary
        ).pack(side=tk.LEFT)

        self._auto_upload_check = tk.Checkbutton(
            toggle_frame,
            variable=self._auto_upload_var,
            command=self._toggle_auto_upload,
            bg=bg_main,
            activebackground=bg_main,
            selectcolor=bg_main
        )
        self._auto_upload_check.pack(side=tk.LEFT, padx=(8, 0))

        enabled_label = tk.Label(
            toggle_frame,
            text="활성화" if self._auto_upload_var.get() else "비활성화",
            font=("맑은 고딕", 9),
            bg=bg_main,
            fg=success if self._auto_upload_var.get() else text_secondary
        )
        enabled_label.pack(side=tk.LEFT, padx=(4, 0))
        self._auto_upload_label = enabled_label

        # 업로드 간격 설정
        interval_frame = tk.Frame(parent, bg=bg_main)
        interval_frame.pack(fill=tk.X, pady=(4, 8))

        tk.Label(
            interval_frame,
            text="업로드 간격 (분)",
            font=("맑은 고딕", 10),
            bg=bg_main,
            fg=text_primary
        ).pack(side=tk.LEFT)

        self._interval_var = tk.StringVar(value=str(self._youtube_manager.get_upload_settings().interval_minutes))
        interval_entry = tk.Entry(
            interval_frame,
            textvariable=self._interval_var,
            width=6,
            font=("맑은 고딕", 10),
            bg=self.get_color("bg_input"),
            fg=text_primary,
            relief=tk.FLAT,
            bd=1
        )
        interval_entry.pack(side=tk.LEFT, padx=(8, 0))
        interval_entry.bind("<FocusOut>", self._update_interval)
        interval_entry.bind("<Return>", self._update_interval)

        tk.Label(
            interval_frame,
            text="(1~1440분)",
            font=("맑은 고딕", 8),
            bg=bg_main,
            fg=text_secondary
        ).pack(side=tk.LEFT, padx=(4, 0))

        # SEO 설정
        seo_header = tk.Frame(parent, bg=bg_main)
        seo_header.pack(fill=tk.X, pady=(12, 4))

        tk.Label(
            seo_header,
            text="SEO 자동 생성",
            font=("맑은 고딕", 11, "bold"),
            bg=bg_main,
            fg=text_primary
        ).pack(side=tk.LEFT)

        # SEO 체크박스들
        upload_settings = self._youtube_manager.get_upload_settings()

        self._auto_title_var = tk.BooleanVar(value=upload_settings.auto_title)
        self._auto_desc_var = tk.BooleanVar(value=upload_settings.auto_description)
        self._auto_tags_var = tk.BooleanVar(value=upload_settings.auto_hashtags)

        seo_options = [
            ("제목 자동 생성", self._auto_title_var),
            ("설명 자동 생성", self._auto_desc_var),
            ("해시태그 자동 생성", self._auto_tags_var),
        ]

        for label_text, var in seo_options:
            opt_frame = tk.Frame(parent, bg=bg_main)
            opt_frame.pack(fill=tk.X, pady=2)

            tk.Checkbutton(
                opt_frame,
                text=label_text,
                variable=var,
                command=self._update_seo_settings,
                font=("맑은 고딕", 9),
                bg=bg_main,
                fg=text_primary,
                activebackground=bg_main,
                selectcolor=bg_main
            ).pack(side=tk.LEFT)

        # 공개 설정
        privacy_frame = tk.Frame(parent, bg=bg_main)
        privacy_frame.pack(fill=tk.X, pady=(12, 8))

        tk.Label(
            privacy_frame,
            text="기본 공개 설정",
            font=("맑은 고딕", 10),
            bg=bg_main,
            fg=text_primary
        ).pack(side=tk.LEFT)

        self._privacy_var = tk.StringVar(value=upload_settings.default_privacy)
        privacy_options = [("공개", "public"), ("일부공개", "unlisted"), ("비공개", "private")]

        for text, value in privacy_options:
            tk.Radiobutton(
                privacy_frame,
                text=text,
                variable=self._privacy_var,
                value=value,
                command=self._update_privacy,
                font=("맑은 고딕", 9),
                bg=bg_main,
                fg=text_primary,
                activebackground=bg_main,
                selectcolor=bg_main
            ).pack(side=tk.LEFT, padx=(8, 0))

        # 초기 상태 업데이트
        self._update_youtube_status()

    def _browse_client_secrets(self) -> None:
        """OAuth 클라이언트 설정 파일 찾기"""
        file_path = filedialog.askopenfilename(
            title="OAuth 클라이언트 파일 선택",
            filetypes=[
                ("JSON 파일", "*.json"),
                ("모든 파일", "*.*")
            ],
            initialdir=os.path.dirname(self._client_secrets_path)
        )

        if file_path:
            # 파일을 프로젝트 루트로 복사
            target_path = self._youtube_manager._get_client_secrets_path()

            try:
                shutil.copy2(file_path, target_path)
                self._client_secrets_path = target_path

                # UI 업데이트
                self._oauth_file_label.configure(
                    text=os.path.basename(target_path),
                    fg=self.get_color("success")
                )

                from .custom_dialog import show_info
                show_info(self, "파일 등록", f"OAuth 클라이언트 파일이 등록되었습니다.\n\n이제 '채널 연결' 버튼을 눌러 YouTube 채널을 연결하세요.")

            except Exception as e:
                logger.error(f"Failed to copy client_secrets.json: {e}")
                from .custom_dialog import show_error
                show_error(self, "오류", f"파일 복사 실패:\n{e}")

    def _connect_youtube(self) -> None:
        """유튜브 채널 연결"""
        # 먼저 client_secrets.json 파일 확인
        if not os.path.exists(self._client_secrets_path):
            from .custom_dialog import show_warning
            show_warning(
                self,
                "파일 필요",
                "OAuth 클라이언트 파일이 필요합니다.\n\n"
                "'파일 찾기' 버튼을 눌러 client_secrets.json 파일을 선택해주세요."
            )
            return

        success = self._youtube_manager.connect_channel(self._client_secrets_path)
        if success:
            from .custom_dialog import show_info
            show_info(self, "연결 완료", "유튜브 채널이 연결되었습니다.")
        else:
            from .custom_dialog import show_error
            show_error(
                self,
                "연결 실패",
                "유튜브 채널 연결에 실패했습니다.\n\n"
                "브라우저에서 Google 계정 인증이 필요합니다.\n"
                "팝업이 차단되었는지 확인해주세요."
            )
        self._update_youtube_status()

    def _disconnect_youtube(self) -> None:
        """유튜브 채널 연결 해제"""
        from .custom_dialog import show_question
        if show_question(self, "연결 해제", "유튜브 채널 연결을 해제하시겠습니까?"):
            self._youtube_manager.disconnect_channel()
            from .custom_dialog import show_info
            show_info(self, "연결 해제", "유튜브 채널 연결이 해제되었습니다.")
            self._update_youtube_status()

    def _update_youtube_status(self) -> None:
        """유튜브 연결 상태 업데이트"""
        if self._youtube_manager.is_connected():
            channel = self._youtube_manager.get_channel_info()
            self._youtube_status_badge.set_text("연결됨")
            self._youtube_status_badge.set_status("success")
            self._youtube_channel_label.configure(
                text=f"({channel.channel_name})" if channel else ""
            )
            self._connect_btn.configure(state="disabled")
            self._disconnect_btn.configure(state="normal")
        else:
            self._youtube_status_badge.set_text("연결 안됨")
            self._youtube_status_badge.set_status("default")
            self._youtube_channel_label.configure(text="")
            self._connect_btn.configure(state="normal")
            self._disconnect_btn.configure(state="disabled")

    def _toggle_auto_upload(self) -> None:
        """자동 업로드 토글"""
        enabled = self._auto_upload_var.get()
        self._youtube_manager.set_upload_enabled(enabled)
        self._auto_upload_label.configure(
            text="활성화" if enabled else "비활성화",
            fg=self.get_color("success") if enabled else self.get_color("text_secondary")
        )

    def _update_interval(self, event=None) -> None:
        """업로드 간격 업데이트"""
        try:
            minutes = int(self._interval_var.get())
            minutes = max(1, min(1440, minutes))
            self._interval_var.set(str(minutes))
            self._youtube_manager.set_upload_interval(minutes)
        except ValueError:
            self._interval_var.set(str(self._youtube_manager.get_upload_settings().interval_minutes))

    def _update_seo_settings(self) -> None:
        """SEO 설정 업데이트"""
        self._youtube_manager.set_seo_settings(
            auto_title=self._auto_title_var.get(),
            auto_description=self._auto_desc_var.get(),
            auto_hashtags=self._auto_tags_var.get()
        )

    def _update_privacy(self) -> None:
        """공개 설정 업데이트"""
        self._youtube_manager.set_privacy_settings(self._privacy_var.get())

    def _create_tutorial_section(self, parent: tk.Frame) -> None:
        """튜토리얼 섹션"""
        bg_main = self.get_color("bg_main")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")

        # 섹션 헤더
        tk.Label(
            parent,
            text="도움말",
            font=("맑은 고딕", 12, "bold"),
            bg=bg_main,
            fg=text_primary,
            anchor="w"
        ).pack(fill=tk.X)

        # 설명
        tk.Label(
            parent,
            text="앱 사용법을 다시 확인하고 싶을 때 튜토리얼을 볼 수 있습니다.",
            font=("맑은 고딕", 9),
            bg=bg_main,
            fg=text_secondary,
            anchor="w",
            wraplength=480
        ).pack(fill=tk.X, pady=(4, 12))

        # 버튼 영역
        btn_frame = tk.Frame(parent, bg=bg_main)
        btn_frame.pack(fill=tk.X)

        # 튜토리얼 다시 보기 버튼
        tutorial_btn = create_rounded_button(
            btn_frame,
            text="튜토리얼 다시 보기",
            command=self._show_tutorial,
            style="primary",
            theme_manager=self._theme_manager
        )
        tutorial_btn.pack(side=tk.LEFT)

    def _show_tutorial(self) -> None:
        """튜토리얼 표시"""
        # 모달 닫기
        self._on_close()

        # 튜토리얼 표시
        show_tutorial = getattr(self.gui, 'show_tutorial', None)
        if show_tutorial is not None:
            show_tutorial()

    def _on_close(self) -> None:
        """모달 닫기"""
        # 마우스 휠 바인딩 해제
        try:
            self.unbind_all("<MouseWheel>")
        except Exception as e:
            logger.debug("Failed to unbind mousewheel: %s", e)
        self.grab_release()
        self.destroy()  # destroy()에서 cleanup_theme() 호출됨

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_main"))

        # 폴더 경로 레이블 테마 적용
        if hasattr(self, '_folder_path_label'):
            try:
                self._folder_path_label.configure(
                    bg=self.get_color("bg_main"),
                    fg=self.get_color("text_secondary")
                )
            except Exception as e:
                logger.debug("Failed to apply theme to folder path label: %s", e)

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()
