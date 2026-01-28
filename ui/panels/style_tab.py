"""
스타일 탭 패널 (심플 버전)
음성/폰트/CTA 선택을 단일 스크롤 가능한 컬럼으로 통합
"""
import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List

from managers.settings_manager import get_settings_manager

logger = logging.getLogger(__name__)
from ..components.tab_container import TabContent
from ..components.base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager


# CTA 옵션 정의 (10개)
CTA_OPTIONS = [
    {"name": "댓글형", "id": "default", "lines": ["영상 속 제품 정보는", "아래 고정댓글에서", "확인해 보세요!"]},
    {"name": "캡션형", "id": "option1", "lines": ["궁금하신 제품 정보는", "영상 하단 캡션에", "적어두었습니다."]},
    {"name": "직진형", "id": "option2", "lines": ["이 제품이 마음에 든다면", "하단 제품 링크를", "지금 눌러보세요!"]},
    {"name": "링크형", "id": "option3", "lines": ["구매 정보가 궁금할 땐", "영상 아래 링크를", "바로 클릭하세요."]},
    {"name": "버튼형", "id": "option4", "lines": ["영상 속 핫템 정보는", "왼쪽 하단 버튼에서", "확인 가능합니다!"]},
    # 추가 5개
    {"name": "할인형", "id": "option5", "lines": ["지금 구매하면", "특별 할인 혜택이", "적용됩니다!"]},
    {"name": "한정형", "id": "option6", "lines": ["수량 한정 상품!", "품절 전에", "서두르세요!"]},
    {"name": "후기형", "id": "option7", "lines": ["실제 구매 후기가", "궁금하다면", "댓글을 확인하세요!"]},
    {"name": "질문형", "id": "option8", "lines": ["이 제품 어떠세요?", "의견을 댓글로", "남겨주세요!"]},
    {"name": "팔로우형", "id": "option9", "lines": ["더 많은 추천템은", "팔로우하고", "확인하세요!"]},
]


