"""
VoiceManager (PyQt6-safe)

Replaces legacy BooleanVar usage with a lightweight SimpleBoolVar
to keep existing logic without Tk dependencies.
"""

from __future__ import annotations

import os
import threading
import tempfile
import wave
import hashlib
from typing import Any, Dict, List, Optional
from caller import ui_controller
from managers.settings_manager import get_settings_manager
from ui.components.custom_dialog import show_info, show_warning, show_error
from utils.logging_config import get_logger

logger = get_logger(__name__)

try:
    import winsound
except ImportError:
    winsound = None

try:
    import simpleaudio
except ImportError:
    simpleaudio = None

try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None

try:
    from google import genai
    from google.genai import types
    GENAI_SDK_AVAILABLE = True
    GENAI_TYPES_AVAILABLE = True
except Exception as e:
    genai = None
    types = None
    GENAI_SDK_AVAILABLE = False
    GENAI_TYPES_AVAILABLE = False

import config

NORMAL = "normal"
DISABLED = "disabled"


class SimpleBoolVar:
    def __init__(self, value: bool = False):
        self._value = bool(value)

    def get(self) -> bool:
        return self._value

    def set(self, value: bool):
        self._value = bool(value)


class VoiceManager:
    """Manager class for handling all voice-related operations."""

    def __init__(self, gui):
        self.gui = gui
        # Normalize voice_vars into SimpleBoolVar instances for compatibility
        raw_vars = getattr(self.gui, "voice_vars", {})
        self.gui.voice_vars = {
            vid: SimpleBoolVar(var.get() if hasattr(var, "get") else var)
            for vid, var in raw_vars.items()
        }

    # --------- selection persistence ---------
    def _save_selected_voices(self, voice_ids: List[str]) -> None:
        try:
            get_settings_manager().set_selected_voices(voice_ids)
        except Exception as e:
            logger.error("[VoiceManager] 선택 저장 실패: %s", e)

    def save_voice_selections(self) -> None:
        selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
        self._save_selected_voices(selected_ids)

        selected_profiles = [self.get_voice_profile(vid) for vid in selected_ids]
        selected_profiles = [p for p in selected_profiles if p]
        if selected_profiles:
            self.gui.multi_voice_presets = [p["voice_name"] for p in selected_profiles]
            self.gui.available_tts_voices = list(self.gui.multi_voice_presets)
        else:
            self.gui.multi_voice_presets = []
            self.gui.available_tts_voices = []

    def load_saved_voices(self) -> None:
        try:
            saved_voice_ids = get_settings_manager().get_selected_voices()
            if not saved_voice_ids:
                if self.gui.voice_profiles:
                    default_id = self.gui.voice_profiles[0]["id"]
                    saved_voice_ids = [default_id]
                else:
                    for voice_id, var in self.gui.voice_vars.items():
                        var.set(False)
                    self.gui.multi_voice_presets = []
                    self.gui.available_tts_voices = []
                    logger.info("[VoiceManager] 저장된 선택 없음 -> 초기화")
                    return

            max_voices = getattr(self.gui, "max_voice_selection", 10)
            if len(saved_voice_ids) > max_voices:
                logger.warning("[VoiceManager] 저장된 선택(%d)이 최대(%d)보다 많음. 앞 %d개만 사용", len(saved_voice_ids), max_voices, max_voices)
                saved_voice_ids = saved_voice_ids[:max_voices]

            for voice_id, var in self.gui.voice_vars.items():
                var.set(False)
            for voice_id in saved_voice_ids:
                if voice_id in self.gui.voice_vars:
                    self.gui.voice_vars[voice_id].set(True)

            selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
            selected_profiles = [self.get_voice_profile(vid) for vid in selected_ids]
            selected_profiles = [p for p in selected_profiles if p]

            if selected_profiles:
                self.gui.multi_voice_presets = [p["voice_name"] for p in selected_profiles]
                self.gui.available_tts_voices = list(self.gui.multi_voice_presets)
            else:
                self.gui.multi_voice_presets = []
                self.gui.available_tts_voices = []

        except Exception as e:
            logger.error("[VoiceManager] 저장된 선택 로드 실패: %s", e)

    # --------- helpers ---------
    def get_voice_profile(self, voice_id: str) -> Optional[Dict[str, Any]]:
        for profile in self.gui.voice_profiles:
            if profile.get("id") == voice_id:
                return profile
            if profile.get("voice_name") == voice_id:
                return profile
        return None

    def get_voice_label(self, voice_id: str) -> str:
        if not voice_id:
            return "선택 없음"
        profile = self.get_voice_profile(voice_id)
        if profile:
            return profile.get("label", voice_id)
        return voice_id

    # --------- UI interactions ---------
    def on_voice_card_clicked(self, voice_id: str):
        var = self.gui.voice_vars.get(voice_id, SimpleBoolVar(False))
        new_state = not var.get()
        var.set(new_state)
        self.gui.voice_vars[voice_id] = var

        selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
        selected_profiles = [self.get_voice_profile(vid) for vid in selected_ids]
        selected_profiles = [p for p in selected_profiles if p]

        if selected_profiles:
            self.gui.multi_voice_presets = [p["voice_name"] for p in selected_profiles]
            self.gui.available_tts_voices = list(self.gui.multi_voice_presets)
        else:
            self.gui.multi_voice_presets = []
            self.gui.available_tts_voices = []

        if hasattr(self.gui, "voice_panel"):
            try:
                self.gui.voice_panel.rebuild_grid()
            except Exception:
                pass

        self._save_selected_voices(selected_ids)

    # --------- sample playback ---------
    def play_voice_sample(self, voice_id: str):
        """Stub for playback; rewire to existing sample paths if available."""
        profile = self.get_voice_profile(voice_id)
        if not profile:
            show_warning(self.gui, "안내", "해당 음성을 찾을 수 없습니다.")
            return
        path = getattr(self.gui, "voice_sample_paths", {}).get(voice_id)
        if not path or not os.path.exists(path):
            show_info(self.gui, "안내", "샘플이 없습니다.")
            return
        try:
            if winsound:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif simpleaudio:
                wave_obj = simpleaudio.WaveObject.from_wave_file(path)
                wave_obj.play()
            else:
                show_info(self.gui, "안내", "재생 모듈이 없습니다.")
        except Exception as exc:
            logger.error("[VoiceManager] 샘플 재생 실패: %s", exc)
            show_error(self.gui, "재생 오류", str(exc))

    # --------- utility placeholders ---------
    def ensure_voice_vars(self):
        """Make sure all profiles have a SimpleBoolVar state."""
        for profile in self.gui.voice_profiles:
            vid = profile.get("id")
            if vid not in self.gui.voice_vars:
                self.gui.voice_vars[vid] = SimpleBoolVar(False)
