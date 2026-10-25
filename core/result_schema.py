"""AI 검증 결과 JSON 의 스키마 검증/정규화 (Qt 의존 없음).

validate_ai_result_schema 는 단계별 헬퍼를 순서대로 호출하는 얇은 조립 함수다.
각 헬퍼는 독립적으로 테스트할 수 있다.
"""
from __future__ import annotations

ALLOWED_RESULTS = {"PASS", "FAIL", "PARTIAL", "INCONCLUSIVE", "EVIDENCE INSUFFICIENT"}
ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
ALLOWED_RISK = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
ALLOWED_EVIDENCE_STATUS = {"SUFFICIENT", "INSUFFICIENT", "PARTIAL", "UNKNOWN"}
ALLOWED_TIMELINE_STATUSES = {"VERIFIED", "PARTIAL", "FAILED", "MISSING", "UNKNOWN"}
ALLOWED_TIMESTAMP_TYPES = {"EVENT_TIME", "OBSERVED_TIME", "TBD"}
ALLOWED_ACTION_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}
ALLOWED_ACTION_STATUSES = {"OPEN", "IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED", "UNKNOWN"}

PLACEHOLDER_EVENTS = {"", "EVENT NAME", "ACTUAL EVENT NAME", "EVENT", "TBD"}
PLACEHOLDER_ACTIONS = {"", "ACTION", "ACTION DESCRIPTION", "NEXT ACTION", "TBD"}

REQUIRED_FIELDS = ("result", "summary")
LIST_FIELDS = (
    "observations", "root_cause", "gaps", "recommended_verification",
    "next_actions", "event_timeline", "coverage_assessment",
    "pass_factors", "fail_factors", "confidence_reason",
)


def _default_fields() -> dict:
    """호출마다 새 객체를 돌려준다 (가변 기본값이 호출 간에 공유되지 않도록)."""
    return {
        "final_verdict": "REVIEW REQUIRED",
        "severity": "UNKNOWN",
        "requirement_id": "TBD",
        "tc_id": "TBD",
        "evidence_coverage": {
            "required_items": 0,
            "verified_items": 0,
            "coverage_percent": 0,
            "missing_items": [],
        },
        "observations": [],
        "root_cause": [],
        "gaps": [],
        "recommended_verification": [],
        "next_actions": [],
        "event_timeline": [],
        "coverage_assessment": [],
        "pass_factors": [],
        "fail_factors": [],
        "confidence_reason": [],
    }


def check_required_and_result(data: dict, errors: list[str]) -> None:
    """필수 필드와 result enum 을 검사하고 result 를 대문자로 정규화한다."""
    for field_name in REQUIRED_FIELDS:
        value = data.get(field_name)
        if value is None or not str(value).strip():
            errors.append(f"필수 필드가 없거나 비어 있습니다: {field_name}")

    result = str(data.get("result", "")).strip().upper()
    if result and result not in ALLOWED_RESULTS:
        errors.append(f"result 값이 올바르지 않습니다: {result}")
    elif result:
        data["result"] = result


def normalize_enum_field(data: dict, name: str, allowed: set[str], warnings: list[str]) -> None:
    """허용되지 않은 값은 경고와 함께 UNKNOWN 으로 바꾼다."""
    value = str(data.get(name, "UNKNOWN")).strip().upper()
    if value not in allowed:
        warnings.append(f"{name} 값이 올바르지 않아 UNKNOWN으로 변경했습니다: {value}")
        value = "UNKNOWN"
    data[name] = value


def apply_defaults_and_list_types(data: dict, warnings: list[str]) -> None:
    """누락 필드에 기본값을 채우고, 목록 필드의 타입을 list 로 맞춘다."""
    for field_name, default_value in _default_fields().items():
        if field_name not in data:
            data[field_name] = default_value

    for field_name in LIST_FIELDS:
        value = data.get(field_name)
        if value is None:
            data[field_name] = []
        elif isinstance(value, str):
            data[field_name] = [value]
        elif not isinstance(value, list):
            warnings.append(f"{field_name} 필드가 List 형식이 아니어서 빈 목록으로 변경했습니다.")
            data[field_name] = []


