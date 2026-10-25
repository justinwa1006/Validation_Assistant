import unittest

import tests.conftest  # noqa: F401
from core.result_schema import validate_ai_result_schema


class ValidateSchemaTest(unittest.TestCase):
    def test_minimal_valid(self):
        ok, errors, _warnings, data = validate_ai_result_schema({"result": "pass", "summary": "ok"})
        self.assertTrue(ok, errors)
        self.assertEqual(data["result"], "PASS")

    def test_non_object(self):
        ok, errors, _w, data = validate_ai_result_schema([1, 2])
        self.assertFalse(ok)
        self.assertEqual(data, {})
        self.assertTrue(errors)

    def test_missing_required_fields(self):
        ok, errors, _w, _d = validate_ai_result_schema({"result": "PASS"})
        self.assertFalse(ok)
        self.assertTrue(any("summary" in e for e in errors))

    def test_invalid_result_enum(self):
        ok, errors, _w, _d = validate_ai_result_schema({"result": "PASS | FAIL", "summary": "x"})
        self.assertFalse(ok)
        self.assertTrue(any("result" in e for e in errors))

    def test_unknown_confidence_is_downgraded_with_warning(self):
        ok, _e, warnings, data = validate_ai_result_schema({"result": "FAIL", "summary": "x", "confidence": "SURE"})
        self.assertTrue(ok)
        self.assertEqual(data["confidence"], "UNKNOWN")
        self.assertTrue(any("confidence" in w for w in warnings))

    def test_next_actions_normalized(self):
        _ok, _e, _w, data = validate_ai_result_schema({
            "result": "FAIL", "summary": "x",
            "next_actions": ["로그 재수집", {"priority": "high", "action": "ACTION", "owner": "kim"},
                             {"priority": "high", "action": "원인 분석", "owner": "kim", "status": "in progress"}],
        })
        actions = data["next_actions"]
        self.assertEqual([a["action"] for a in actions], ["로그 재수집", "원인 분석"])
        self.assertEqual(actions[0]["owner"], "TBD")
        self.assertEqual(actions[1]["priority"], "HIGH")
        self.assertEqual(actions[1]["status"], "IN_PROGRESS")

    def test_does_not_mutate_input(self):
        original = {"result": "pass", "summary": "x"}
        validate_ai_result_schema(original)
        self.assertEqual(original["result"], "pass")


if __name__ == "__main__":
    unittest.main()


class HelperTest(unittest.TestCase):
    def test_defaults_are_not_shared_between_calls(self):
        from core.result_schema import validate_ai_result_schema as v
        _, _, _, first = v({"result": "PASS", "summary": "x"})
        first["evidence_coverage"]["missing_items"].append("mutated")
        first["observations"].append("mutated")
        _, _, _, second = v({"result": "PASS", "summary": "x"})
        self.assertEqual(second["evidence_coverage"]["missing_items"], [])
        self.assertEqual(second["observations"], [])

    def test_timeline_sorted_and_placeholder_dropped(self):
        from core.result_schema import normalize_event_timeline
        warnings = []
        out = normalize_event_timeline([
            {"order": 3, "event": "c", "timestamp": "1.0s"},
            {"order": 1, "event": "EVENT"},
            {"order": 2, "event": "b", "status": "verified"},
            42,
        ], warnings)
        self.assertEqual([e["event"] for e in out], ["b", "c"])
        self.assertEqual(out[0]["status"], "VERIFIED")
        self.assertEqual(out[1]["timestamp_type"], "OBSERVED_TIME")
        self.assertEqual(len(warnings), 1)

    def test_list_field_coercion(self):
        from core.result_schema import validate_ai_result_schema as v
        _, _, warnings, data = v({"result": "PASS", "summary": "x", "gaps": "single", "observations": 5})
        self.assertEqual(data["gaps"], ["single"])
        self.assertEqual(data["observations"], [])
        self.assertTrue(any("observations" in w for w in warnings))

