"""파일명/목록 접두사 등 텍스트 유틸 (Qt 의존 없음)."""
from __future__ import annotations

import re


def strip_existing_list_prefix(value: object) -> str:
    text = "" if value is None else str(value).strip()
    previous = None
    while text and text != previous:
        previous = text
        text = re.sub(r"^\s*(?:(?:step|precondition|expected(?: result)?)\s*)?(?:\d+(?:\.\d+)*(?:[.)]|(?=\s))|[-•▪◦])\s*", "", text, flags=re.IGNORECASE).strip()
    return text


def make_safe_filename(text: object, fallback: str = "Validation_Result") -> str:
    """Windows 파일명에 사용할 수 없는 문자를 제거한다."""
    invalid_chars = '<>:"/\\|?*'

    safe_name = str(text or "").strip()

    for char in invalid_chars:
        safe_name = safe_name.replace(char, "_")

    # 줄바꿈과 연속 공백 정리
    safe_name = " ".join(safe_name.split())

    # Windows에서 파일명 끝의 점과 공백은 사용할 수 없음
    safe_name = safe_name.rstrip(". ")

    # 파일명이 지나치게 길어지지 않게 제한
    safe_name = safe_name[:100]

    return safe_name or fallback

