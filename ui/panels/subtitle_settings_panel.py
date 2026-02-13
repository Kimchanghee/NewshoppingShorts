"""
Subtitle Settings Panel for PyQt6
자막 위치 설정 패널 - 핸드폰 화면 미리보기 + 드래그 직접 배치
"""
import logging
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QWidget, QPushButton, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor, QPen
from ui.components.base_widget import ThemedMixin
from managers.settings_manager import get_settings_manager
from ui.design_system_v2 import get_design_system, get_color

logger = logging.getLogger(__name__)

SUBTITLE_POSITION_OPTIONS = [
    {"label": "상단 중앙", "id": "top_center"},
    {"label": "중앙", "id": "middle_center"},
    {"label": "하단 중앙", "id": "bottom_center"},
    {"label": "직접 선택", "id": "custom"},
]

# Preset Y percentages (0-100, top to bottom)
PRESET_Y_PERCENT = {
    "top_center": 15.0,
    "middle_center": 45.0,
    "bottom_center": 80.0,
}


class SubtitlePositionPreview(QFrame):
    """Mini phone screen preview showing subtitle position (9:16 aspect ratio)
    Supports drag-to-position in custom mode.
    """
    position_clicked = pyqtSignal(str)
    custom_y_changed = pyqtSignal(float)  # emits Y percent (0-100)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_position = "bottom_center"
        self.custom_y_percent = 80.0  # default custom position
        self.overlay_on_chinese = True
        self._dragging = False
        self.setFixedSize(180, 320)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_position(self, position):
        self.current_position = position
        self.update()

    def set_custom_y(self, y_pct):
        self.custom_y_percent = max(5.0, min(95.0, y_pct))
        self.update()

    def set_overlay_mode(self, overlay):
        self.overlay_on_chinese = overlay
        self.update()

    def _bar_y(self):
        """Calculate actual pixel Y for the subtitle bar based on current mode"""
        w, h = self.width(), self.height()
        bar_h = 18
        margin = 16
        usable_top = margin + 10
        usable_bottom = h - bar_h - margin - 10

        if self.current_position == "custom":
            # Map 5-95% to usable area
            ratio = (self.custom_y_percent - 5.0) / 90.0
            return int(usable_top + ratio * (usable_bottom - usable_top))
        else:
            pct = PRESET_Y_PERCENT.get(self.current_position, 80.0)
            ratio = (pct - 5.0) / 90.0
            return int(usable_top + ratio * (usable_bottom - usable_top))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Phone frame background
        painter.setBrush(QColor(30, 30, 30))
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 8, 8)

        # 9:16 label
        painter.setPen(QColor(80, 80, 80))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "9:16")

        bar_w = int(w * 0.75)
        bar_h = 18
        bar_x = (w - bar_w) // 2
        margin = 16

        if self.overlay_on_chinese:
            # Chinese subtitle indicator
            cn_y = h - bar_h - margin - 20
            painter.setBrush(QColor(255, 200, 50, 60))
            painter.setPen(QPen(QColor(255, 200, 50, 120), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(bar_x - 5, cn_y - 2, bar_w + 10, bar_h + 4, 3, 3)
            painter.setPen(QColor(255, 200, 50, 180))
            painter.setFont(QFont("Arial", 7))
            painter.drawText(bar_x - 5, cn_y - 12, bar_w + 10, 12,
                             Qt.AlignmentFlag.AlignCenter, "CN")

            # Korean subtitle above Chinese
            kr_y = cn_y - bar_h - 8
            painter.setBrush(QColor(227, 22, 57, 200))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_x, kr_y, bar_w, bar_h, 3, 3)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            painter.drawText(bar_x, kr_y, bar_w, bar_h,
                             Qt.AlignmentFlag.AlignCenter, "한국어 자막")
        else:
            # Preset ghost slots (only show when not in custom mode)
            if self.current_position != "custom":
                usable_top = margin + 10
                usable_bottom = h - bar_h - margin - 10
                for pos_id, pct in PRESET_Y_PERCENT.items():
                    ratio = (pct - 5.0) / 90.0
                    slot_y = int(usable_top + ratio * (usable_bottom - usable_top))
                    if pos_id != self.current_position:
                        painter.setBrush(QColor(80, 80, 80, 60))
                        painter.setPen(QPen(QColor(100, 100, 100, 80), 1, Qt.PenStyle.DashLine))
                        painter.drawRoundedRect(bar_x, slot_y, bar_w, bar_h, 3, 3)

            # Active subtitle bar
            bar_y = self._bar_y()
            painter.setBrush(QColor(227, 22, 57, 200))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            painter.drawText(bar_x, bar_y, bar_w, bar_h,
                             Qt.AlignmentFlag.AlignCenter, "한국어 자막")

            # In custom mode, show drag hint and Y% label
            if self.current_position == "custom":
                # Y percentage label
                painter.setPen(QColor(200, 200, 200, 180))
                painter.setFont(QFont("Arial", 8))
                pct_text = f"{self.custom_y_percent:.0f}%"
                painter.drawText(bar_x + bar_w + 4, bar_y, 30, bar_h,
                                 Qt.AlignmentFlag.AlignVCenter, pct_text)

                # Drag arrows
                if not self._dragging:
                    arrow_x = w // 2
                    painter.setPen(QColor(150, 150, 150, 120))
                    painter.setFont(QFont("Arial", 10))
                    painter.drawText(arrow_x - 5, bar_y - 16, 10, 14,
                                     Qt.AlignmentFlag.AlignCenter, "▲")
                    painter.drawText(arrow_x - 5, bar_y + bar_h + 2, 10, 14,
                                     Qt.AlignmentFlag.AlignCenter, "▼")

        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.overlay_on_chinese:
            return
        if self.current_position == "custom":
            self._dragging = True
            self._handle_drag(event.position().y())
        else:
            # Click to select preset
            y = event.position().y()
            h = self.height()
            third = h / 3
            if y < third:
                pos = "top_center"
            elif y < third * 2:
                pos = "middle_center"
            else:
                pos = "bottom_center"
            self.position_clicked.emit(pos)

    def mouseMoveEvent(self, event):
        if self._dragging and self.current_position == "custom":
            self._handle_drag(event.position().y())

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self.update()

    def _handle_drag(self, mouse_y):
        """Convert mouse Y position to subtitle Y percentage"""
        bar_h = 18
        margin = 16
        usable_top = margin + 10
        usable_bottom = self.height() - bar_h - margin - 10
        usable_range = usable_bottom - usable_top

        if usable_range <= 0:
            return

        ratio = (mouse_y - usable_top) / usable_range
        ratio = max(0.0, min(1.0, ratio))
        y_pct = 5.0 + ratio * 90.0  # Map to 5-95%

        self.custom_y_percent = round(y_pct, 1)
        self.update()
        self.custom_y_changed.emit(self.custom_y_percent)


class SubtitleSettingsPanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.position_buttons = {}
        self.__init_themed__(theme_manager)
        self._loading = True
        self.create_widgets()
        self._load_settings()
        self._loading = False
        self.apply_theme()

    def create_widgets(self):
        ds = self.ds

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(ds.spacing.space_4, ds.spacing.space_3, ds.spacing.space_4, ds.spacing.space_3)
        main_layout.setSpacing(ds.spacing.space_3)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll = scroll

        scroll_content = QWidget()
        self.scroll_content = scroll_content
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setSpacing(ds.spacing.space_4)

        # ── Section 1: Overlay on Chinese subtitle ──
        overlay_section = self._create_section(
            "중국어 자막 위 배치",
            "한국어 자막을 중국어 자막 바로 위에 배치합니다."
        )

        self.overlay_checkbox = QCheckBox("중국어 자막 위에 한국어 자막 배치")
        self.overlay_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overlay_checkbox.stateChanged.connect(self._on_overlay_changed)
        overlay_section.layout().addWidget(self.overlay_checkbox)

        content_layout.addWidget(overlay_section)

        # ── Section 2: Manual position selection ──
        self.position_section, self.pos_title_label, self.pos_desc_label = self._create_section(
            "자막 위치 선택",
            "한국어 자막이 표시될 위치를 선택하세요. '직접 선택' 시 프리뷰를 드래그하여 배치할 수 있습니다.",
            return_labels=True
        )

        pos_content = QHBoxLayout()
        pos_content.setSpacing(ds.spacing.space_4)

        # Position buttons column
        pos_btn_layout = QVBoxLayout()
        pos_btn_layout.setSpacing(ds.spacing.space_2)

        for opt in SUBTITLE_POSITION_OPTIONS:
            btn = QPushButton(opt["label"])
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setMinimumWidth(100)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, pid=opt["id"]: self._on_position_selected(pid))
            pos_btn_layout.addWidget(btn)
            self.position_buttons[opt["id"]] = btn

        # Custom Y value label (shown only in custom mode)
        self.custom_y_label = QLabel("")
        self.custom_y_label.setStyleSheet("font-size: 12px; color: #B8B8B8;")
        self.custom_y_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.custom_y_label.setVisible(False)
        pos_btn_layout.addWidget(self.custom_y_label)

        pos_btn_layout.addStretch()
        pos_content.addLayout(pos_btn_layout)

        # Phone preview
        self.position_preview = SubtitlePositionPreview()
        self.position_preview.position_clicked.connect(self._on_position_selected)
        self.position_preview.custom_y_changed.connect(self._on_custom_y_changed)
        pos_content.addWidget(self.position_preview)

        self.position_section.layout().addLayout(pos_content)
        content_layout.addWidget(self.position_section)

        # ── Section 3: Notice ──
        notice_section = QFrame()
        notice_section.setFrameShape(QFrame.Shape.NoFrame)
        notice_layout = QVBoxLayout(notice_section)
        notice_layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_3, ds.spacing.space_3, ds.spacing.space_3)

        self.notice_label = QLabel()
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet(f"""
            font-size: 12px;
            color: #FFB800;
            padding: {ds.spacing.space_2}px {ds.spacing.space_3}px;
            background-color: rgba(255, 184, 0, 0.08);
            border: 1px solid rgba(255, 184, 0, 0.2);
            border-radius: {ds.radius.sm}px;
        """)
        notice_layout.addWidget(self.notice_label)
        content_layout.addWidget(notice_section)

        content_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _create_section(self, title, description, return_labels=False):
        ds = self.ds
        section = QFrame()
        section.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_3, ds.spacing.space_3, ds.spacing.space_3)
        layout.setSpacing(ds.spacing.space_2)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 14px; font-weight: {ds.typography.weight_bold}; color: #FFFFFF;")
        layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setStyleSheet("font-size: 12px; color: #888888;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        if return_labels:
            return section, title_label, desc_label
        return section

    # ── Settings Load ──

    def _load_settings(self):
        sm = get_settings_manager()
        settings = sm.get_subtitle_settings()

        overlay = settings.get("overlay_on_chinese", True)
        position = settings.get("position", "bottom_center")
        custom_y = settings.get("custom_y_percent", 80.0)

        self.overlay_checkbox.setChecked(overlay)
        self.position_preview.set_custom_y(custom_y)
        self._update_position_selection(position)
        self._update_ui_state(overlay)

        # Set gui attributes
        self.gui.subtitle_overlay_on_chinese = overlay
        self.gui.subtitle_position = position
        self.gui.subtitle_custom_y_percent = custom_y

        logger.info("[자막 설정] 로드 완료: overlay=%s, position=%s, custom_y=%.1f%%",
                    overlay, position, custom_y)

    # ── Event Handlers ──

    def _on_overlay_changed(self, state):
        overlay = state == Qt.CheckState.Checked.value
        self._update_ui_state(overlay)

        if self._loading:
            return

        self.gui.subtitle_overlay_on_chinese = overlay
        get_settings_manager().set_subtitle_overlay_on_chinese(overlay)
        logger.info("[자막 설정] 중국어 위 배치: %s", overlay)

    def _update_ui_state(self, overlay):
        """Enable/disable position section based on overlay checkbox"""
        ds = self.ds

        # 프리뷰 오버레이 모드 동기화
        self.position_preview.set_overlay_mode(overlay)

        # 체크 시 위치 선택 비활성화 (회색 처리), 체크 해제 시 활성화
        self.position_section.setEnabled(not overlay)
        self.position_preview.setEnabled(not overlay)

        if overlay:
            # 비활성화: 모든 버튼 회색 처리
            for btn in self.position_buttons.values():
                btn.setEnabled(False)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('surface_variant')};
                        color: #555555;
                        border: 1px solid {get_color('border_light')};
                        border-radius: {ds.radius.sm}px;
                        font-size: 12px;
                    }}
                """)
            # 섹션 타이틀/설명 회색 처리
            self.pos_title_label.setStyleSheet(f"font-size: 14px; font-weight: {ds.typography.weight_bold}; color: #555555;")
            self.pos_desc_label.setStyleSheet("font-size: 12px; color: #444444;")
        else:
            # 활성화: 버튼 원래 스타일 복원
            for btn in self.position_buttons.values():
                btn.setEnabled(True)
            self._update_position_selection(self.position_preview.current_position)
            # 섹션 타이틀/설명 원래 색상
            self.pos_title_label.setStyleSheet(f"font-size: 14px; font-weight: {ds.typography.weight_bold}; color: #FFFFFF;")
            self.pos_desc_label.setStyleSheet("font-size: 12px; color: #888888;")

        is_custom = self.position_preview.current_position == "custom"
        self.custom_y_label.setVisible(not overlay and is_custom)
        if is_custom:
            self.custom_y_label.setText(f"위치: {self.position_preview.custom_y_percent:.0f}%")

        if overlay:
            self.notice_label.setText(
                "※ 중국어 자막이 감지되면 한국어 자막을 중국어 자막 바로 위에 배치합니다.\n"
                "※ 중국어 자막이 없는 영상의 경우, 현재 설정된 위치에 자막이 표시됩니다."
            )
        else:
            pos_name = self._get_position_name()
            self.notice_label.setText(
                f"※ 중국어 자막이 없는 영상에서는 '{pos_name}' 위치에 자막이 표시됩니다.\n"
                "※ 중국어 자막이 있는 영상에서도 선택한 위치에 자막이 고정됩니다."
            )

    def _get_position_name(self):
        pos = self.position_preview.current_position
        if pos == "custom":
            return f"직접 선택 ({self.position_preview.custom_y_percent:.0f}%)"
        for opt in SUBTITLE_POSITION_OPTIONS:
            if opt["id"] == pos:
                return opt["label"]
        return "하단 중앙"

    def _on_position_selected(self, position_id):
        self._update_position_selection(position_id)
        if self._loading:
            return
        self.gui.subtitle_position = position_id
        get_settings_manager().set_subtitle_position(position_id)
        self._update_ui_state(self.overlay_checkbox.isChecked())
        logger.info("[자막 설정] 위치 변경: %s", position_id)

    def _on_custom_y_changed(self, y_pct):
        """Called when user drags subtitle position in custom mode"""
        self.custom_y_label.setText(f"위치: {y_pct:.0f}%")

        if self._loading:
            return

        self.gui.subtitle_custom_y_percent = y_pct
        get_settings_manager().set_subtitle_custom_y(y_pct)
        self._update_ui_state(self.overlay_checkbox.isChecked())

    def _update_position_selection(self, selected_id):
        ds = self.ds
        is_custom = selected_id == "custom"

        for pid, btn in self.position_buttons.items():
            is_sel = (pid == selected_id)
            btn.setChecked(is_sel)
            if is_sel:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('primary')};
                        color: white;
                        border: none;
                        border-radius: {ds.radius.sm}px;
                        font-weight: bold;
                        font-size: 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('surface_variant')};
                        color: {get_color('text_secondary')};
                        border: 1px solid {get_color('border_light')};
                        border-radius: {ds.radius.sm}px;
                        font-size: 12px;
                    }}
                """)

        self.position_preview.set_position(selected_id)
        self.custom_y_label.setVisible(is_custom)
        if is_custom:
            self.custom_y_label.setText(f"위치: {self.position_preview.custom_y_percent:.0f}%")

    def apply_theme(self):
        ds = self.ds
        bg = get_color('surface')
        self.setStyleSheet(f"background-color: {bg}; border: none;")
        self.scroll.setStyleSheet(f"background-color: {bg};")
        self.scroll_content.setStyleSheet(f"background-color: {bg};")

        # Checkbox styling
        primary = get_color('primary')
        self.overlay_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: #FFFFFF;
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {get_color('border_light')};
                border-radius: 4px;
                background-color: {get_color('surface_variant')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {primary};
                border-color: {primary};
            }}
        """)
