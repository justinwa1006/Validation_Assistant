"""모델 응답 텍스트에서 JSON 을 추출/복구한다 (Qt 의존 없음)."""
from __future__ import annotations

import html
import json
import re


def extract_json_from_text(text: object) -> str | None:
    text = html.unescape(str(text)).replace("“", '"').replace("”", '"').replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE).strip()
    if not text:
        return None

    marker = "[JSON OUTPUT]"
    if marker in text:
        text = text.split(marker, 1)[1].strip()

    if "```json" in text:
        parts = text.split("```json", 1)
        text = parts[1]
        if "```" in text:
            text = text.split("```", 1)[0]
        text = text.strip()
    elif "```" in text:
        parts = text.split("```", 1)
        text = parts[1]
        if "```" in text:
            text = text.split("```", 1)[0]
        text = text.strip()

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    start_index = text.find("{")
    if start_index < 0:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for index in range(start_index, len(text)):
        char = text[index]

        if in_string:
            if escape_next:
                escape_next = False
            elif char == "\\":
                escape_next = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start_index:index + 1].strip()
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    return None

    return None


def repair_common_json_errors(text: str | None) -> str:
    """AI 응답의 흔한 JSON 오류를 간단히 정리한다."""

    if not text:
        return ""

    repaired = text.strip()

    repaired = repaired.replace("```json", "")
    repaired = repaired.replace("```JSON", "")
    repaired = repaired.replace("```", "")

    # Python 형식 값을 JSON 형식으로 변경
    repaired = repaired.replace(": None", ": null")
    repaired = repaired.replace(": True", ": true")
    repaired = repaired.replace(": False", ": false")

    # 마지막 쉼표 제거
    repaired = repaired.replace(",\n}", "\n}")
    repaired = repaired.replace(",\n]", "\n]")

    return repaired.strip()

