from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QScrollArea

from config.font_catalog import FONT_IDS, ui_font_options
from config.voice_profiles import VOICE_PROFILES
from ui.components.step_nav import StepNav
from ui.panels.cta_panel import CTA_OPTIONS, get_selected_cta_lines
from ui.panels.cta_panel import CTAPanel
from ui.panels.mode_selection_panel import ModeSelectionPanel
from ui.panels.voice_panel import VoicePanel
from ui.panels.watermark_panel import WATERMARK_FONT_OPTIONS


ROOT = Path(__file__).resolve().parents[2]


def test_review_cta_option_removed_and_stale_selection_falls_back():
    assert all(option["id"] != "option7" for option in CTA_OPTIONS)
    assert all(option["name"] != "후기형" for option in CTA_OPTIONS)

    class DummyGui:
        selected_cta_id = "option7"

    assert get_selected_cta_lines(DummyGui()) == CTA_OPTIONS[0]["lines"]


def test_voice_profiles_include_ten_female_and_ten_male_gemini_voices():
    ids = [profile["id"] for profile in VOICE_PROFILES]
    voice_names = {profile["voice_name"] for profile in VOICE_PROFILES}

    assert len(ids) == len(set(ids)) == 20
    assert sum(profile["gender"] == "female" for profile in VOICE_PROFILES) == 10
    assert sum(profile["gender"] == "male" for profile in VOICE_PROFILES) == 10
    assert {
        "Despina",
        "Sulafat",
        "Vindemiatrix",
        "Leda",
        "Erinome",
        "Enceladus",
        "Iapetus",
        "Umbriel",
        "Gacrux",
        "Sadaltager",
    }.issubset(voice_names)

    sample_dir = ROOT / "resource/voice_samples"
    for voice_id in ids:
        sample_path = sample_dir / f"{voice_id}.wav"
        assert sample_path.exists(), f"missing voice sample: {sample_path.name}"
        assert sample_path.stat().st_size > 100_000


def test_font_choices_share_one_catalog_across_ui_and_renderer():
    assert tuple(option["id"] for option in ui_font_options()) == FONT_IDS
    assert tuple(option["id"] for option in WATERMARK_FONT_OPTIONS) == FONT_IDS

    font_panel_source = (ROOT / "ui/panels/font_panel.py").read_text(encoding="utf-8")
    style_tab_source = (ROOT / "ui/panels/style_tab.py").read_text(encoding="utf-8")
    video_tool_source = (ROOT / "core/video/VideoTool.py").read_text(encoding="utf-8")
    settings_source = (ROOT / "managers/settings_manager.py").read_text(encoding="utf-8")

    assert "ui_font_options" in font_panel_source
    assert "ui_font_options" in style_tab_source
    assert "font_candidate_paths" in video_tool_source
    assert "normalize_font_id" in settings_source
    assert "font_id_map" not in video_tool_source


def test_selection_panels_adapt_without_icon_text_overlap():
    app = QApplication.instance() or QApplication([])

    steps = [
        ("mode", "만들기 방식", "mode"),
        ("source", "영상 넣기", "source"),
        ("voice", "목소리 선택", "voice"),
        ("cta", "마무리 멘트", "cta"),
        ("font", "글씨체 선택", "font"),
        ("subtitle_settings", "자막 설정", "subtitle_settings"),
        ("watermark", "워터마크", "watermark"),
        ("queue", "진행 상황", "queue"),
        ("settings", "설정", "settings"),
    ]
    nav = StepNav(steps)
    nav.resize(280, 520)
    nav.show()
    app.processEvents()

    for step_id, button in nav._buttons.items():
        icon = button.icon_label.geometry()
        text = button.text_label.geometry()
        assert not icon.intersects(text), step_id
        assert text.x() > icon.right(), step_id

    class Var:
        def __init__(self, value=False):
            self.value = value

        def get(self):
            return self.value

    class DummyGui:
        def __init__(self):
            self.voice_profiles = VOICE_PROFILES
            self.voice_vars = {profile["id"]: Var(False) for profile in VOICE_PROFILES}
            self.selected_cta_id = "default"

        def play_voice_sample(self, voice_id):
            return None

    gui = DummyGui()
    mode_panel = ModeSelectionPanel(None, gui)
    voice_panel = VoicePanel(None, gui)
    cta_panel = CTAPanel(None, gui)

    mode_panel.resize(1128, 550)
    mode_panel.show()
    app.processEvents()
    assert mode_panel._card_columns == 3
    for mode_id, card in mode_panel._cards.items():
        icon_box = card.icon_box.geometry()
        title = card.title_label.geometry()
        subtitle = card.subtitle_label.geometry()
        assert icon_box.bottom() < title.top(), mode_id
        assert title.bottom() < subtitle.top(), mode_id

    mode_scroll = QScrollArea()
    mode_scroll.setWidgetResizable(True)
    mode_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    mode_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    compact_mode_panel = ModeSelectionPanel(None, gui)
    mode_scroll.setWidget(compact_mode_panel)
    mode_scroll.resize(780, 430)
    mode_scroll.show()
    app.processEvents()
    assert compact_mode_panel._card_columns == 3
    assert mode_scroll.horizontalScrollBar().maximum() == 0
    assert mode_scroll.verticalScrollBar().maximum() == 0
    for card in compact_mode_panel._cards.values():
        assert card.select_label.geometry().bottom() <= card.contentsRect().bottom()

    for width, expected_voice_columns, expected_cta_columns in (
        (360, 1, 1),
        (620, 2, 3),
        (820, 3, 3),
    ):
        voice_panel.resize(width, 700)
        cta_panel.resize(width, 700)
        voice_panel.show()
        cta_panel.show()
        app.processEvents()

        assert voice_panel._column_count() == expected_voice_columns
        assert cta_panel._column_count() == expected_cta_columns

    nav.close()
    mode_panel.close()
    mode_scroll.close()
    voice_panel.close()
    cta_panel.close()
