"""차량 로그 처리용 순수 함수 (Qt 의존 없음)."""
from __future__ import annotations

import json
import re


def split_dbc_identifier_words(value: object) -> list[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).lower()
    return [word for word in text.split() if word]


def event_priority(event: dict) -> int:
    text = json.dumps(event, ensure_ascii=False).lower()
    critical_words = ("error", "fail", "failed", "timeout", "invalid", "fault")
    if any(word in text for word in critical_words):
        return 0
    if event.get("event_type") == "signal_change":
        return 1
    return 2


def decode_uds_payload(payload: bytes | bytearray | list[int]) -> dict[str, str]:
    if not payload:
        return {}
    sid = payload[0]
    service_names = {
        0x10: "DiagnosticSessionControl", 0x11: "ECUReset",
        0x14: "ClearDiagnosticInformation", 0x19: "ReadDTCInformation",
        0x22: "ReadDataByIdentifier", 0x23: "ReadMemoryByAddress",
        0x27: "SecurityAccess", 0x28: "CommunicationControl",
        0x2E: "WriteDataByIdentifier", 0x2F: "InputOutputControlByIdentifier",
        0x31: "RoutineControl", 0x34: "RequestDownload",
        0x36: "TransferData", 0x37: "RequestTransferExit",
        0x3E: "TesterPresent", 0x85: "ControlDTCSetting"
    }
    nrc_names = {
        0x10: "General Reject", 0x11: "Service Not Supported",
        0x12: "SubFunction Not Supported", 0x13: "Incorrect Message Length",
        0x21: "Busy Repeat Request", 0x22: "Conditions Not Correct",
        0x24: "Request Sequence Error", 0x31: "Request Out Of Range",
        0x33: "Security Access Denied", 0x35: "Invalid Key",
        0x36: "Exceeded Number Of Attempts", 0x37: "Required Time Delay Not Expired",
        0x70: "Upload Download Not Accepted", 0x71: "Transfer Data Suspended",
        0x72: "General Programming Failure", 0x73: "Wrong Block Sequence Counter",
        0x78: "Response Pending"
    }
    result = {"service_id": f"0x{sid:02X}"}
    if sid == 0x7F and len(payload) >= 3:
        request_sid, nrc = payload[1], payload[2]
        result.update({
            "response_type": "NEGATIVE",
            "request_service_id": f"0x{request_sid:02X}",
            "service_name": service_names.get(request_sid, "UNKNOWN"),
            "negative_response_code": f"0x{nrc:02X}",
            "negative_response_name": nrc_names.get(nrc, "UNKNOWN")
        })
    elif sid >= 0x40 and (sid - 0x40) in service_names:
        request_sid = sid - 0x40
        result.update({
            "response_type": "POSITIVE",
            "request_service_id": f"0x{request_sid:02X}",
            "service_name": service_names[request_sid]
        })
    else:
        result.update({
            "response_type": "REQUEST_OR_UNCLASSIFIED",
            "service_name": service_names.get(sid, "UNKNOWN")
        })
    if sid in (0x22, 0x2E, 0x2F) and len(payload) >= 3:
        result["did"] = f"0x{payload[1]:02X}{payload[2]:02X}"
    if sid in (0x62, 0x6E, 0x6F) and len(payload) >= 3:
        result["did"] = f"0x{payload[1]:02X}{payload[2]:02X}"
    if sid in (0x10, 0x11, 0x27, 0x28, 0x31, 0x3E) and len(payload) >= 2:
        result["sub_function"] = f"0x{payload[1]:02X}"
    return result



