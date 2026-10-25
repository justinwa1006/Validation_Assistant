import json
import unittest
from pathlib import Path

import tests.conftest  # noqa: F401
from eval.run_eval import load_jsonl, score

CASES = Path(__file__).resolve().parent.parent / "eval" / "cases" / "analysis_cases.jsonl"


def _out(result, order_ok=True, extra_number=None):
    data = {"evidence_status": "SUFFICIENT", "observations": ["x"], "gaps": [], "pass_factors": [],
            "fail_factors": [], "result": result, "confidence": "HIGH", "risk": "LOW",
            "summary": "요약" + (f" {extra_number}ms" if extra_number else "")}
    return "```json\n" + json.dumps(data, ensure_ascii=False) + "\n```"


class EvalScoreTest(unittest.TestCase):
    def test_seed_cases_load(self):
        cases = load_jsonl(CASES)
        self.assertEqual(len(cases), 20)
        self.assertEqual({c["expected_result"] for c in cases}, {"PASS", "FAIL", "INCONCLUSIVE"})

    def test_perfect_outputs(self):
        cases = load_jsonl(CASES)
        outputs = [{"case_id": c["id"], "output": _out(c["expected_result"])} for c in cases]
        report = score(cases, outputs)
        self.assertEqual(report["verdict_accuracy"], 1.0)
        self.assertEqual(report["schema_ok_rate"], 1.0)

    def test_wrong_verdict_and_invented_number(self):
        cases = load_jsonl(CASES)[:2]
        outputs = [{"case_id": cases[0]["id"], "output": _out("FAIL", extra_number=999)},
                   {"case_id": cases[1]["id"], "output": "not json"}]
        report = score(cases, outputs)
        self.assertEqual(report["verdict_accuracy"], 0.0)
        self.assertEqual(report["json_valid_rate"], 0.5)
        self.assertEqual(report["unsupported_number_rate"], 0.5)

    def test_missing_output_is_not_counted_as_answered(self):
        cases = load_jsonl(CASES)
        report = score(cases, [])
        self.assertEqual(report["answered"], 0)


if __name__ == "__main__":
    unittest.main()

