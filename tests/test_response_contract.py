from core.contracts import AppMode
from core.response_contract import validate_response_contract


def test_generation_rejects_step_expected_count_mismatch():
    report = validate_response_contract(
        {"test_cases": [{"steps": ["a", "b"], "expected_results": ["a"]}]},
        AppMode.TC_GENERATION,
    )
    assert not report.valid
    assert any(issue.code == "COUNT_MISMATCH" for issue in report.issues)


def test_analysis_rejects_pass_with_fail_factors():
    report = validate_response_contract(
        {"result": "PASS", "confidence": "HIGH", "fail_factors": ["x"], "gaps": []},
        AppMode.VALIDATION_ANALYSIS,
    )
    assert not report.valid
    assert any(issue.code == "CONTRADICTION" for issue in report.issues)


def test_analysis_checks_coverage_calculation():
    report = validate_response_contract(
        {
            "result": "FAIL", "confidence": "HIGH", "fail_factors": ["x"],
            "evidence_coverage": {"required_items": 4, "verified_items": 3, "coverage_percent": 50},
        },
        AppMode.VALIDATION_ANALYSIS,
    )
    assert any(issue.code == "CALCULATION" for issue in report.issues)


def test_review_accepts_valid_contract():
    report = validate_response_contract(
        {
            "review_summary": {"total_count": 1},
            "reviewed_test_cases": [{"review_result": "PASS", "score": 95}],
        },
        AppMode.TC_REVIEW,
    )
    assert report.valid
