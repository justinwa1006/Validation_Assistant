"""Validation Analysis / TC Review 프롬프트 조립 (Qt 의존 없음).

위젯에서 읽은 값과 도메인 설정을 인자로 받아 문자열만 돌려주는 순수 함수다.
GUI 없이 단위 테스트할 수 있고, tc_engine.generate_prompt 는 입력 수집과 후처리만 담당한다.
"""
from __future__ import annotations

from .templating import fill_template

ANALYSIS_RULES = """[Analysis Rules]
1. 입력된 TC 목적과 기대 결과를 기준으로 관찰 사실과 추론을 명확히 구분한다.
2. 증적이 부족한 경우 result는 "INCONCLUSIVE" 또는 "EVIDENCE INSUFFICIENT"로 처리한다.
3. recommended_verification은 정량적 확인 방법과 판단 기준을 포함하여 작성한다.
4. 근거 필드(observations, gaps, pass_factors, fail_factors)를 먼저 작성하고, 그 내용에서 result와 confidence를 도출한다.
5. result 기준: PASS=모든 Expected 조건이 증적으로 확인됨, FAIL=하나 이상의 Expected 조건이 증적으로 위반됨, PARTIAL=일부 조건만 충족되고 나머지는 증적 부족, INCONCLUSIVE=증적 부족으로 판정 불가.
6. confidence 기준: HIGH=증적 충분(coverage 100%)하고 측정값이 기준과 명확히 구분됨, MEDIUM=coverage 50~99% 또는 기준값과 근접, LOW=coverage 50% 미만이거나 추론에 의존함.
7. 입력에 없는 임계값·수치·신호명은 지어내지 말고 "TBD (사양 미정: 확인 필요 항목)"으로 표기한다.
"""

REVIEW_RULES = """[Review Rules]
1. TC의 명확성, 정량적 측정 가능성, 누락된 경계 조건(Boundary Conditions)을 검토한다.
2. 모호한 정성적 문구가 있을 경우 정량적 수치 조건(ms, V, 0xHEX)으로 보정안을 제시한다.
"""


def build_validation_analysis_prompt(
    *,
    system_instruction: str,
    few_shot: str,
    domain_role: str,
    domain_rules: str,
    domain_evidence: str,
    tc_name: str,
    tc_information: str,
    actual_result: str,
    analysis_purpose: str,
    analysis_question: str,
) -> str:
    """Validation Analysis 프롬프트 본문을 만든다 (후처리 전)."""
    template = (
        f"{system_instruction}\n\n"
        f"{few_shot}\n\n"
        "너는 __DOMAIN_ROLE__이다.\n"
        "다음 분야별 분석 기준을 적용하라.\n"
        "__DOMAIN_RULES__\n\n"
        "[Validation Information]\n"
        "TC Name: __TC_NAME__\n"
        "TC Information: __PURPOSE__\n"
        "Actual Result / Issue: __ACTUAL__\n"
        "Selected Analysis Purpose: __ANALYSIS_PURPOSE__\n"
        "User Analysis Question: __ANALYSIS_QUESTION__\n\n"
        "[Evidence Summary]\n"
        "__DOMAIN_EVIDENCE__\n\n"
        "[Attached Evidence]\n"
        "[[EVIDENCE_PREVIEW]]\n\n"
        f"{ANALYSIS_RULES}"
    )
    return fill_template(template, {
        "__DOMAIN_ROLE__": domain_role,
        "__DOMAIN_RULES__": domain_rules,
        "__DOMAIN_EVIDENCE__": domain_evidence,
        "__TC_NAME__": tc_name,
        "__PURPOSE__": tc_information,
        "__ACTUAL__": actual_result,
        "__ANALYSIS_PURPOSE__": analysis_purpose,
        "__ANALYSIS_QUESTION__": analysis_question or "Actual Result와 Expected Result 간 차이 원인을 정량 분석하라.",
    })


def build_tc_review_prompt(
    *,
    system_instruction: str,
    domain_role: str,
    domain_rules: str,
    tc_name: str,
    purpose: str,
    expected: str,
) -> str:
    """TC Review 프롬프트 본문을 만든다 (후처리 전)."""
    template = (
        f"{system_instruction}\n\n"
        "너는 __DOMAIN_ROLE__이다.\n"
        "다음 분야별 리뷰 기준을 적용하라.\n"
        "__DOMAIN_RULES__\n\n"
        "[TC Information]\n"
        "TC Name: __TC_NAME__\n"
        "Purpose: __PURPOSE__\n"
        "Expected Result: __EXPECTED__\n\n"
        f"{REVIEW_RULES}"
    )
    return fill_template(template, {
        "__DOMAIN_ROLE__": domain_role,
        "__DOMAIN_RULES__": domain_rules,
        "__TC_NAME__": tc_name,
        "__PURPOSE__": purpose,
        "__EXPECTED__": expected,
    })

