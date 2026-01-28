"""
VoiceManager - Manages all voice-related functionality for the video analyzer GUI.

This module handles:
- Voice profile management and selection
- Voice card UI interactions
- Voice sample generation and playback
- TTS voice mode controls
- Voice status displays
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
from utils.logging_config import get_logger

logger = get_logger(__name__)

import tkinter as tk
from ui.components.custom_dialog import show_info, show_warning, show_error

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


class VoiceManager:
    """
    Manager class for handling all voice-related operations.

    This class manages voice profiles, voice selection UI, sample playback,
    and TTS voice mode controls. It requires a reference to the main GUI
    to access shared state and UI elements.
    """

    def __init__(self, gui):
        """
        Initialize the VoiceManager.

        Args:
            gui: Reference to the VideoAnalyzerGUI instance
        """
        self.gui = gui

    def _save_selected_voices(self, voice_ids: List[str]) -> None:
        """Save selected voice IDs to persistent settings."""
        try:
            get_settings_manager().set_selected_voices(voice_ids)
        except Exception as e:
            logger.error("[음성 관리자] 음성 저장 실패: %s", e)

    def save_voice_selections(self) -> None:
        """현재 선택된 음성들을 저장 (voice_panel에서 호출)"""
        selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
        self._save_selected_voices(selected_ids)

        # Update presets
        selected_profiles = [self.get_voice_profile(vid) for vid in selected_ids]
        selected_profiles = [p for p in selected_profiles if p]
        if selected_profiles:
            self.gui.multi_voice_presets = [p["voice_name"] for p in selected_profiles]
            self.gui.available_tts_voices = list(self.gui.multi_voice_presets)
        else:
            self.gui.multi_voice_presets = []
            self.gui.available_tts_voices = []

    def load_saved_voices(self) -> None:
        """Load saved voice selections and apply them to voice_vars."""
        try:
            saved_voice_ids = get_settings_manager().get_selected_voices()
            if not saved_voice_ids:
                # 저장된 음성이 없으면 첫 번째 음성을 기본 선택
                if self.gui.voice_profiles:
                    default_id = self.gui.voice_profiles[0]["id"]
                    saved_voice_ids = [default_id]
                else:
                    # 프로필이 비어 있으면 기존 선택을 모두 초기화
                    for voice_id, var in self.gui.voice_vars.items():
                        var.set(False)
                    self.gui.multi_voice_presets = []
                    self.gui.available_tts_voices = []
                    logger.info("[음성 관리자] 음성 프로필이 비어 있어 모든 선택을 초기화했습니다.")
                    return

            # Enforce max selection limit
            max_voices = getattr(self.gui, 'max_voice_selection', 10)
            if len(saved_voice_ids) > max_voices:
                logger.warning("[음성 관리자] 저장된 음성 수(%d)가 최대 선택 수(%d)를 초과합니다. 처음 %d개만 로드합니다.", len(saved_voice_ids), max_voices, max_voices)
                saved_voice_ids = saved_voice_ids[:max_voices]

            # Clear existing selections first to prevent stale selections
            for voice_id, var in self.gui.voice_vars.items():
                var.set(False)

            # Apply saved selections to voice_vars
            for voice_id in saved_voice_ids:
                if voice_id in self.gui.voice_vars:
                    self.gui.voice_vars[voice_id].set(True)

            # Update multi_voice_presets and available_tts_voices
            selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
            selected_profiles = [self.get_voice_profile(vid) for vid in selected_ids]
            selected_profiles = [p for p in selected_profiles if p]

            if selected_profiles:
                self.gui.multi_voice_presets = [p["voice_name"] for p in selected_profiles]
                self.gui.available_tts_voices = list(self.gui.multi_voice_presets)
            else:
                # Ensure empty lists when no valid profiles
                self.gui.multi_voice_presets = []
                self.gui.available_tts_voices = []

        except Exception as e:
            logger.error("[음성 관리자] 음성 로드 실패: %s", e)

    def get_voice_profile(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Get voice profile by ID or voice_name."""
        for profile in self.gui.voice_profiles:
            # First try matching by ID
            if profile.get("id") == voice_id:
                return profile
            # Also try matching by voice_name (for TTS voice names like "Callirrhoe")
            if profile.get("voice_name") == voice_id:
                return profile
        return None

    def get_voice_label(self, voice_id: str) -> str:
        """음성 ID를 한글 이름으로 변환"""
        if not voice_id:
            return "알 수 없음"

        profile = self.get_voice_profile(voice_id)
        if profile:
            return profile.get('label', voice_id)
        return voice_id

    def on_voice_card_clicked(self, voice_id: str):
        """Handle voice card click to toggle selection."""
        var = self.gui.voice_vars.get(voice_id)
        if var is None:
            return

        # Toggle current selection state
        current_state = var.get()
        new_state = not current_state

        # Check max selection count when selecting
        if new_state:
            selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
            if len(selected_ids) >= self.gui.max_voice_selection:
                show_info(self.gui.root, "알림", f"최대 {self.gui.max_voice_selection}개까지 선택할 수 있습니다.")
                return

        # Update state
        var.set(new_state)

        # Update selected voices
        selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
        selected_profiles = [self.get_voice_profile(vid) for vid in selected_ids]
        selected_profiles = [p for p in selected_profiles if p]

        if selected_profiles:
            self.gui.multi_voice_presets = [p["voice_name"] for p in selected_profiles]
            self.gui.available_tts_voices = list(self.gui.multi_voice_presets)
        else:
            # Set to empty list if no selection
            self.gui.multi_voice_presets = []
            self.gui.available_tts_voices = []

        # Save selected voices to persistent settings
        self._save_selected_voices(selected_ids)

        self.update_voice_summary()
        self.update_voice_card_styles()
        self.refresh_voice_status_display()

    def on_voice_checkbox_toggled(self, voice_id: str):
        """Handle checkbox toggle (kept for backward compatibility)."""
        self.on_voice_card_clicked(voice_id)

    def on_voice_card_hover(self, voice_id: str, is_hovering: bool):
        """Change card style on mouse hover."""
        frame = self.gui.voice_card_frames.get(voice_id)
        if not frame:
            return

        selected = self.gui.voice_vars.get(voice_id, tk.BooleanVar(value=False)).get()

        # Change background color based on hover state
        if is_hovering:
            if selected:
                bg = "#dcd0ff"  # Selected card hover
                border_width = 3
            else:
                bg = "#f5f0ff"  # Unselected card hover
                border_width = 2
        else:
            # Return to original style when hover is released
            if selected:
                bg = "#e8e0ff"
                border_width = 3
            else:
                bg = "#fbf9ff"
                border_width = 2

        frame.configure(bg=bg, highlightthickness=border_width)

        # Update child widget backgrounds
        for child in frame.winfo_children():
            try:
                if isinstance(child, tk.Label):
                    child.configure(bg=bg)
            except tk.TclError:
                pass

    def update_voice_card_styles(self):
        """Update list item styles based on selection state."""
        for voice_id, row_frame in getattr(self.gui, 'voice_card_frames', {}).items():
            selected = self.gui.voice_vars.get(voice_id, tk.BooleanVar(value=False)).get()

            # Update row background for selected items
            if selected:
                bg = "#e8e0ff"  # Highlighted background
            else:
                # Keep zebra striping - check current bg
                current_bg = row_frame.cget("bg")
                bg = current_bg  # Keep original zebra color

            # Update frame and all children
            row_frame.configure(bg=bg)
            for child in row_frame.winfo_children():
                try:
                    if isinstance(child, tk.Label):
                        # Update checkbox icon
                        if child.cget("text") in ["☑", "☐"]:
                            child.configure(
                                text="☑" if selected else "☐",
                                fg=self.gui.accent_color if selected else "#c0c0c0",
                                bg=bg
                            )
                        else:
                            child.configure(bg=bg)
                    elif isinstance(child, tk.Frame):
                        child.configure(bg=bg)
                        # Update frame's children (checkbox frame)
                        for subchild in child.winfo_children():
                            if isinstance(subchild, tk.Label):
                                subchild.configure(
                                    text="☑" if selected else "☐",
                                    fg=self.gui.accent_color if selected else "#c0c0c0",
                                    bg=bg
                                )
                except tk.TclError:
                    pass

            # Update play button style
            button = self.gui.voice_play_buttons.get(voice_id)
            if button:
                button.configure(
                    bg=self.gui.accent_color if selected else "#e8e0ff",
                    fg="#ffffff" if selected else self.gui.accent_color,
                    state=tk.NORMAL if self.gui.voice_sample_paths.get(voice_id) else tk.DISABLED
                )

    def update_voice_summary(self):
        """Update voice summary display with improved visibility."""
        selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
        count = len(selected_ids)
        total = len(self.gui.voice_profiles)

        if count == 0:
            self.gui.voice_summary_var.set("⚠️ 선택 안 함")
            # 라벨 색상을 빨간색으로 변경
            voice_panel = getattr(self.gui, 'voice_panel', None)
            if voice_panel is not None:
                voice_summary_label = getattr(voice_panel, 'voice_summary_label', None)
                if voice_summary_label is not None:
                    voice_summary_label.config(fg="#dc2626")  # 빨간색
        else:
            # 간결한 요약 (잘림 방지)
            self.gui.voice_summary_var.set(f"✅ {count}개 선택됨")
            # 라벨 색상을 보라색으로 변경
            voice_panel = getattr(self.gui, 'voice_panel', None)
            if voice_panel is not None:
                voice_summary_label = getattr(voice_panel, 'voice_summary_label', None)
                if voice_summary_label is not None:
                    voice_summary_label.config(fg=self.gui.accent_color)  # 보라색

    def play_voice_sample(self, voice_id: str):
        """Play voice sample audio."""
        profile = self.get_voice_profile(voice_id)
        if not profile:
            logger.warning("[Play] Profile not found: %s", voice_id)
            return

        path = self.gui.voice_sample_paths.get(voice_id)
        logger.debug("[Play] voice_id: %s", voice_id)
        logger.debug("[Play] Cached path: %s", path)

        # Check if file actually exists even if path is not loaded
        if not path:
            dest_path = os.path.join(self.gui.voice_sample_dir, f"{voice_id}.wav")
            logger.debug("[Play] Check file exists: %s", dest_path)
            logger.debug("[Play] File exists: %s", os.path.exists(dest_path))
            if os.path.exists(dest_path):
                self.gui.voice_sample_paths[voice_id] = dest_path
                path = dest_path
                logger.debug("[Play] Path update complete: %s", path)
                # Update button state
                self.update_voice_card_styles()

        if not path or not os.path.exists(path):
            logger.error("[Play Error] File not found: %s", path)
            show_warning(
                self.gui.root,
                "샘플 없음",
                f"샘플 오디오 파일을 찾을 수 없습니다.\n경로: {path}"
            )
            return

        # Convert to absolute path (winsound compatibility)
        abs_path = os.path.abspath(path)
        logger.debug("[Play] Start playing: %s", abs_path)
        logger.debug("[Play] winsound available: %s", winsound is not None)

        try:
            if winsound is not None:
                logger.debug("[Play] Try playing with winsound")
                # Stop previous playback
                winsound.PlaySound(None, winsound.SND_PURGE)
                # Play with absolute path
                winsound.PlaySound(abs_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                logger.debug("[Play] Playing started: %s", profile.get('label', voice_id))
            elif simpleaudio is not None and AudioSegment is not None:
                if self.gui._active_sample_player:
                    try:
                        self.gui._active_sample_player.stop()
                    except Exception as e:
                        logger.debug("[Play] Failed to stop previous player: %s", e)
                audio = AudioSegment.from_file(path)
                play_obj = simpleaudio.play_buffer(
                    audio.raw_data,
                    num_channels=audio.channels,
                    bytes_per_sample=audio.sample_width,
                    sample_rate=audio.frame_rate,
                )
                self.gui._active_sample_player = play_obj
            elif simpleaudio is not None:
                show_warning(self.gui.root, "재생 불가", "pydub 모듈을 사용할 수 없습니다.")
                return
            else:
                show_warning(self.gui.root, "재생 불가", "이 환경에서는 오디오 재생이 지원되지 않습니다.")
                return
        except Exception as exc:
            ui_controller.write_error_log(exc)
            show_error(self.gui.root, "재생 오류", str(exc))

    def ensure_voice_samples(self, force: bool = False) -> bool:
        """Ensure each voice has a playable preview sample produced by Gemini."""
        if not GENAI_SDK_AVAILABLE:
            logger.warning("[Voice Sample] Cannot generate voice samples without Gemini SDK.")
            return False
        # Map existing samples first
        existing_only = True
        targets: List[Dict[str, Any]] = []
        for profile in self.gui.voice_profiles:
            voice_id = profile.get("id")
            if not voice_id:
                continue
            dest_path = os.path.join(self.gui.voice_sample_dir, f"{voice_id}.wav")
            if os.path.exists(dest_path) and not force:
                self.gui.voice_sample_paths[voice_id] = dest_path
                continue
            targets.append(profile)
            existing_only = False

        if existing_only and not force:
            if threading.current_thread() is threading.main_thread():
                self.update_voice_card_styles()
            else:
                self.gui.root.after(0, self.update_voice_card_styles)
            return False

        # Ensure we have a Gemini client only if we actually need to generate
        client = getattr(self.gui, 'genai_client', None)
        if client is None:
            if not self.gui.init_client():
                self._notify_api_missing()
                return False
            client = getattr(self.gui, 'genai_client', None)
            if client is None:
                self._notify_api_missing()
                return False

        generated_any = False
        failures: List[str] = []

        # When force=True regenerate every profile; otherwise only missing
        generation_list = self.gui.voice_profiles if force else targets

        for profile in generation_list:
            voice_id = profile.get('id')
            if not voice_id:
                continue

            dest_path = os.path.join(self.gui.voice_sample_dir, f"{voice_id}.wav")

            if self._generate_tts_sample(profile, dest_path, duration=3.0):
                self.gui.voice_sample_paths[voice_id] = dest_path
                generated_any = True
            else:
                failures.append(profile.get('label', voice_id))

        if failures:
            message = "다음 음성 샘플 생성에 실패했습니다:\n- " + "\n- ".join(failures) + \
                      "\n\nGemini API 키 설정을 확인하고 다시 시도하세요."
            def warn():
                show_warning(self.gui.root, "샘플 생성 실패", message)
            if threading.current_thread() is threading.main_thread():
                warn()
            else:
                self.gui.root.after(0, warn)

        if threading.current_thread() is threading.main_thread():
            self.update_voice_card_styles()
        else:
            self.gui.root.after(0, self.update_voice_card_styles)
        return generated_any

    def _generate_tts_sample(self, profile: Dict[str, Any], dest_path: str, duration: float = 3.0) -> bool:
        """Use Gemini TTS to create a trimmed preview sample if possible."""
        if not (GENAI_SDK_AVAILABLE and GENAI_TYPES_AVAILABLE):
            logger.warning("[Voice Sample] Cannot generate sample without Gemini SDK components.")
            return False
        prompt = profile.get('sample_text') or (
            f"Hello. This is a {profile.get('label')} voice sample."
            " A short greeting."
        )

        attempts = 0
        max_attempts = max(1, len(getattr(self.gui.api_key_manager, "api_keys", {})))

        while attempts < max_attempts:
            client = getattr(self.gui, 'genai_client', None)
            if client is None:
                return False
            try:
                response = client.models.generate_content(
                    model=config.GEMINI_TTS_MODEL,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=profile.get('voice_name')
                                )
                            )
                        )
                    )
                )
                audio_data = response.candidates[0].content.parts[0].inline_data.data
                self._write_trimmed_sample(dest_path, audio_data, duration)
                return True
            except Exception as exc:
                ui_controller.write_error_log(exc)
                attempts += 1
                if self._is_api_key_error(exc) and hasattr(self.gui, "api_key_manager"):
                    try:
                        self.gui.api_key_manager.block_current_key(duration_minutes=60)
                    except Exception as e:
                        logger.debug("[TTS] Failed to block API key: %s", e)
                    if not self.gui.init_client():
                        break
                    continue
                logger.error("[TTS] Sample generation failed (%s): %s", profile.get('label'), exc)
                return False
        return False

    @staticmethod
    def _is_api_key_error(exc: Exception) -> bool:
        """Check if exception is an API key error."""
        msg = str(exc)
        return any(token in msg for token in ("PERMISSION_DENIED", "API key not valid", "quota", "UNAUTHENTICATED"))

    def _write_trimmed_sample(self, dest_path: str, audio_data: Any, duration: float) -> None:
        """Persist audio data, trimming or padding to the target duration."""
        import base64

        # Convert audio_data to binary
        if isinstance(audio_data, str):
            binary_data = base64.b64decode(audio_data)
        else:
            binary_data = audio_data or b""

        # Save directly if RIFF header exists
        if binary_data.startswith(b"RIFF"):
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(binary_data)
            logger.info("[Sample Generated] WAV file saved: %s (%d bytes)", os.path.basename(dest_path), len(binary_data))
            return

        # Treat as raw PCM and add WAV header if no RIFF header
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            # Convert raw PCM to WAV
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)  # mono
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(24000)  # 24kHz
                wf.writeframes(binary_data)

            logger.debug("[Sample Generated] RAW PCM -> WAV conversion: %d bytes", len(binary_data))

            # Trim/pad to duration
            with wave.open(tmp_path, "rb") as src:
                channels = src.getnchannels()
                sample_width = src.getsampwidth()
                frame_rate = src.getframerate()
                max_frames = int(frame_rate * duration)
                frames = src.readframes(max_frames)
                expected = max_frames * channels * sample_width
                if len(frames) < expected:
                    frames += b"\x00" * (expected - len(frames))

            # Resample to 44.1kHz using numpy (audioop removed in Python 3.13+)
            target_rate = 44100
            if frame_rate != target_rate:
                try:
                    import numpy as np
                    # Convert bytes to numpy array
                    if sample_width == 1:
                        dtype = np.uint8
                    elif sample_width == 2:
                        dtype = np.int16
                    elif sample_width == 4:
                        dtype = np.int32
                    else:
                        dtype = np.int16

                    audio_data = np.frombuffer(frames, dtype=dtype)

                    # Calculate resampling ratio
                    ratio = target_rate / frame_rate
                    new_length = int(len(audio_data) * ratio)

                    # Simple linear interpolation resampling
                    indices = np.linspace(0, len(audio_data) - 1, new_length)
                    resampled = np.interp(indices, np.arange(len(audio_data)), audio_data.astype(np.float64))
                    resampled = resampled.astype(dtype)

                    frames = resampled.tobytes()
                    frame_rate = target_rate
                except ImportError:
                    # Fallback: skip resampling if numpy not available
                    logger.warning("[Warning] numpy not available for resampling, using original sample rate")

            # Save final file
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with wave.open(dest_path, "wb") as dst:
                dst.setnchannels(channels)
                dst.setsampwidth(sample_width)
                dst.setframerate(frame_rate)
                dst.writeframes(frames)

            logger.info("[Sample Generated] Final save: %s", os.path.basename(dest_path))
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def _notify_api_missing(self) -> None:
        """Notify user that Gemini API configuration is required."""
        def warn():
            show_warning(
                self.gui.root,
                "API 키 필요",
                "Gemini TTS 샘플을 생성하려면 먼저 API 키를 등록해야 합니다.\n"
                "API 키 관리 메뉴에서 키를 설정하고 다시 시도하세요."
            )
        if threading.current_thread() is threading.main_thread():
            warn()
        else:
            self.gui.root.after(0, warn)

    def on_voice_mode_change(self, *_):
        """Handle voice mode change. (Deprecated - voice selection now uses checkboxes)"""
        self.update_voice_controls()

    def on_single_voice_change(self, *_):
        """Handle single voice selection change. (Deprecated - voice selection now uses checkboxes)"""
        self.update_voice_controls()

    def update_voice_controls(self):
        """Update voice control UI. (Deprecated - voice selection now uses checkboxes)"""
        # Legacy compatibility - no-op since voice selection is now via voice_vars checkboxes
        self.update_voice_info_label()
        self.refresh_voice_status_display()

    def update_voice_info_label(self, latest_voice: str = None):
        """Update voice information label to show selected voices from checkboxes."""
        voice_info_label = getattr(self.gui, 'voice_info_label', None)
        if voice_info_label is None:
            return

        # Get selected voices from checkboxes
        selected_voices = [vid for vid, state in self.gui.voice_vars.items() if state.get()]

        if selected_voices:
            if len(selected_voices) == 1:
                summary = f"선택된 음성: {selected_voices[0]}"
            else:
                summary = f"선택된 음성 ({len(selected_voices)}개): " + ", ".join(selected_voices[:3])
                if len(selected_voices) > 3:
                    summary += f" 외 {len(selected_voices) - 3}개"
        else:
            summary = "⚠ 음성이 선택되지 않음"

        if latest_voice:
            summary += f" | 최근 사용: {latest_voice}"

        self.gui.voice_info_label.config(text=summary)

    def get_voice_status_text(self) -> str:
        """Get voice status text for display based on selected checkboxes."""
        selected_voices = [vid for vid, state in self.gui.voice_vars.items() if state.get()]

        if not selected_voices:
            return "미선택"
        elif len(selected_voices) == 1:
            return selected_voices[0]
        else:
            return f"{len(selected_voices)}개 음성"

    def refresh_voice_status_display(self, latest_voice: str = None):
        """Refresh voice status display in status bar."""
        status_label = getattr(self.gui, "status_bar", None)
        if not status_label:
            return
        states = getattr(self.gui, 'progress_states', {}) or {}
        if states and not all((s.get('status') == 'waiting') for s in states.values()):
            return
        voice_text = latest_voice or self.get_voice_status_text()
        # status_label.config(text=f"Ready! (Voice: {voice_text})")
        status_label.config(text=f"")

    def prepare_tts_voice(self) -> str:
        """Get selected TTS voice from UI checkboxes (voice_vars).

        Note: This function is deprecated. The actual voice selection is done
        via voice_vars checkboxes in the UI. Keeping for backward compatibility.
        """
        # Get first checked voice from voice_vars
        selected_voices = [vid for vid, state in self.gui.voice_vars.items() if state.get()]

        if selected_voices:
            voice_id = selected_voices[0]
            profile = self.get_voice_profile(voice_id)
            if profile and profile.get("voice_name"):
                voice = profile["voice_name"]
            else:
                voice = voice_id
            display_voice = self.get_voice_label(voice_id)
            logger.debug("[TTS] UI selection: '%s' -> '%s'", voice_id, voice)
        else:
            # Fallback to first available voice or profile default
            voice = self.gui.available_tts_voices[0] if self.gui.available_tts_voices else ""
            if not voice:
                fallback_profile = self.gui.voice_profiles[0] if self.gui.voice_profiles else None
                if fallback_profile:
                    voice = fallback_profile.get("voice_name") or fallback_profile.get("id") or ""
            if not voice:
                voice = "aoede"
            display_voice = self.get_voice_label(voice)
            logger.debug("[TTS] No selection, default voice: '%s'", voice)

        self.gui.fixed_tts_voice = voice
        self.gui.last_voice_used = voice
        self.update_voice_info_label(latest_voice=display_voice)
        self.refresh_voice_status_display(latest_voice=display_voice)
        return voice
