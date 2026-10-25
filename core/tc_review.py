"""생성된 TC 에 대한 규칙 기반 리뷰 (Qt 의존 없음)."""
from __future__ import annotations

import re


def build_rule_based_tc_review(generation_data: object) -> dict:
    """AI 호출 없이 생성 TC의 구조와 기본 품질을 검사한다."""
    cases = generation_data.get("test_cases", []) if isinstance(generation_data, dict) else []
    reviewed = []
    pass_count = 0
    needs_count = 0

    for index, item in enumerate(cases, 1):
        issues = []
        recommendations = []
        preconditions = item.get("preconditions", [])
        steps = item.get("steps", [])
        expected_results = item.get("expected_results", [])

        if not isinstance(preconditions, list) or not preconditions:
            issues.append("Preconditions가 없거나 배열 형식이 아닙니다.")
            recommendations.append("실행 전에 필요한 상태, 환경, 데이터 조건을 배열로 작성하세요.")
        if not isinstance(steps, list) or not steps:
            issues.append("Test Steps가 없거나 배열 형식이 아닙니다.")
            recommendations.append("실행 순서에 따라 Step을 하나의 동작씩 작성하세요.")
        if not isinstance(expected_results, list) or not expected_results:
            issues.append("Expected Results가 없거나 배열 형식이 아닙니다.")
            recommendations.append("각 Step에서 관찰하거나 측정할 결과를 작성하세요.")
        if isinstance(steps, list) and isinstance(expected_results, list):
            if len(steps) != len(expected_results):
                issues.append(
                    f"Steps와 Expected Results 개수가 다릅니다. ({len(steps)} / {len(expected_results)})"
                )
                recommendations.append("각 Step과 같은 번호의 Expected Result를 1:1로 맞추세요.")

        combined = " ".join(
            str(value) for values in (preconditions, steps, expected_results)
            if isinstance(values, list) for value in values
        )
        if re.search(r"\bTBD\b", combined, re.I):
            # 프롬프트의 MISSING-VALUE POLICY 에 따라 모델이 '사양에 없는 값'을 TBD 로 표기한 경우
            issues.append("사양 미정(TBD) 항목이 포함되어 있습니다.")
            recommendations.append("요구사항/사양에서 해당 값을 확인해 TBD 를 확정하세요.")
        if re.search(r"\b(UNKNOWN|추후|적절히|정상적으로)\b", combined, re.I):
            issues.append("확정되지 않았거나 모호한 표현이 포함되어 있습니다.")
            recommendations.append("수치, 상태, 시간 또는 관찰 기준으로 구체화하세요.")

        multi_action_count = 0
        if isinstance(steps, list):
            for step in steps:
                text = str(step)
                if text.count("하고") + text.count("한 후") + text.count("및") >= 2:
                    multi_action_count += 1
        if multi_action_count:
            issues.append(f"여러 동작이 섞였을 가능성이 있는 Step이 {multi_action_count}개 있습니다.")
            recommendations.append("한 Step에는 하나의 실행 동작만 남기도록 분리하세요.")

        risk = str(item.get("risk", "UNKNOWN")).upper()
        if risk not in {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}:
            issues.append("Risk 값이 허용된 값이 아닙니다.")
            recommendations.append("Risk를 HIGH, MEDIUM, LOW, UNKNOWN 중 하나로 작성하세요.")
        if not str(item.get("risk_description", "")).strip():
            issues.append("Risk Description이 비어 있습니다.")
            recommendations.append("TC 실패 시 발생 가능한 기능 또는 서비스 영향을 작성하세요.")

        score = max(0, 100 - len(issues) * 12)
        result = "PASS" if not issues else "NEEDS_IMPROVEMENT"
        if result == "PASS":
            pass_count += 1
        else:
            needs_count += 1
        reviewed.append({
            "tc_id": item.get("tc_id", f"TC_{index:03d}"),
            "title": item.get("title", ""),
            "review_result": result,
            "score": score,
            "issues": issues,
            "recommendations": recommendations,
            "steps_count": len(steps) if isinstance(steps, list) else 0,
            "expected_results_count": len(expected_results) if isinstance(expected_results, list) else 0,
            "risk": risk,
        })

    return {
        "summary": {
            "total_count": len(cases),
            "pass_count": pass_count,
            "needs_improvement_count": needs_count,
            "review_method": "Built-in rule-based review"
        },
        "reviewed_test_cases": reviewed
    }