def normalize_event_timeline(items: list, warnings: list[str]) -> list[dict]:
    """event_timeline 항목을 표준 형태로 바꾸고 order 순으로 정렬한다."""
    normalized: list[dict] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, str):
            normalized.append({
                "order": index,
                "event": item.strip() or "TBD",
                "status": "UNKNOWN",
                "evidence": "TBD",
                "timestamp": "TBD",
                "timestamp_type": "TBD",
            })
            continue

        if not isinstance(item, dict):
            warnings.append(f"event_timeline의 {index}번째 항목이 Object 형식이 아니어서 제외했습니다.")
            continue

        try:
            order = int(item.get("order", index))
        except (TypeError, ValueError):
            order = index

        event = str(item.get("event", "TBD")).strip()
        if event.upper() in PLACEHOLDER_EVENTS:
            continue

        status = str(item.get("status", "UNKNOWN")).strip().upper()
        if status not in ALLOWED_TIMELINE_STATUSES:
            status = "UNKNOWN"

        evidence = str(item.get("evidence", "TBD")).strip() or "TBD"
        timestamp = str(item.get("timestamp", "TBD")).strip() or "TBD"
        timestamp_type = str(item.get("timestamp_type", "TBD")).strip().upper()
        if timestamp_type not in ALLOWED_TIMESTAMP_TYPES:
            timestamp_type = "TBD"

        if timestamp.upper() == "TBD":
            timestamp_type = "TBD"
        elif timestamp_type == "TBD":
            timestamp_type = "OBSERVED_TIME"

        normalized.append({
            "order": max(order, 1),
            "event": event,
            "status": status,
            "evidence": evidence,
            "timestamp": timestamp,
            "timestamp_type": timestamp_type,
        })

    normalized.sort(key=lambda entry: entry.get("order", 9999))
    return normalized


def normalize_next_actions(items: list) -> list[dict]:
    """next_actions 항목을 {priority, action, owner, status} 로 정규화한다."""
    normalized: list[dict] = []
    for item in items:
        if isinstance(item, str):
            action_text = item.strip()
            if not action_text:
                continue
            normalized.append({"priority": "UNKNOWN", "action": action_text, "owner": "TBD", "status": "OPEN"})
            continue

        if not isinstance(item, dict):
            continue

        priority = str(item.get("priority", "UNKNOWN")).strip().upper()
        if "|" in priority or priority not in ALLOWED_ACTION_PRIORITIES:
            priority = "UNKNOWN"

        action = str(item.get("action", "")).strip()
        if action.upper() in PLACEHOLDER_ACTIONS:
            continue

        owner = str(item.get("owner", "TBD")).strip() or "TBD"
        status = str(item.get("status", "OPEN")).strip().upper().replace(" ", "_").replace("-", "_")
        if "|" in status or status not in ALLOWED_ACTION_STATUSES:
            status = "OPEN"

        normalized.append({"priority": priority, "action": action, "owner": owner, "status": status})
    return normalized


def validate_ai_result_schema(data: object) -> tuple[bool, list[str], list[str], dict]:
    """AI JSON 을 검증/정규화한다. 반환: (유효 여부, 오류 목록, 경고 목록, 정규화된 dict)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        errors.append("JSON 최상위 구조는 Object여야 합니다.")
        return False, errors, warnings, {}

    normalized = dict(data)

    check_required_and_result(normalized, errors)
    normalize_enum_field(normalized, "confidence", ALLOWED_CONFIDENCE, warnings)
    normalize_enum_field(normalized, "risk", ALLOWED_RISK, warnings)
    normalize_enum_field(normalized, "evidence_status", ALLOWED_EVIDENCE_STATUS, warnings)
    apply_defaults_and_list_types(normalized, warnings)

    normalized["event_timeline"] = normalize_event_timeline(normalized.get("event_timeline", []), warnings)
    normalized["next_actions"] = normalize_next_actions(normalized.get("next_actions", []))

    return not errors, errors, warnings, normalized

