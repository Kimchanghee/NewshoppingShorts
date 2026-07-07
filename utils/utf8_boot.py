# -*- coding: utf-8 -*-
"""
UTF-8 강제 부트스트랩 — cp949↔utf-8 모지바케(제목 ????? / 채널명 깨짐) 근본 차단.

윈도우 한국어 환경의 기본 코드페이지(cp949)로 텍스트가 인코딩/디코딩되면
한글/중문이 손상되고 표현 불가 글자가 '?'로 치환된다. 이 모듈을 앱과 모든
벌크 스크립트의 '최상단'에서 import(또는 force_utf8() 호출)하면:

- 자식 프로세스가 상속하도록 PYTHONUTF8=1 / PYTHONIOENCODING=utf-8 환경변수 설정
- 현재 프로세스의 stdout/stderr를 utf-8로 재설정
- subprocess env 헬퍼 제공(utf8_env)

import 시점에 자동 적용되므로 `import utils.utf8_boot  # noqa` 한 줄이면 된다.
"""
from __future__ import annotations

import os
import sys


def force_utf8() -> None:
    """Set UTF-8 env (inherited by child processes) and reconfigure std streams."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    # Some libraries read this; harmless elsewhere.
    os.environ.setdefault("PYTHONLEGACYWINDOWSFSENCODING", "0")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # py3.7+
        except Exception:
            pass


def utf8_env(extra: dict | None = None) -> dict:
    """Return an environment dict for subprocess calls that forces UTF-8 in the child."""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    return env


# Apply immediately on import.
force_utf8()
