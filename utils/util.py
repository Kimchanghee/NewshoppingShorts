from tkinter import ttk, filedialog, scrolledtext, simpledialog
from ui.components.custom_dialog import show_question
import os

def check_seoul_font(self):
    """서울한강체 설치 확인 및 안내"""
    seoul_fonts = [
        "C:/Windows/Fonts/SeoulHangangL.ttf",
        "C:/Windows/Fonts/SeoulHangangM.ttf",
        "C:/Windows/Fonts/SeoulHangangB.ttf",
        "C:/Windows/Fonts/SeoulHangangEB.ttf"
    ]

    font_exists = any(os.path.exists(font) for font in seoul_fonts)

    if not font_exists:
        message = (
            "서울한강체가 설치되지 않았습니다.\n\n"
            "더 나은 자막 품질을 위해 서울한강체 설치를 권장합니다.\n"
            "서울시 홈페이지에서 무료로 다운로드 가능합니다.\n\n"
            "계속 진행하시겠습니까?"
        )

        response = show_question(self.root, "폰트 안내", message)
        if not response:
            return False
    return True