class StyleTab(TabContent):
    """스타일 탭 - 심플한 단일 컬럼 레이아웃"""

    def __init__(self, parent: tk.Widget, gui, theme_manager: Optional[ThemeManager] = None):
        self.gui = gui
        self.voice_items: Dict[str, dict] = {}
        self.font_items: Dict[str, dict] = {}
        self.cta_items: Dict[str, dict] = {}
        self.watermark_position_items: Dict[str, dict] = {}
        super().__init__(parent, theme_manager=theme_manager, padding=(0, 0))
        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 스크롤 가능한 컨테이너
        self.canvas = tk.Canvas(self.inner, bg=self.get_color("bg_main"), highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.inner, orient="vertical", command=self.canvas.yview)
        self.scrollable = tk.Frame(self.canvas, bg=self.get_color("bg_main"))

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.scrollable.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.scrollable.bind("<MouseWheel>", self._on_mousewheel)

        # 4개 섹션 생성
        self._create_voice_section()
        self._create_font_section()
        self._create_cta_section()
        self._create_watermark_section()

        # 저장된 설정 로드
        self._load_saved_settings()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ===== 음성 섹션 =====
    def _create_voice_section(self) -> None:
        """음성 선택 섹션"""
        section = self._create_section_frame("음성 선택")

        # 선택 카운트 표시
        self.voice_count_label = tk.Label(
            section.header_frame,
            text="0개 선택",
            font=("맑은 고딕", 9),
            bg=self.get_color("primary"),
            fg="#FFFFFF",
            padx=6, pady=2
        )
        self.voice_count_label.pack(side=tk.RIGHT)

        # 전체선택/해제 버튼
        btn_frame = tk.Frame(section.content, bg=self.get_color("bg_card"))
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        self.select_all_btn = tk.Label(
            btn_frame, text="전체선택", font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"), fg=self.get_color("primary"),
            cursor="hand2", padx=6
        )
        self.select_all_btn.pack(side=tk.LEFT)
        self.select_all_btn.bind("<Button-1>", lambda e: self._select_all_voices())

        self.deselect_all_btn = tk.Label(
            btn_frame, text="전체해제", font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"), fg=self.get_color("text_secondary"),
            cursor="hand2", padx=6
        )
        self.deselect_all_btn.pack(side=tk.LEFT)
        self.deselect_all_btn.bind("<Button-1>", lambda e: self._deselect_all_voices())

        # 음성 목록 (2열 그리드)
        grid_frame = tk.Frame(section.content, bg=self.get_color("bg_card"))
        grid_frame.pack(fill=tk.X)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        for i, profile in enumerate(self.gui.voice_profiles):
            row, col = i // 2, i % 2
            self._create_voice_item(grid_frame, profile, row, col)

    def _create_voice_item(self, parent, profile: dict, row: int, col: int) -> None:
        """음성 항목 생성"""
        vid = profile["id"]

        # 변수 초기화
        if vid not in self.gui.voice_vars:
            self.gui.voice_vars[vid] = tk.BooleanVar(value=False)

        frame = tk.Frame(parent, bg=self.get_color("bg_card"), cursor="hand2")
        frame.grid(row=row, column=col, sticky="ew", padx=4, pady=3)

        # 체크박스
        is_selected = self.gui.voice_vars[vid].get()
        check_bg = self.get_color("primary") if is_selected else self.get_color("bg_secondary")
        check_text = "✓" if is_selected else ""

        check_lbl = tk.Label(
            frame, text=check_text, font=("맑은 고딕", 8, "bold"),
            bg=check_bg, fg="#FFFFFF", width=2, cursor="hand2"
        )
        check_lbl.pack(side=tk.LEFT, padx=(0, 6))

        # 성별 아이콘
        gender_icon = "♀" if profile.get("gender") == "female" else "♂"
        icon_color = "#FF6B81" if profile.get("gender") == "female" else "#5B9BD5"

        tk.Label(
            frame, text=gender_icon, font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=icon_color
        ).pack(side=tk.LEFT)

        # 이름
        name_lbl = tk.Label(
            frame, text=profile["label"], font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=self.get_color("text_primary"),
            cursor="hand2"
        )
        name_lbl.pack(side=tk.LEFT, padx=(4, 0))

        # 재생 버튼
        play_btn = tk.Label(
            frame, text="▶", font=("맑은 고딕", 8),
            bg=icon_color, fg="#FFFFFF", padx=4, cursor="hand2"
        )
        play_btn.pack(side=tk.RIGHT)
        play_btn.bind("<Button-1>", lambda e, v=vid: self.gui.play_voice_sample(v))

        # 클릭 이벤트
        def toggle(e, voice_id=vid):
            self._toggle_voice(voice_id)

        for w in [frame, check_lbl, name_lbl]:
            w.bind("<Button-1>", toggle)
            w.bind("<MouseWheel>", self._on_mousewheel)

        self.voice_items[vid] = {
            "frame": frame, "check_lbl": check_lbl, "name_lbl": name_lbl,
            "play_btn": play_btn, "profile": profile
        }

    def _toggle_voice(self, voice_id: str) -> None:
        """음성 선택 토글"""
        var = self.gui.voice_vars.get(voice_id)
        if not var:
            return

        new_val = not var.get()

        # 최대 선택 수 체크
        if new_val:
            selected = sum(1 for v in self.gui.voice_vars.values() if v.get())
            max_voices = getattr(self.gui, 'max_voice_selection', 10)
            if selected >= max_voices:
                from ui.components.custom_dialog import show_info
                show_info(self.gui.root, "알림", f"최대 {max_voices}개까지 선택 가능합니다.")
                return

        var.set(new_val)
        self._update_voice_item_style(voice_id)
        self._update_voice_count()

        voice_manager = getattr(self.gui, 'voice_manager', None)
        if voice_manager is not None:
            save_fn = getattr(voice_manager, 'save_voice_selections', None)
            if save_fn is not None:
                save_fn()

    def _update_voice_item_style(self, voice_id: str) -> None:
        """음성 항목 스타일 업데이트"""
        if voice_id not in self.voice_items:
            return

        item = self.voice_items[voice_id]
        is_selected = self.gui.voice_vars.get(voice_id, tk.BooleanVar()).get()

        check_bg = self.get_color("primary") if is_selected else self.get_color("bg_secondary")
        check_text = "✓" if is_selected else ""

        item["check_lbl"].configure(bg=check_bg, text=check_text)

    def _update_voice_count(self) -> None:
        """선택된 음성 수 업데이트"""
        count = sum(1 for v in self.gui.voice_vars.values() if v.get())
        bg = self.get_color("primary") if count > 0 else self.get_color("error")
        self.voice_count_label.configure(text=f"{count}개 선택", bg=bg)

    def _select_all_voices(self) -> None:
        """전체 선택"""
        max_voices = getattr(self.gui, 'max_voice_selection', 10)
        count = 0
        for vid, var in self.gui.voice_vars.items():
            if count >= max_voices:
                break
            var.set(True)
            self._update_voice_item_style(vid)
            count += 1
        self._update_voice_count()

    def _deselect_all_voices(self) -> None:
        """전체 해제"""
        for vid, var in self.gui.voice_vars.items():
            var.set(False)
            self._update_voice_item_style(vid)
        self._update_voice_count()

    # ===== 폰트 섹션 =====
    def _create_font_section(self) -> None:
        """폰트 선택 섹션 (2열 그리드)"""
        section = self._create_section_frame("폰트 선택")

        self.font_selected_label = tk.Label(
            section.header_frame, text="", font=("맑은 고딕", 9),
            bg=self.get_color("primary"), fg="#FFFFFF", padx=6, pady=2
        )
        self.font_selected_label.pack(side=tk.RIGHT)

        project_fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fonts")

        font_options = [
            # 기존 5개
            {"name": "서울 한강체", "id": "seoul_hangang", "path": os.path.join(project_fonts_dir, "SeoulHangangB.ttf")},
            {"name": "프리텐다드", "id": "pretendard", "path": os.path.join(project_fonts_dir, "Pretendard-ExtraBold.ttf")},
            {"name": "G마켓 산스", "id": "gmarketsans", "path": os.path.join(project_fonts_dir, "GmarketSansTTFBold.ttf")},
            {"name": "페이퍼로지", "id": "paperlogy", "path": os.path.join(project_fonts_dir, "Paperlogy-9Black.ttf")},
            {"name": "유앤피플", "id": "unpeople_gothic", "path": os.path.join(project_fonts_dir, "UnPeople.ttf")},
            # 추가 5개 (상업용 무료)
            {"name": "나눔스퀘어", "id": "nanum_square", "path": os.path.join(project_fonts_dir, "NanumSquareEB.ttf")},
            {"name": "카페24 써라운드", "id": "cafe24_surround", "path": os.path.join(project_fonts_dir, "Cafe24Ssurround.ttf")},
            {"name": "스포카 한 산스", "id": "spoqa_han_sans", "path": os.path.join(project_fonts_dir, "SpoqaHanSansNeo-Bold.ttf")},
            {"name": "IBM Plex Sans KR", "id": "ibm_plex", "path": os.path.join(project_fonts_dir, "IBMPlexSansKR-Bold.ttf")},
            {"name": "코펍바탕", "id": "kopub_batang", "path": os.path.join(project_fonts_dir, "KoPubBatangBold.ttf")},
        ]

        # 2열 그리드 레이아웃
        grid_frame = tk.Frame(section.content, bg=self.get_color("bg_card"))
        grid_frame.pack(fill=tk.X)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        for i, opt in enumerate(font_options):
            row, col = i // 2, i % 2
            self._create_font_item(grid_frame, opt, row, col)

    def _create_font_item(self, parent, option: dict, row: int, col: int) -> None:
        """폰트 항목 생성 (2열 그리드)"""
        fid = option["id"]
        font_exists = os.path.exists(option["path"])

        frame = tk.Frame(
            parent, bg=self.get_color("bg_card"),
            cursor="hand2" if font_exists else "arrow"
        )
        frame.grid(row=row, column=col, sticky="ew", padx=4, pady=3)

        # 라디오 인디케이터
        is_selected = getattr(self.gui, 'selected_font_id', 'seoul_hangang') == fid
        radio_text = "●" if is_selected else "○" if font_exists else "✕"
        radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")

        radio_lbl = tk.Label(
            frame, text=radio_text, font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=radio_fg,
            cursor="hand2" if font_exists else "arrow"
        )
        radio_lbl.pack(side=tk.LEFT, padx=(0, 6))

        # 폰트 이름
        name_text = option["name"] if font_exists else f"{option['name']} (없음)"
        name_fg = self.get_color("text_primary") if font_exists else self.get_color("text_disabled")

        name_lbl = tk.Label(
            frame, text=name_text, font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=name_fg,
            cursor="hand2" if font_exists else "arrow"
        )
        name_lbl.pack(side=tk.LEFT)

        if font_exists:
            def select(e, font_id=fid):
                self._select_font(font_id)

            for w in [frame, radio_lbl, name_lbl]:
                w.bind("<Button-1>", select)
                w.bind("<MouseWheel>", self._on_mousewheel)

        self.font_items[fid] = {
            "frame": frame, "radio_lbl": radio_lbl, "name_lbl": name_lbl,
            "font_exists": font_exists, "option": option
        }

    def _select_font(self, font_id: str) -> None:
        """폰트 선택"""
        self.gui.selected_font_id = font_id
        get_settings_manager().set_font_id(font_id)

        for fid, item in self.font_items.items():
            is_selected = fid == font_id
            radio_text = "●" if is_selected else "○" if item["font_exists"] else "✕"
            radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")
            item["radio_lbl"].configure(text=radio_text, fg=radio_fg)

        self._update_font_selected_label()

    def _update_font_selected_label(self) -> None:
        """선택된 폰트 라벨 업데이트"""
        fid = getattr(self.gui, 'selected_font_id', 'seoul_hangang')
        name = "선택 안됨"
        for item in self.font_items.values():
            if item["option"]["id"] == fid:
                name = item["option"]["name"]
                break
        self.font_selected_label.configure(text=name)

    # ===== CTA 섹션 =====
    def _create_cta_section(self) -> None:
        """CTA 선택 섹션 (2열 그리드)"""
        section = self._create_section_frame("CTA 선택")

        self.cta_selected_label = tk.Label(
            section.header_frame, text="", font=("맑은 고딕", 9),
            bg=self.get_color("primary"), fg="#FFFFFF", padx=6, pady=2
        )
        self.cta_selected_label.pack(side=tk.RIGHT)

        # 2열 그리드 레이아웃
        grid_frame = tk.Frame(section.content, bg=self.get_color("bg_card"))
        grid_frame.pack(fill=tk.X)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        for i, opt in enumerate(CTA_OPTIONS):
            row, col = i // 2, i % 2
            self._create_cta_item(grid_frame, opt, row, col)

    def _create_cta_item(self, parent, option: dict, row: int, col: int) -> None:
        """CTA 항목 생성 (2열 그리드)"""
        cid = option["id"]

        frame = tk.Frame(parent, bg=self.get_color("bg_card"), cursor="hand2")
        frame.grid(row=row, column=col, sticky="ew", padx=4, pady=3)

        is_selected = getattr(self.gui, 'selected_cta_id', 'default') == cid
        radio_text = "●" if is_selected else "○"
        radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")

        radio_lbl = tk.Label(
            frame, text=radio_text, font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=radio_fg, cursor="hand2"
        )
        radio_lbl.pack(side=tk.LEFT, padx=(0, 6))

        # CTA 이름
        name_lbl = tk.Label(
            frame, text=option["name"], font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=self.get_color("text_primary"),
            cursor="hand2"
        )
        name_lbl.pack(side=tk.LEFT)

        def select(e, cta_id=cid):
            self._select_cta(cta_id)

        for w in [frame, radio_lbl, name_lbl]:
            w.bind("<Button-1>", select)
            w.bind("<MouseWheel>", self._on_mousewheel)

        self.cta_items[cid] = {
            "frame": frame, "radio_lbl": radio_lbl, "name_lbl": name_lbl,
            "option": option
        }

    def _select_cta(self, cta_id: str) -> None:
        """CTA 선택"""
        self.gui.selected_cta_id = cta_id
        get_settings_manager().set_cta_id(cta_id)

        for cid, item in self.cta_items.items():
            is_selected = cid == cta_id
            radio_text = "●" if is_selected else "○"
            radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")
            item["radio_lbl"].configure(text=radio_text, fg=radio_fg)

        self._update_cta_selected_label()

    def _update_cta_selected_label(self) -> None:
        """선택된 CTA 라벨 업데이트"""
        cid = getattr(self.gui, 'selected_cta_id', 'default')
        name = "선택 안됨"
        for opt in CTA_OPTIONS:
            if opt["id"] == cid:
                name = opt["name"]
                break
        self.cta_selected_label.configure(text=name)

    # ===== 워터마크 섹션 =====
    def _create_watermark_section(self) -> None:
        """워터마크 설정 섹션"""
        section = self._create_section_frame("워터마크")

        # 상태 라벨
        self.watermark_status_label = tk.Label(
            section.header_frame, text="비활성", font=("맑은 고딕", 9),
            bg=self.get_color("text_secondary"), fg="#FFFFFF", padx=6, pady=2
        )
        self.watermark_status_label.pack(side=tk.RIGHT)

        # 활성화 체크박스
        enable_frame = tk.Frame(section.content, bg=self.get_color("bg_card"))
        enable_frame.pack(fill=tk.X, pady=(0, 8))

        self.watermark_enabled_var = tk.BooleanVar(value=False)
        self.watermark_check_lbl = tk.Label(
            enable_frame, text="", font=("맑은 고딕", 8, "bold"),
            bg=self.get_color("bg_secondary"), fg="#FFFFFF", width=2, cursor="hand2"
        )
        self.watermark_check_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self.watermark_enable_label = tk.Label(
            enable_frame, text="워터마크 사용", font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=self.get_color("text_primary"), cursor="hand2"
        )
        self.watermark_enable_label.pack(side=tk.LEFT)

        for w in [self.watermark_check_lbl, self.watermark_enable_label]:
            w.bind("<Button-1>", lambda e: self._toggle_watermark_enabled())
            w.bind("<MouseWheel>", self._on_mousewheel)

        # 채널 이름 입력
        name_frame = tk.Frame(section.content, bg=self.get_color("bg_card"))
        name_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            name_frame, text="채널 이름:", font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=self.get_color("text_primary")
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.watermark_name_entry = tk.Entry(
            name_frame, font=("맑은 고딕", 10), width=20,
            bg=self.get_color("bg_secondary"), fg=self.get_color("text_primary"),
            insertbackground=self.get_color("text_primary"),
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=self.get_color("border_light"),
            highlightcolor=self.get_color("primary")
        )
        self.watermark_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.watermark_name_entry.bind("<KeyRelease>", lambda e: self._on_watermark_name_change())
        self.watermark_name_entry.bind("<MouseWheel>", self._on_mousewheel)

        # 위치 선택 라벨
        tk.Label(
            section.content, text="위치 선택:", font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=self.get_color("text_primary")
        ).pack(anchor=tk.W, pady=(0, 4))

        # 위치 선택 (2x2 그리드)
        position_grid = tk.Frame(section.content, bg=self.get_color("bg_card"))
        position_grid.pack(fill=tk.X)
        position_grid.columnconfigure(0, weight=1)
        position_grid.columnconfigure(1, weight=1)

        position_options = [
            {"id": "top_left", "name": "좌측 상단", "row": 0, "col": 0},
            {"id": "top_right", "name": "우측 상단", "row": 0, "col": 1},
            {"id": "bottom_left", "name": "좌측 하단", "row": 1, "col": 0},
            {"id": "bottom_right", "name": "우측 하단", "row": 1, "col": 1},
        ]

        for opt in position_options:
            self._create_watermark_position_item(position_grid, opt)

    def _create_watermark_position_item(self, parent, option: dict) -> None:
        """워터마크 위치 항목 생성"""
        pid = option["id"]

        frame = tk.Frame(parent, bg=self.get_color("bg_card"), cursor="hand2")
        frame.grid(row=option["row"], column=option["col"], sticky="ew", padx=4, pady=3)

        is_selected = getattr(self.gui, 'watermark_position', 'bottom_right') == pid
        radio_text = "●" if is_selected else "○"
        radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")

        radio_lbl = tk.Label(
            frame, text=radio_text, font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=radio_fg, cursor="hand2"
        )
        radio_lbl.pack(side=tk.LEFT, padx=(0, 6))

        name_lbl = tk.Label(
            frame, text=option["name"], font=("맑은 고딕", 10),
            bg=self.get_color("bg_card"), fg=self.get_color("text_primary"), cursor="hand2"
        )
        name_lbl.pack(side=tk.LEFT)

        def select(e, pos_id=pid):
            self._select_watermark_position(pos_id)

        for w in [frame, radio_lbl, name_lbl]:
            w.bind("<Button-1>", select)
            w.bind("<MouseWheel>", self._on_mousewheel)

        self.watermark_position_items[pid] = {
            "frame": frame, "radio_lbl": radio_lbl, "name_lbl": name_lbl, "option": option
        }

    def _toggle_watermark_enabled(self) -> None:
        """워터마크 활성화 토글"""
        new_val = not self.watermark_enabled_var.get()
        self.watermark_enabled_var.set(new_val)
        self.gui.watermark_enabled = new_val
        get_settings_manager().set_watermark_enabled(new_val)
        self._update_watermark_check_style()
        self._update_watermark_status_label()

    def _update_watermark_check_style(self) -> None:
        """워터마크 체크박스 스타일 업데이트"""
        is_enabled = self.watermark_enabled_var.get()
        check_bg = self.get_color("primary") if is_enabled else self.get_color("bg_secondary")
        check_text = "✓" if is_enabled else ""
        self.watermark_check_lbl.configure(bg=check_bg, text=check_text)

    def _update_watermark_status_label(self) -> None:
        """워터마크 상태 라벨 업데이트"""
        is_enabled = self.watermark_enabled_var.get()
        channel_name = self.watermark_name_entry.get().strip()

        if is_enabled and channel_name:
            self.watermark_status_label.configure(text="활성", bg=self.get_color("primary"))
        elif is_enabled:
            self.watermark_status_label.configure(text="이름 필요", bg=self.get_color("warning") if hasattr(self, 'get_color') else "#FFA500")
        else:
            self.watermark_status_label.configure(text="비활성", bg=self.get_color("text_secondary"))

    def _on_watermark_name_change(self) -> None:
        """채널 이름 변경 시"""
        name = self.watermark_name_entry.get().strip()
        self.gui.watermark_channel_name = name
        get_settings_manager().set_watermark_channel_name(name)
        self._update_watermark_status_label()

    def _select_watermark_position(self, position_id: str) -> None:
        """워터마크 위치 선택"""
        self.gui.watermark_position = position_id
        get_settings_manager().set_watermark_position(position_id)

        for pid, item in self.watermark_position_items.items():
            is_selected = pid == position_id
            radio_text = "●" if is_selected else "○"
            radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")
            item["radio_lbl"].configure(text=radio_text, fg=radio_fg)

    # ===== 유틸리티 =====
    def _create_section_frame(self, title: str):
        """섹션 프레임 생성"""
        container = tk.Frame(self.scrollable, bg=self.get_color("bg_card"))
        container.pack(fill=tk.X, padx=16, pady=8)

        # 헤더
        header = tk.Frame(container, bg=self.get_color("bg_card"))
        header.pack(fill=tk.X, padx=12, pady=(12, 8))

        tk.Label(
            header, text=title, font=("맑은 고딕", 12, "bold"),
            bg=self.get_color("bg_card"), fg=self.get_color("text_primary")
        ).pack(side=tk.LEFT)

        # 컨텐츠
        content = tk.Frame(container, bg=self.get_color("bg_card"))
        content.pack(fill=tk.X, padx=12, pady=(0, 12))

        container.header_frame = header
        container.content = content
        return container

    def _load_saved_settings(self) -> None:
        """저장된 설정 로드"""
        # 음성 로드
        voice_manager = getattr(self.gui, 'voice_manager', None)
        if voice_manager is not None:
            load_saved_voices = getattr(voice_manager, 'load_saved_voices', None)
            if load_saved_voices is not None:
                load_saved_voices()

        for vid in self.voice_items:
            self._update_voice_item_style(vid)
        self._update_voice_count()

        # 폰트 로드
        if getattr(self.gui, 'selected_font_id', None) is None:
            self.gui.selected_font_id = get_settings_manager().get_font_id()
        self._update_font_selected_label()
        for fid, item in self.font_items.items():
            is_selected = fid == self.gui.selected_font_id
            radio_text = "●" if is_selected else "○" if item["font_exists"] else "✕"
            radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")
            item["radio_lbl"].configure(text=radio_text, fg=radio_fg)

        # CTA 로드
        if getattr(self.gui, 'selected_cta_id', None) is None:
            self.gui.selected_cta_id = get_settings_manager().get_cta_id()
        self._update_cta_selected_label()
        for cid, item in self.cta_items.items():
            is_selected = cid == self.gui.selected_cta_id
            radio_text = "●" if is_selected else "○"
            radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")
            item["radio_lbl"].configure(text=radio_text, fg=radio_fg)

        # 워터마크 로드 (방어적 접근 + 에러 핸들링)
        try:
            watermark_settings = get_settings_manager().get_watermark_settings()
            wm_enabled = watermark_settings.get("enabled", False)
            wm_channel_name = watermark_settings.get("channel_name", "")
            wm_position = watermark_settings.get("position", "bottom_right")
        except Exception as e:
            # 설정 로드 실패 시 기본값 사용
            logger.debug("Failed to load watermark settings, using defaults: %s", e)
            wm_enabled, wm_channel_name, wm_position = False, "", "bottom_right"

        self.gui.watermark_enabled = wm_enabled
        self.gui.watermark_channel_name = wm_channel_name
        self.gui.watermark_position = wm_position

        self.watermark_enabled_var.set(wm_enabled)
        self.watermark_name_entry.delete(0, tk.END)
        self.watermark_name_entry.insert(0, wm_channel_name)
        self._update_watermark_check_style()
        self._update_watermark_status_label()

        for pid, item in self.watermark_position_items.items():
            is_selected = pid == wm_position
            radio_text = "●" if is_selected else "○"
            radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")
            item["radio_lbl"].configure(text=radio_text, fg=radio_fg)

    def apply_theme(self) -> None:
        """테마 적용"""
        super().apply_theme()

        # GUI 색상 변수 업데이트
        if hasattr(self, 'gui') and self.gui:
            tm = self._theme_manager
            self.gui.card_bg = tm.get_color("bg_card")
            self.gui.bg_color = tm.get_color("bg_main")
            self.gui.text_color = tm.get_color("text_primary")
            self.gui.secondary_text = tm.get_color("text_secondary")
            self.gui.border_color = tm.get_color("border_light")
            self.gui.primary_color = tm.get_color("primary")
            self.gui.is_dark_mode = tm.is_dark_mode

        # 캔버스/스크롤 영역
        if hasattr(self, 'canvas'):
            self.canvas.configure(bg=self.get_color("bg_main"))
        if hasattr(self, 'scrollable'):
            self.scrollable.configure(bg=self.get_color("bg_main"))

        # 섹션 프레임들 업데이트
        for child in self.scrollable.winfo_children():
            self._apply_theme_to_frame(child)

        # 각 항목 스타일 업데이트
        for vid in self.voice_items:
            self._update_voice_item_theme(vid)

        for fid in self.font_items:
            self._update_font_item_theme(fid)

        for cid in self.cta_items:
            self._update_cta_item_theme(cid)

        for pid in self.watermark_position_items:
            self._update_watermark_position_theme(pid)

        # 워터마크 위젯 테마 업데이트
        if hasattr(self, 'watermark_check_lbl'):
            self._update_watermark_check_style()
        if hasattr(self, 'watermark_enable_label'):
            self.watermark_enable_label.configure(
                bg=self.get_color("bg_card"), fg=self.get_color("text_primary")
            )
        if hasattr(self, 'watermark_name_entry'):
            self.watermark_name_entry.configure(
                bg=self.get_color("bg_secondary"), fg=self.get_color("text_primary"),
                insertbackground=self.get_color("text_primary"),
                highlightbackground=self.get_color("border_light"),
                highlightcolor=self.get_color("primary")
            )
        if hasattr(self, 'watermark_status_label'):
            self._update_watermark_status_label()

        # 버튼/라벨 업데이트
        if hasattr(self, 'voice_count_label'):
            self._update_voice_count()
        if hasattr(self, 'select_all_btn'):
            self.select_all_btn.configure(bg=self.get_color("bg_card"), fg=self.get_color("primary"))
        if hasattr(self, 'deselect_all_btn'):
            self.deselect_all_btn.configure(bg=self.get_color("bg_card"), fg=self.get_color("text_secondary"))
        if hasattr(self, 'font_selected_label'):
            self._update_font_selected_label()
        if hasattr(self, 'cta_selected_label'):
            self._update_cta_selected_label()

    def _apply_theme_to_frame(self, frame: tk.Frame) -> None:
        """프레임에 테마 적용"""
        try:
            frame.configure(bg=self.get_color("bg_card"))
            for child in frame.winfo_children():
                if isinstance(child, tk.Frame):
                    self._apply_theme_to_frame(child)
                elif isinstance(child, tk.Label):
                    # 특수 라벨 제외
                    if child not in [
                        getattr(self, 'voice_count_label', None),
                        getattr(self, 'font_selected_label', None),
                        getattr(self, 'cta_selected_label', None)
                    ]:
                        child.configure(bg=self.get_color("bg_card"))
        except tk.TclError:
            pass

    def _update_voice_item_theme(self, voice_id: str) -> None:
        """음성 항목 테마 업데이트"""
        if voice_id not in self.voice_items:
            return

        item = self.voice_items[voice_id]
        item["frame"].configure(bg=self.get_color("bg_card"))
        item["name_lbl"].configure(bg=self.get_color("bg_card"), fg=self.get_color("text_primary"))

        is_selected = self.gui.voice_vars.get(voice_id, tk.BooleanVar()).get()
        check_bg = self.get_color("primary") if is_selected else self.get_color("bg_secondary")
        item["check_lbl"].configure(bg=check_bg)

    def _update_font_item_theme(self, font_id: str) -> None:
        """폰트 항목 테마 업데이트"""
        if font_id not in self.font_items:
            return

        item = self.font_items[font_id]
        item["frame"].configure(bg=self.get_color("bg_card"))

        is_selected = getattr(self.gui, 'selected_font_id', 'seoul_hangang') == font_id
        radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")
        item["radio_lbl"].configure(bg=self.get_color("bg_card"), fg=radio_fg)

        name_fg = self.get_color("text_primary") if item["font_exists"] else self.get_color("text_disabled")
        item["name_lbl"].configure(bg=self.get_color("bg_card"), fg=name_fg)

    def _update_cta_item_theme(self, cta_id: str) -> None:
        """CTA 항목 테마 업데이트"""
        if cta_id not in self.cta_items:
            return

        item = self.cta_items[cta_id]
        item["frame"].configure(bg=self.get_color("bg_card"))

        is_selected = getattr(self.gui, 'selected_cta_id', 'default') == cta_id
        radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")
        item["radio_lbl"].configure(bg=self.get_color("bg_card"), fg=radio_fg)
        item["name_lbl"].configure(bg=self.get_color("bg_card"), fg=self.get_color("text_primary"))

    def _update_watermark_position_theme(self, position_id: str) -> None:
        """워터마크 위치 항목 테마 업데이트"""
        if position_id not in self.watermark_position_items:
            return

        item = self.watermark_position_items[position_id]
        item["frame"].configure(bg=self.get_color("bg_card"))

        is_selected = getattr(self.gui, 'watermark_position', 'bottom_right') == position_id
        radio_fg = self.get_color("primary") if is_selected else self.get_color("text_secondary")
        item["radio_lbl"].configure(bg=self.get_color("bg_card"), fg=radio_fg)
        item["name_lbl"].configure(bg=self.get_color("bg_card"), fg=self.get_color("text_primary"))


def get_selected_cta_lines(gui) -> list:
    """선택된 CTA 라인 반환"""
    selected_id = getattr(gui, 'selected_cta_id', 'default')
    for opt in CTA_OPTIONS:
        if opt["id"] == selected_id:
            return opt["lines"]
    return CTA_OPTIONS[0]["lines"]
