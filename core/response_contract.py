"""Pure semantic validation for TC Generation, Analysis and Review JSON."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import AppMode, Confidence, ReviewVerdict, Verdict


@dataclass(frozen=True)
class ContractIssue:
    path: str
    code: str
    message: str


@dataclass(frozen=True)
class ContractReport:
    valid: bool
    issues: tuple[ContractIssue, ...]


def _issue(path: str, code: str, message: str) -> ContractIssue:
    return ContractIssue(path=path, code=code, message=message)


def validate_response_contract(data: Any, mode: str | AppMode) -> ContractReport:
    issues: list[ContractIssue] = []
    if not isinstance(data, Mapping):
        return ContractReport(False, (_issue("$", "TYPE", "최상위 결과는 JSON Object여야 합니다."),))
    mode_value = str(mode)
    if mode_value == AppMode.TC_GENERATION.value:
        _validate_generation(data, issues)
    elif mode_value == AppMode.VALIDATION_ANALYSIS.value:
        _validate_analysis(data, issues)
    elif mode_value == AppMode.TC_REVIEW.value:
        _validate_review(data, issues)
    else:
        issues.append(_issue("$.mode", "ENUM", f"지원하지 않는 모드입니다: {mode_value}"))
    return ContractReport(not issues, tuple(issues))


def _validate_generation(data: Mapping[str, Any], issues: list[ContractIssue]) -> None:
    cases = data.get("test_cases")
    if not isinstance(cases, list) or not cases:
        issues.append(_issue("$.test_cases", "REQUIRED", "1개 이상의 TC 배열이 필요합니다."))
        return
    for index, case in enumerate(cases):
        path = f"$.test_cases[{index}]"
        if not isinstance(case, Mapping):
            issues.append(_issue(path, "TYPE", "TC는 JSON Object여야 합니다."))
            continue
        steps = case.get("steps")
        expected = case.get("expected_results")
        if not isinstance(steps, list):
            issues.append(_issue(path + ".steps", "TYPE", "steps는 배열이어야 합니다."))
        if not isinstance(expected, list):
            issues.append(_issue(path + ".expected_results", "TYPE", "expected_results는 배열이어야 합니다."))
        if isinstance(steps, list) and isinstance(expected, list) and len(steps) != len(expected):
            issues.append(_issue(path, "COUNT_MISMATCH", "steps와 expected_results 개수가 다릅니다."))


def _validate_analysis(data: Mapping[str, Any], issues: list[ContractIssue]) -> None:
    result = str(data.get("result", "")).upper()
    confidence = str(data.get("confidence", "")).upper()
    allowed_result = {item.value for item in Verdict}
    allowed_confidence = {item.value for item in Confidence}
    if result not in allowed_result:
        issues.append(_issue("$.result", "ENUM", "허용되지 않은 result입니다."))
    if confidence not in allowed_confidence:
        issues.append(_issue("$.confidence", "ENUM", "허용되지 않은 confidence입니다."))
    if result == Verdict.PASS.value and data.get("fail_factors"):
        issues.append(_issue("$.fail_factors", "CONTRADICTION", "PASS 결과에 fail_factors가 존재합니다."))
    if result in {Verdict.INCONCLUSIVE.value, Verdict.EVIDENCE_INSUFFICIENT.value} and not data.get("gaps"):
        issues.append(_issue("$.gaps", "REQUIRED", "판정 불가 결과에는 최소 1개의 gap이 필요합니다."))
    coverage = data.get("evidence_coverage")
    if isinstance(coverage, Mapping):
        required = coverage.get("required_items")
        verified = coverage.get("verified_items")
        percent = coverage.get("coverage_percent")
        if all(isinstance(v, (int, float)) for v in (required, verified, percent)):
            expected = 0 if required == 0 else round(verified / required * 100)
            if percent != expected:
                issues.append(_issue("$.evidence_coverage.coverage_percent", "CALCULATION", f"계산값은 {expected}%여야 합니다."))
            if verified > required:
                issues.append(_issue("$.evidence_coverage", "RANGE", "verified_items는 required_items를 초과할 수 없습니다."))


def _validate_review(data: Mapping[str, Any], issues: list[ContractIssue]) -> None:
    cases = data.get("reviewed_test_cases")
    if not isinstance(cases, list):
        issues.append(_issue("$.reviewed_test_cases", "TYPE", "reviewed_test_cases는 배열이어야 합니다."))
        return
    allowed = {item.value for item in ReviewVerdict}
    for index, case in enumerate(cases):
        path = f"$.reviewed_test_cases[{index}]"
        if not isinstance(case, Mapping):
            issues.append(_issue(path, "TYPE", "Review 결과는 JSON Object여야 합니다."))
            continue
        if case.get("review_result") not in allowed:
            issues.append(_issue(path + ".review_result", "ENUM", "허용되지 않은 review_result입니다."))
        score = case.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
            issues.append(_issue(path + ".score", "RANGE", "score는 0~100 숫자여야 합니다."))
    summary = data.get("review_summary")
    if isinstance(summary, Mapping) and summary.get("total_count") not in (None, len(cases)):
        issues.append(_issue("$.review_summary.total_count", "COUNT_MISMATCH", "실제 Review TC 개수와 다릅니다."))
