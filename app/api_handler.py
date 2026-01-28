"""
API Key Management Handler

This module handles API key management UI and logic, extracted from main.py.
API keys are stored securely using SecretsManager (encrypted storage).
"""

import tkinter as tk
from tkinter import ttk
import json
import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ui.components.custom_dialog import show_info, show_warning, show_error, show_question
from ui.components.rounded_widgets import create_rounded_button, ModernScrollbar, StatusBadge
from ui.components.base_widget import ThemedMixin
from ui.theme_manager import ThemeManager, get_theme_manager
from core.api import ApiKeyManager
from utils.logging_config import get_logger
from utils.secrets_manager import SecretsManager
import config

# Initialize logger
logger = get_logger(__name__)

# Stricter Gemini API key validation pattern
# Format: AIza followed by 35-100 alphanumeric, underscore, or dash characters
# Max length prevents excessively long inputs (typical key is 39 chars total)
GEMINI_API_KEY_PATTERN = re.compile(r'^AIza[A-Za-z0-9_-]{35,96}$')

if TYPE_CHECKING:
    from app.main_app import VideoAnalyzerGUI


class APIHandler:
    """Handles API key management UI and logic"""

    def __init__(self, app: 'VideoAnalyzerGUI'):
        self.app = app

    def load_saved_api_keys(self):
        """
        Load saved API keys from secure storage via APIKeyManager.
        저장된 API 키 자동 로드 (APIKeyManager를 통해 SecretsManager에서).

        APIKeyManager가 SecretsManager를 사용하여 암호화된 저장소에서 키를 로드합니다.
        레거시 JSON 파일이 있으면 마이그레이션을 수행합니다.

        Note:
            APIKeyManager가 이미 SecretsManager를 사용하므로 중복 로딩 로직 제거됨.
            This method now delegates to APIKeyManager which handles SecretsManager internally.
        """
        try:
            # APIKeyManager 초기화 (SecretsManager에서 키 로드)
            # Initialize APIKeyManager (loads keys from SecretsManager)
            api_manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)
            loaded_keys = api_manager.api_keys

            if loaded_keys:
                config.GEMINI_API_KEYS = loaded_keys.copy()
                logger.info(f"[API Handler] {len(loaded_keys)}개 API 키 로드됨 (via APIKeyManager)")
                return

            # 레거시 JSON 파일에서 마이그레이션 (한 번만 수행)
            # Migrate from legacy JSON file (one-time operation)
            self._migrate_legacy_keys()

        except Exception as e:
            logger.exception(f"[API Handler] API 키 로드 중 오류: {e}")

    def _migrate_legacy_keys(self):
        """
        레거시 JSON 파일에서 SecretsManager로 키 마이그레이션
        Migrate keys from legacy JSON file to SecretsManager
        """
        try:
            api_keys_file = getattr(self.app, 'api_keys_file', None)
            if not api_keys_file or not os.path.exists(api_keys_file):
                return

            logger.info("[API Handler] 레거시 JSON에서 API 키 마이그레이션 시작...")

            with open(api_keys_file, 'r', encoding='utf-8') as f:
                saved_keys = json.load(f)

            # 이미 마이그레이션된 경우 스킵
            if saved_keys.get('migrated_to_secure_storage'):
                logger.debug("[API Handler] 이미 마이그레이션 완료됨")
                return

            if 'gemini' not in saved_keys or not isinstance(saved_keys['gemini'], dict):
                return

            original = saved_keys['gemini']
            normalized = {}
            migrated_count = 0

            for idx, (_, val) in enumerate(original.items(), start=1):
                if val:
                    key_name = f"api_{idx}"
                    normalized[key_name] = val

                    # SecretsManager에 저장
                    try:
                        if SecretsManager.store_api_key(f"gemini_api_{idx}", val):
                            migrated_count += 1
                    except Exception as migrate_err:
                        logger.warning(f"[API Handler] 키 마이그레이션 실패 {key_name}: {migrate_err}")

            if migrated_count > 0:
                config.GEMINI_API_KEYS = normalized
                logger.info(f"[API Handler] {migrated_count}개 키 마이그레이션 완료")

                # 마이그레이션 완료 표시 (평문 키 제거)
                try:
                    backup_data = {
                        'gemini': {},
                        'migrated_to_secure_storage': True,
                        'migrated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    with open(api_keys_file, 'w', encoding='utf-8') as f:
                        json.dump(backup_data, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass

        except (IOError, OSError) as e:
            logger.warning(f"[API Handler] 레거시 파일 I/O 오류: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"[API Handler] JSON 파싱 오류: {e}")
        except Exception as e:
            logger.exception(f"[API Handler] 마이그레이션 오류: {e}")

    def show_api_key_manager(self):
        """
        API 키 관리 모달 - 최대 10개 입력 가능
        테마 시스템을 사용한 모던 UI
        """
        tm = get_theme_manager()

        key_window = tk.Toplevel(self.app.root)
        key_window.title("API 키 관리")
        key_window.configure(bg=tm.get_color("bg_main"))
        key_window.resizable(False, False)

        # 윈도우 크기 및 위치 (중앙 배치)
        width = 600
        height = 680
        parent = self.app.root
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        key_window.geometry(f"{width}x{height}+{x}+{y}")

        # 모달 동작
        key_window.transient(parent)
        key_window.grab_set()

        # ESC로 닫기
        key_window.bind("<Escape>", lambda e: key_window.destroy())

        # 헤더
        header = tk.Frame(key_window, bg=tm.get_color("bg_header"), height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="API 키 관리",
            font=("맑은 고딕", 14, "bold"),
            bg=tm.get_color("bg_header"),
            fg=tm.get_color("text_primary"),
            padx=20
        ).pack(side=tk.LEFT, pady=12)

        # 닫기 버튼
        close_label = tk.Label(
            header,
            text="X",
            font=("맑은 고딕", 14),
            bg=tm.get_color("bg_header"),
            fg=tm.get_color("text_secondary"),
            cursor="hand2"
        )
        close_label.pack(side=tk.RIGHT, padx=16, pady=12)
        close_label.bind("<Button-1>", lambda e: key_window.destroy())
        close_label.bind("<Enter>", lambda e: close_label.configure(fg=tm.get_color("error")))
        close_label.bind("<Leave>", lambda e: close_label.configure(fg=tm.get_color("text_secondary")))

        # 구분선
        tk.Frame(key_window, bg=tm.get_color("border_light"), height=1).pack(fill=tk.X)

        # 컨텐츠 영역
        content = tk.Frame(key_window, bg=tm.get_color("bg_main"))
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # 현재 상태 표시
        current_count = len(config.GEMINI_API_KEYS)
        status_type = "success" if current_count > 0 else "error"

        status_frame = tk.Frame(content, bg=tm.get_color("bg_main"))
        status_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            status_frame,
            text="등록된 키:",
            font=("맑은 고딕", 10),
            bg=tm.get_color("bg_main"),
            fg=tm.get_color("text_primary")
        ).pack(side=tk.LEFT)

        # 상태 배지
        self._status_badge = StatusBadge(
            status_frame,
            text=f"{current_count}/10개",
            status=status_type
        )
        self._status_badge.pack(side=tk.LEFT, padx=(8, 0))

        if current_count == 0:
            # 경고 배지
            warning_badge = StatusBadge(
                status_frame,
                text="최소 1개 필요",
                status="warning"
            )
            warning_badge.pack(side=tk.LEFT, padx=(8, 0))

        # 스크롤 가능한 API 키 입력 영역
        keys_container = tk.Frame(content, bg=tm.get_color("bg_card"))
        keys_container.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        canvas = tk.Canvas(
            keys_container,
            bg=tm.get_color("bg_card"),
            highlightthickness=0
        )
        scrollbar = ModernScrollbar(
            keys_container,
            command=canvas.yview,
            width=8
        )
        scrollable_frame = tk.Frame(canvas, bg=tm.get_color("bg_card"))

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=540)
        canvas.configure(yscrollcommand=scrollbar.set)

        # 마우스 휠 스크롤
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4))

        # API 키 입력 필드들 (10개)
        self.app.api_key_entries = []

        for i in range(10):
            # 각 키 입력 행
            key_row = tk.Frame(scrollable_frame, bg=tm.get_color("bg_card"))
            key_row.pack(fill=tk.X, padx=12, pady=6)

            # 라벨
            tk.Label(
                key_row,
                text=f"키 {i+1}",
                width=5,
                bg=tm.get_color("bg_card"),
                fg=tm.get_color("text_primary"),
                font=("맑은 고딕", 9, "bold"),
                anchor="w"
            ).pack(side=tk.LEFT, padx=(0, 8))

            # 입력 필드
            entry = tk.Entry(
                key_row,
                font=("Consolas", 10),
                bg=tm.get_color("bg_input"),
                fg=tm.get_color("text_primary"),
                relief=tk.FLAT,
                show="*",
                bd=0,
                highlightthickness=1,
                highlightbackground=tm.get_color("border_light"),
                highlightcolor=tm.get_color("border_focus"),
                insertbackground=tm.get_color("primary")
            )
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))

            # 기존 키가 있으면 표시
            key_name = f"api_{i+1}"
            if key_name in config.GEMINI_API_KEYS:
                entry.insert(0, config.GEMINI_API_KEYS[key_name])

            self.app.api_key_entries.append(entry)

            # 표시/숨기기 토글 버튼 (클로저로 상태 캡처)
            toggle_btn = tk.Button(
                key_row,
                text="보기",
                bg=tm.get_color("bg_secondary"),
                activebackground=tm.get_color("bg_hover"),
                fg=tm.get_color("text_secondary"),
                font=("맑은 고딕", 8),
                width=4,
                relief=tk.FLAT,
                cursor="hand2"
            )

            def make_toggle_command(ent, btn):
                """Create toggle command with proper closure."""
                def toggle():
                    if ent.cget('show') == '':
                        ent.config(show='*')
                        btn.config(text="보기")
                    else:
                        ent.config(show='')
                        btn.config(text="숨김")
                return toggle

            toggle_btn.config(command=make_toggle_command(entry, toggle_btn))
            toggle_btn.pack(side=tk.LEFT)

        # 버튼 프레임
        button_frame = tk.Frame(content, bg=tm.get_color("bg_main"))
        button_frame.pack(fill=tk.X, pady=(8, 0))

        # 저장 버튼
        save_btn = create_rounded_button(
            button_frame,
            text="저장하기",
            command=lambda: self.save_api_keys_from_ui(key_window),
            style="primary",
            theme_manager=tm
        )
        save_btn.pack(side=tk.LEFT)

        # 모두 지우기 버튼
        clear_btn = create_rounded_button(
            button_frame,
            text="모두 지우기",
            command=lambda: self.clear_all_api_keys(key_window),
            style="danger",
            theme_manager=tm
        )
        clear_btn.pack(side=tk.LEFT, padx=(8, 0))

        # 닫기 버튼
        close_btn = create_rounded_button(
            button_frame,
            text="닫기",
            command=key_window.destroy,
            style="secondary",
            theme_manager=tm
        )
        close_btn.pack(side=tk.LEFT, padx=(8, 0))

        # 도움말 섹션
        help_frame = tk.Frame(content, bg=tm.get_color("info_bg"))
        help_frame.pack(fill=tk.X, pady=(16, 0))

        help_text = (
            "Gemini API 키 발급 방법:\n"
            "1. https://aistudio.google.com/apikey 접속\n"
            "2. Google 계정 로그인 후 'Create API Key' 클릭\n"
            "3. AIzaSy로 시작하는 39자 키 복사\n"
            "4. 여러 키 등록 시 부하 분산으로 안정성 향상"
        )

        tk.Label(
            help_frame,
            text=help_text,
            font=("맑은 고딕", 9),
            bg=tm.get_color("info_bg"),
            fg=tm.get_color("info"),
            justify=tk.LEFT,
            anchor="w",
            padx=12,
            pady=10
        ).pack(fill=tk.X)

        # 창 닫힐 때 마우스휠 바인딩 해제
        def on_close():
            try:
                canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
            key_window.destroy()

        key_window.protocol("WM_DELETE_WINDOW", on_close)

    def save_api_keys_from_ui(self, window):
        """
        UI에서 입력받은 API 키를 SecretsManager에 저장
        Save API keys from UI to SecretsManager

        검증 -> 저장 -> APIKeyManager 재초기화 순서로 진행
        Flow: Validate -> Store -> Reinitialize APIKeyManager
        """
        try:
            # 암호화 라이브러리 확인
            # Check cryptography library availability
            try:
                from cryptography.fernet import Fernet  # noqa: F401
            except ImportError:
                show_error(
                    window,
                    "라이브러리 오류",
                    "암호화 라이브러리가 설치되지 않았습니다.\n\n"
                    "터미널에서 다음 명령어를 실행하세요:\n"
                    "pip install cryptography"
                )
                return

            # 키 수집 및 검증 (패턴 검증은 GEMINI_API_KEY_PATTERN 사용)
            # Collect and validate keys
            new_gemini_keys = {}
            valid_count = 0
            invalid_entries = []

            for i, entry in enumerate(self.app.api_key_entries):
                key_value = entry.get().strip()
                if not key_value:
                    continue

                if GEMINI_API_KEY_PATTERN.match(key_value):
                    key_name = f"api_{i+1}"
                    new_gemini_keys[key_name] = key_value
                    valid_count += 1
                else:
                    invalid_entries.append(i + 1)
                    logger.warning(f"[API Handler] 키 {i+1}: 잘못된 형식 (무시됨)")

            if valid_count == 0:
                msg = "유효한 Gemini API 키를 최소 1개 이상 입력해주세요.\n(AIza로 시작하는 39자 이상)"
                if invalid_entries:
                    msg += f"\n\n잘못된 형식: 키 {', '.join(map(str, invalid_entries))}"
                show_warning(window, "경고", msg)
                return

            # SecretsManager에 저장
            # Store to SecretsManager
            stored_count = 0
            store_errors = []

            for key_name, key_value in new_gemini_keys.items():
                try:
                    # SecretsManager 키 이름 형식: gemini_api_N
                    secret_key_name = f"gemini_{key_name}"
                    if SecretsManager.store_api_key(secret_key_name, key_value):
                        stored_count += 1
                    else:
                        store_errors.append(f"{key_name}: 저장 실패")
                except RuntimeError as runtime_err:
                    store_errors.append(f"{key_name}: {str(runtime_err)}")
                    logger.error(f"[API Handler] {key_name} 저장 오류: {runtime_err}")
                except Exception as store_err:
                    store_errors.append(f"{key_name}: {str(store_err)}")
                    logger.error(f"[API Handler] {key_name} 저장 실패: {store_err}")

            if stored_count == 0:
                error_detail = "\n".join(store_errors) if store_errors else "알 수 없는 오류"
                show_error(
                    window,
                    "저장 오류",
                    f"API 키를 안전하게 저장하는 데 실패했습니다.\n\n"
                    f"오류 상세:\n{error_detail}"
                )
                return

            # 전역 변수 및 APIKeyManager 업데이트
            # Update global config and reinitialize APIKeyManager
            config.GEMINI_API_KEYS = new_gemini_keys

            # APIKeyManager 재초기화 (SecretsManager에서 로드)
            self.app.api_key_manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)

            # 클라이언트 재초기화
            try:
                self.app.init_client()
                show_info(
                    window,
                    "저장 완료",
                    f"API 키가 안전하게 저장되었습니다!\n\n"
                    f"• Gemini: {valid_count}개 (암호화됨)\n\n"
                    f"다음 실행 시 자동으로 로드됩니다."
                )
                window.destroy()
            except Exception as init_error:
                logger.exception("[API Handler] API 초기화 실패")
                show_error(window, "오류", f"API 초기화 실패:\n{str(init_error)}")

        except Exception as e:
            logger.exception("[API Handler] API 키 저장 실패")
            show_error(window, "오류", f"저장 실패:\n{str(e)}")

    def clear_all_api_keys(self, window):
        """모든 API 키 입력 필드 초기화"""
        if show_question(window, "확인", "모든 API 키를 지우시겠습니까?"):
            for entry in self.app.api_key_entries:
                entry.delete(0, tk.END)

    def save_api_keys_to_file(self) -> bool:
        """
        현재 config의 API 키를 SecretsManager에 저장
        Save current config API keys to SecretsManager

        Note:
            이 메서드는 레거시 호환성을 위해 유지됩니다.
            실제 저장은 SecretsManager를 통해 수행됩니다.

        Returns:
            bool: 저장 성공 여부
        """
        try:
            stored_count = 0
            for key_name, key_value in config.GEMINI_API_KEYS.items():
                if not key_value:
                    continue

                try:
                    # key_name: api_N -> secret_key: gemini_api_N
                    idx = key_name.replace('api_', '')
                    secret_key_name = f"gemini_api_{idx}"

                    if SecretsManager.store_api_key(secret_key_name, key_value):
                        stored_count += 1
                except Exception as store_err:
                    logger.error(f"[API Handler] {key_name} 저장 실패: {store_err}")

            if stored_count > 0:
                logger.info(f"[API Handler] {stored_count}개 키 저장 완료 (SecretsManager)")
                return True
            else:
                logger.warning("[API Handler] 저장할 API 키 없음")
                return False

        except Exception as e:
            logger.exception(f"[API Handler] API 키 저장 중 오류: {e}")
            return False

    def show_api_status(self):
        """API 키 상태를 팝업으로 표시"""
        api_key_manager = getattr(self.app, 'api_key_manager', None)
        if api_key_manager is None:
            show_warning(self.app.root, "경고", "API 키 관리자가 초기화되지 않았습니다.")
            return
        status = api_key_manager.get_status()
        key_count = len(config.GEMINI_API_KEYS)
        title = f"API 키 상태 ({key_count}개 등록됨)"
        show_info(self.app.root, title, f"현재 API 키 상태:\n\n{status}")
