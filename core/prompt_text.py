"""프롬프트 텍스트 정리/정규화 유틸 (Qt 의존 없음)."""
from __future__ import annotations

import hashlib
import re
import textwrap
from typing import Any, List, Tuple

SECTION_HEADER_RE = re.compile(r'^\[{1,2}[^\[\]"]+\]{1,2}$')
NUMBERED_PREFIX_RE = re.compile(r"^\d+[.)]\s")
NUMBERED_ITEM_RE = re.compile(
    r"^(?P<step>Step\s*)?(?P<num>\d+(?:[-.]\d+)*)(?P<sep>\s*[.)：:](?!\d)\s*|\s+|$)(?P<rest>.*)$",
    re.I,
)
DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
HEX_RE = re.compile(r"^[+-]?0[xX][0-9A-Fa-f]+$")
UNIT_NUMBER_RE = re.compile(
    r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:ms|us|µs|s|mv|v|ma|a|khz|hz|deg|%)$", re.I
)

def numbered_items(text: str) -> List[Tuple[str, str]]:
    items = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        match = NUMBERED_ITEM_RE.match(line)
        # "13.5V 인가", "150ms 이내" 같은 수치 시작 문장은 번호로 보지 않는다.
        is_numbered = bool(
            match
            and (
                match.group("step")
                or match.group("sep").strip()
                or re.search(r"[-.]", match.group("num"))
            )
        )
        if is_numbered:
            items.append((match.group("num"), match.group("rest").strip() or line))
        else:
            items.append((str(len(items) + 1), line))
    return items


def normalize_signal_match_name(value: Any) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value or ""))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).lower().strip()
    aliases = {"req": "request", "sts": "status", "stat": "status", "res": "result", "rsp": "response", "cmd": "command", "drv": "driver", "psg": "passenger", "veh": "vehicle"}
    return " ".join(aliases.get(token, token) for token in text.split())


def coerce_rule_value(value: Any) -> Any:
    text = str(value).strip()
    if HEX_RE.match(text):
        return float(int(text, 16))
    if DECIMAL_RE.match(text):
        return float(text)
    unit_match = UNIT_NUMBER_RE.match(text)
    if unit_match:
        return float(unit_match.group(1))
    return text.upper()


def light_alias_suffix(token: str) -> str:
    digest = hashlib.sha256(("VA_LIGHT_MASK_V1|" + str(token)).encode("utf-8")).hexdigest().upper()
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return f"_{letters[int(digest[:2],16)%len(letters)]}{int(digest[2:4],16)%10}"


def normalize_prompt_spacing(text: str) -> str:
    if not text:
        return ""
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned_lines = []
    previous_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and previous_blank:
            continue
        cleaned_lines.append(line)
        previous_blank = is_blank
    return "\n".join(cleaned_lines).strip()


def is_structural_line(stripped: str) -> bool:
    """JSON 스키마 등 들여쓰기/중복이 의미를 갖는 구조 라인 판별."""
    if stripped[0] in '{}]"':
        return True
    return stripped[0] == "[" and not SECTION_HEADER_RE.match(stripped)


def clean_prompt_block(text: str) -> str:
    if not text:
        return ""
    text = textwrap.dedent(text)
    text = text.replace("\t", "    ")
    lines = text.splitlines()
    cleaned_lines = []
    previous_blank = False
    for line in lines:
        line = line.rstrip()
        is_blank = not line.strip()
        if is_blank:
            if previous_blank:
                continue
            cleaned_lines.append("")
            previous_blank = True
            continue
        cleaned_lines.append(line)
        previous_blank = False
    return "\n".join(cleaned_lines).strip()

