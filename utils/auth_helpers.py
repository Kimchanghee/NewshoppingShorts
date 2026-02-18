# -*- coding: utf-8 -*-
"""
인증/로그인 관련 공통 유틸리티 함수.
"""

from datetime import datetime, timezone


def extract_user_id(login_data) -> str | None:
    """login_data 딕셔너리에서 user_id를 안전하게 추출한다.

    지원하는 구조:
      - {"data": {"data": {"id": "..."}}}  (서버 응답 래핑)
      - {"userId": "..."}                  (플랫 구조)
    """
    if not login_data or not isinstance(login_data, dict):
        return None
    data_part = login_data.get("data", {})
    if isinstance(data_part, dict):
        inner = data_part.get("data", {})
        user_id = inner.get("id") if isinstance(inner, dict) else None
        if user_id:
            return user_id
    return login_data.get("userId")


def parse_utc_datetime(value) -> datetime | None:
    """ISO datetime 문자열을 timezone-aware UTC datetime으로 파싱한다.

    - "Z" 접미사를 "+00:00"으로 변환
    - naive datetime은 UTC로 간주
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(value, datetime):
            dt = value
        else:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None
