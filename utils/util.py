"""
Utility helpers without any Tkinter dependency.
"""

import os
from ui.components.custom_dialog import show_question


def check_seoul_font(parent=None) -> bool:
    """
    Ensure the Seoul font family is available. If missing, prompt the user
    using the PyQt6 dialog helpers. Returns True when it is safe to continue.
    """
    seoul_fonts = (
        "C:/Windows/Fonts/SeoulHangangL.ttf",
        "C:/Windows/Fonts/SeoulHangangM.ttf",
        "C:/Windows/Fonts/SeoulHangangB.ttf",
        "C:/Windows/Fonts/SeoulHangangEB.ttf",
    )

    if any(os.path.exists(font) for font in seoul_fonts):
        return True

    message = (
        "서울서체가 설치되어 있지 않습니다.\n\n"
        "더 나은 자막 품질을 위해 서울서체 설치를 권장합니다.\n"
        "서울시 홈페이지에서 무료로 다운로드 받을 수 있습니다.\n\n"
        "계속 진행하시겠습니까?"
    )
    return bool(show_question(parent, "폰트 안내", message))
