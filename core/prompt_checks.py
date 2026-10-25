"""프롬프트 예시/모델 출력의 구조 검사 (Qt 의존 없음).

테스트(tests/)와 평가 스크립트(eval/run_eval.py)가 같은 기준을 쓰도록 한 곳에 둔다.
"""
from __future__ import annotations

import json
import re
from typing import Any

ALLOWED_RESULTS = {"PASS", "FAIL", "PARTIAL", "INCONCLUSIVE", "EVIDENCE INSUFFICIENT"}
ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
ALLOWED_RISK = {"HIGH", "MEDIUM", "LOW"}
ALLOWED_EVIDENCE_STATUS = {"SUFFICIENT", "INSUFFICIENT", "PARTIAL"}

# 근거 필드는 판정(result)보다 먼저 나와야 한다.
EVIDENCE_FIELDS = ("observations", "gaps", "pass_factors", "fail_factors")

VAGUE_PATTERNS = [
    r"약\s?\d", r"대략", r"적절히", r"확인할 것", r"상응하는", r"정상\s?(?:적으로\s)?(?:감지|동작|처리)",
    r"\bproperly\b", r"\broughly\b", r"\babout\b",
]
_VAGUE_RE = re.compile("|".join(VAGUE_PATTERNS))
_JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n```", re.S)
_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
_QUANT_RE = re.compile(r"(\d|0x[0-9A-Fa-f]+|==|!=|>=|<=|HTTP\s?\d{3}|\b(?:true|false)\b)")


def extract_json_blocks(text: str) -> list[str]:
    """텍스트 안의 ```json 코드블록 본문을 모두 반환한다."""
    return _JSON_BLOCK_RE.findall(text)


def parse_model_output(text: str) -> Any:
    """모델 출력(코드블록 유무 모두)을 JSON으로 파싱한다. 실패하면 ValueError."""
    blocks = extract_json_blocks(text)
    candidate = blocks[0] if blocks else text.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON 파싱 실패: {error}") from error


def find_vague_phrases(text: str) -> list[str]:
    return [m.group(0) for m in _VAGUE_RE.finditer(text)]


def check_tc_item(item: dict) -> list[str]:
    """생성된 TC 하나의 구조 문제를 문자열 목록으로 반환한다 (빈 목록이면 통과)."""
    problems: list[str] = []
    steps = item.get("steps") or []
    expected = item.get("expected_results") or []
    if len(steps) != len(expected):
        problems.append(f"steps({len(steps)})와 expected_results({len(expected)}) 개수 불일치")
    for index, line in enumerate(expected, start=1):
        text = str(line)
        if "TBD" in text:
            continue  # 사양에 없는 값은 TBD로 명시하는 것이 올바른 동작
        if not _QUANT_RE.search(text):
            problems.append(f"expected_results[{index}] 정량 표현 없음: {text[:40]}")
        vague = find_vague_phrases(text)
        if vague:
            problems.append(f"expected_results[{index}] 모호한 표현: {vague}")
    return problems


def check_analysis_output(raw_text: str) -> dict:
    """검증 분석 출력 하나를 검사한다. 반환: {'ok': bool, 'problems': [...], 'data': dict|None}."""
    problems: list[str] = []
    try:
        data = parse_model_output(raw_text)
    except ValueError as error:
        return {"ok": False, "problems": [str(error)], "data": None}
    if not isinstance(data, dict):
        return {"ok": False, "problems": ["최상위가 Object가 아님"], "data": None}

    result = str(data.get("result", "")).strip().upper()
    if result not in ALLOWED_RESULTS:
        problems.append(f"result 값 오류: {result!r}")
    for name, allowed in (("confidence", ALLOWED_CONFIDENCE), ("risk", ALLOWED_RISK),
                          ("evidence_status", ALLOWED_EVIDENCE_STATUS)):
        value = str(data.get(name, "")).strip().upper()
        if value not in allowed:
            problems.append(f"{name} 값 오류: {value!r}")
    if not str(data.get("summary", "")).strip():
        problems.append("summary 비어 있음")

    keys = list(data.keys())
    if "result" in keys:
        verdict_index = keys.index("result")
        late = [f for f in EVIDENCE_FIELDS if f in keys and keys.index(f) > verdict_index]
        if late:
            problems.append(f"판정(result)보다 뒤에 나온 근거 필드: {late}")
    return {"ok": not problems, "problems": problems, "data": data}


def numbers_in(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def unsupported_numbers(output_text: str, source_text: str) -> set[str]:
    """출력에는 있지만 입력(사양/로그)에는 없는 숫자 — 지어낸 수치 후보(휴리스틱)."""
    return numbers_in(output_text) - numbers_in(source_text)