def process_isotp_frame_data(
    can_id: int,
    payload: bytes,
    relative_time: float,
    sessions: list[dict],
    active: dict[int, dict],
    tp_ids: set[int],
    max_payload_bytes: int = 4095,
) -> None:
    """ISO-TP 단일/다중 프레임을 조립하고 완료된 세션을 sessions 에 추가한다."""
    if tp_ids and can_id not in tp_ids:
        return
    if not payload:
        return
    frame_type = payload[0] >> 4
    if frame_type not in (0, 1, 2, 3):
        return
    if frame_type == 0:
        length = payload[0] & 0x0F
        if length == 0 or length > len(payload) - 1:
            return
        body = payload[1:1 + length]
        sessions.append({
            "protocol": "ISO-TP", "can_id": f"0x{can_id:X}",
            "start_time_sec": round(relative_time, 6), "end_time_sec": round(relative_time, 6),
            "frame_count": 1, "payload_length": len(body), "status": "COMPLETE",
            "payload_hex": body.hex(" ").upper(), "uds": decode_uds_payload(body),
        })
    elif frame_type == 1:
        if len(payload) < 2:
            return
        total_length = ((payload[0] & 0x0F) << 8) | payload[1]
        if total_length <= 7 or total_length > max_payload_bytes:
            return
        active[can_id] = {
            "start": relative_time, "total_length": total_length,
            "payload": bytearray(payload[2:]), "frame_count": 1,
            "next_sequence": 1, "issues": [], "flow_control": [],
        }
    elif frame_type == 2:
        state = active.get(can_id)
        if not state:
            return
        sequence = payload[0] & 0x0F
        if sequence != state["next_sequence"]:
            state["issues"].append(f"SEQUENCE_MISMATCH expected={state['next_sequence']} received={sequence}")
        state["next_sequence"] = (sequence + 1) & 0x0F
        state["payload"].extend(payload[1:])
        state["frame_count"] += 1
        if len(state["payload"]) >= state["total_length"]:
            body = bytes(state["payload"][:state["total_length"]])
            sessions.append({
                "protocol": "ISO-TP", "can_id": f"0x{can_id:X}",
                "start_time_sec": round(state["start"], 6), "end_time_sec": round(relative_time, 6),
                "duration_ms": round((relative_time - state["start"]) * 1000, 3),
                "frame_count": state["frame_count"], "payload_length": len(body),
                "status": "COMPLETE" if not state["issues"] else "COMPLETE_WITH_ISSUES",
                "issues": state["issues"], "payload_hex": body.hex(" ").upper(),
                "uds": decode_uds_payload(body),
            })
            del active[can_id]
    elif frame_type == 3:
        flow_status = payload[0] & 0x0F
        sessions.append({
            "protocol": "ISO-TP", "can_id": f"0x{can_id:X}",
            "start_time_sec": round(relative_time, 6), "end_time_sec": round(relative_time, 6),
            "frame_count": 1, "status": "FLOW_CONTROL",
            "flow_status": {0: "CONTINUE", 1: "WAIT", 2: "OVERFLOW"}.get(flow_status, "UNKNOWN"),
            "block_size": payload[1] if len(payload) > 1 else None,
            "st_min_raw": payload[2] if len(payload) > 2 else None,
        })


def finalize_incomplete_tp_sessions(active_tp_sessions: dict[int, dict], tp_sessions: list[dict]) -> None:
    """종료되지 않은 ISO-TP 다중 프레임 세션을 INCOMPLETE 상태로 마감한다."""
    for can_id, state in active_tp_sessions.items():
        payload = bytes(state["payload"][:state["total_length"]])
        tp_sessions.append({
            "protocol": "ISO-TP", "can_id": f"0x{can_id:X}",
            "start_time_sec": round(state["start"], 6), "end_time_sec": None,
            "frame_count": state["frame_count"],
            "expected_payload_length": state["total_length"],
            "received_payload_length": len(payload),
            "status": "INCOMPLETE", "issues": state["issues"] + ["MISSING_CONSECUTIVE_FRAME"],
            "payload_hex": payload.hex(" ").upper(),
            "uds": decode_uds_payload(payload),
        })


def filter_and_prioritize_blf_events(
    all_decoded_signal_events: list[dict],
    candidate_events: list[dict],
    always_keep_signals: set[str],
    event_limit: int,
) -> tuple[list[dict], list[dict], list[str], int]:
    """변화 없는 신호를 정리하고 우선순위에 따라 핵심 타임라인과 주요 발견 사항을 추출한다."""
    signal_value_sets: dict[tuple[str, str], set[str]] = {}
    signal_real_changes: dict[tuple[str, str], int] = {}
    for event in all_decoded_signal_events:
        sig_key = (event.get("message", ""), event.get("signal", ""))
        signal_value_sets.setdefault(sig_key, set()).add(str(event.get("to")))
        if event.get("from") != "UNOBSERVED" and str(event.get("from")) != str(event.get("to")):
            signal_real_changes[sig_key] = signal_real_changes.get(sig_key, 0) + 1
    changing_keys = {
        key for key, values in signal_value_sets.items()
        if len(values) > 1 or signal_real_changes.get(key, 0) > 0 or key[1] in always_keep_signals
    }
    no_change_removed = len(signal_value_sets) - len(changing_keys)
    filtered_all = [
        ev for ev in all_decoded_signal_events
        if (ev.get("message", ""), ev.get("signal", "")) in changing_keys
    ]
    filtered_candidates = [
        ev for ev in candidate_events
        if ev.get("event_type") != "signal_change" or (ev.get("message", ""), ev.get("signal", "")) in changing_keys
    ]
    prioritized = sorted(
        filtered_candidates,
        key=lambda item: (event_priority(item), item.get("time_sec", 0)),
    )[:event_limit]
    key_timeline = sorted(prioritized, key=lambda item: item.get("time_sec", 0))
    findings: list[str] = []
    for event in key_timeline:
        event_text = json.dumps(event, ensure_ascii=False).lower()
        if any(word in event_text for word in ("error", "fail", "timeout", "invalid", "fault")):
            if event.get("event_type") == "signal_change":
                findings.append(f"{event['time_sec']}s {event['signal']}: {event['from']} -> {event['to']}")
            else:
                findings.append(f"{event['time_sec']}s {event['can_id']} raw payload changed")
        if len(findings) >= 10:
            break
    return filtered_all, key_timeline, findings, no_change_removed
