"""
애니메이션 유틸리티 (PyQt6)
"""

def ease_out_quad(t):
    return 1 - (1 - t) * (1 - t)

class TkAnimation:
    @staticmethod
    def animate_value(*args, **kwargs):
        # 참고: 애니메이션은 Qt에서 별도로 처리됩니다
        pass
