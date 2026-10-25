import unittest

import tests.conftest  # noqa: F401
from core.automotive_utils import decode_uds_payload, event_priority, split_dbc_identifier_words


class UdsDecodeTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(decode_uds_payload(b""), {})

    def test_negative_response(self):
        out = decode_uds_payload(bytes([0x7F, 0x27, 0x35]))
        self.assertEqual(out["response_type"], "NEGATIVE")
        self.assertEqual(out["service_name"], "SecurityAccess")
        self.assertEqual(out["negative_response_name"], "Invalid Key")

    def test_positive_read_did(self):
        out = decode_uds_payload(bytes([0x62, 0xF1, 0x90]))
        self.assertEqual(out["response_type"], "POSITIVE")
        self.assertEqual(out["service_name"], "ReadDataByIdentifier")
        self.assertEqual(out["did"], "0xF190")

    def test_request_with_subfunction(self):
        out = decode_uds_payload(bytes([0x10, 0x03]))
        self.assertEqual(out["service_name"], "DiagnosticSessionControl")
        self.assertEqual(out["sub_function"], "0x03")

    def test_unknown_service(self):
        self.assertEqual(decode_uds_payload(bytes([0x99]))["service_name"], "UNKNOWN")


class MiscTest(unittest.TestCase):
    def test_event_priority(self):
        self.assertEqual(event_priority({"msg": "Timeout on ECU"}), 0)
        self.assertEqual(event_priority({"event_type": "signal_change"}), 1)
        self.assertEqual(event_priority({"event_type": "other"}), 2)

    def test_split_identifier_words(self):
        self.assertEqual(split_dbc_identifier_words("Sig_DrvDoorLockSt"), ["sig", "drv", "door", "lock", "st"])




    def test_process_isotp_single_and_multiframe(self):
        from core.automotive_utils import process_isotp_frame_data, finalize_incomplete_tp_sessions
        sessions = []
        active = {}
        # Single frame UDS ReadDataByIdentifier (0x22 0xF1 0x90)
        process_isotp_frame_data(0x7E0, bytes([0x03, 0x22, 0xF1, 0x90, 0, 0, 0, 0]), 1.0, sessions, active, set())
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["status"], "COMPLETE")
        self.assertEqual(sessions[0]["uds"]["service_name"], "ReadDataByIdentifier")

        # Multi-frame First Frame (length 10) + Consecutive Frame
        process_isotp_frame_data(0x7E8, bytes([0x10, 0x0A, 0x62, 0xF1, 0x90, 0x41, 0x42, 0x43]), 1.1, sessions, active, set())
        self.assertIn(0x7E8, active)
        process_isotp_frame_data(0x7E8, bytes([0x21, 0x44, 0x45, 0x46, 0x47, 0x00, 0x00, 0x00]), 1.12, sessions, active, set())
        self.assertNotIn(0x7E8, active)
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[1]["status"], "COMPLETE")
        self.assertEqual(sessions[1]["payload_length"], 10)

        # Incomplete multi-frame session
        process_isotp_frame_data(0x7E0, bytes([0x10, 0x0C, 0x2E, 0xF1, 0x90, 0x01, 0x02, 0x03]), 2.0, sessions, active, set())
        finalize_incomplete_tp_sessions(active, sessions)
        self.assertEqual(sessions[-1]["status"], "INCOMPLETE")
        self.assertIn("MISSING_CONSECUTIVE_FRAME", sessions[-1]["issues"])

    def test_filter_and_prioritize_blf_events(self):
        from core.automotive_utils import filter_and_prioritize_blf_events
        events = [
            {"time_sec": 0.1, "event_type": "signal_change", "message": "M1", "signal": "StaticSig", "from": "UNOBSERVED", "to": "0"},
            {"time_sec": 0.2, "event_type": "signal_change", "message": "M1", "signal": "DoorLock", "from": "UNOBSERVED", "to": "UNLOCKED"},
            {"time_sec": 0.5, "event_type": "signal_change", "message": "M1", "signal": "DoorLock", "from": "UNLOCKED", "to": "LOCKED"},
            {"time_sec": 0.6, "event_type": "signal_change", "message": "M1", "signal": "AuthError", "from": "0", "to": "TIMEOUT_ERROR"},
        ]
        filtered_all, timeline, findings, removed = filter_and_prioritize_blf_events(
            events, list(events), always_keep_signals=set(), event_limit=10
        )
        self.assertEqual(removed, 1)  # StaticSig removed
        self.assertEqual(len(filtered_all), 3)
        self.assertEqual(len(timeline), 3)
        self.assertTrue(any("AuthError" in f for f in findings))


if __name__ == "__main__":
    unittest.main()

