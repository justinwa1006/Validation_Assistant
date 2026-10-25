from .core_runtime import *

try:
    from .core.json_tools import repair_common_json_errors as _core_repair_common_json_errors
    from .core.json_tools import extract_json_from_text as _core_extract_json_from_text
    from .core.result_schema import validate_ai_result_schema as _core_validate_ai_result_schema
    from .core.tc_review import build_rule_based_tc_review as _core_build_rule_based_tc_review
except ImportError:  # 패키지 밖에서 단독 실행하는 경우
    from core.json_tools import repair_common_json_errors as _core_repair_common_json_errors
    from core.json_tools import extract_json_from_text as _core_extract_json_from_text
    from core.result_schema import validate_ai_result_schema as _core_validate_ai_result_schema
    from core.tc_review import build_rule_based_tc_review as _core_build_rule_based_tc_review



class AiEngineMixin:
    def validate_result_by_mode(self, data):
            mode = self.mode.currentText()
            if "TC Generation" in mode:
                if isinstance(data, list):
                    data = {"test_cases": data}
                errors = []
                cases = data.get("test_cases") if isinstance(data, dict) else None
                if not isinstance(cases, list) or not cases:
                    errors.append("test_cases 목록이 없거나 비어 있습니다.")
                else:
                    for index, item in enumerate(cases, 1):
                        if not isinstance(item, dict):
                            errors.append(f"{index}번째 TC가 JSON Object가 아닙니다.")
                            continue
                        # Legacy 단일 문자열도 새 배열 구조로 자동 변환한다.
                        if "preconditions" not in item:
                            legacy_precondition = item.get("precondition", "")
                            item["preconditions"] = [legacy_precondition] if legacy_precondition else []
                        if "expected_results" not in item:
                            legacy_expected = item.get("expected_result", "")
                            steps_count = len(item.get("steps", [])) if isinstance(item.get("steps"), list) else 0
                            item["expected_results"] = (
                                [legacy_expected] * max(steps_count, 1) if legacy_expected else []
                            )
                        for field in ("tc_id", "title", "preconditions", "steps", "expected_results"):
                            if field not in item or item.get(field) in (None, "", []):
                                errors.append(f"{index}번째 TC의 {field}가 비어 있습니다.")
                        for field in ("preconditions", "steps", "expected_results"):
                            if not isinstance(item.get(field, []), list):
                                errors.append(f"{index}번째 TC의 {field}는 배열이어야 합니다.")
                        if isinstance(item.get("steps"), list) and isinstance(item.get("expected_results"), list):
                            if len(item["steps"]) != len(item["expected_results"]):
                                errors.append(
                                    f"{index}번째 TC의 steps와 expected_results 항목 수가 다릅니다. "
                                    f"({len(item['steps'])} / {len(item['expected_results'])})"
                                )
                return not errors, errors, [], data
    
            if "TC Review" in mode:
                errors = []
                if not isinstance(data, dict):
                    return False, ["최상위 JSON은 Object여야 합니다."], [], {}
                reviews = data.get("reviewed_test_cases")
                if not isinstance(reviews, list) or not reviews:
                    errors.append("reviewed_test_cases 목록이 없거나 비어 있습니다.")
                else:
                    for index, item in enumerate(reviews, 1):
                        if not isinstance(item, dict):
                            errors.append(f"{index}번째 Review가 JSON Object가 아닙니다.")
                            continue
                        for field in ("tc_id", "review_result", "issues", "recommendations"):
                            if field not in item:
                                errors.append(f"{index}번째 Review에 {field}가 없습니다.")
                        for field in ("missing_conditions", "issues", "recommendations", "revised_steps"):
                            if field in item and not isinstance(item[field], list):
                                errors.append(f"{index}번째 Review의 {field}는 배열이어야 합니다.")
                if "review_summary" not in data:
                    data["review_summary"] = {}
                return not errors, errors, [], data
    
            return self.validate_ai_result_schema(data)

    def build_rule_based_tc_review(self, *args, **kwargs):
        return _core_build_rule_based_tc_review(*args, **kwargs)

    def display_structured_ai_result(self, data):
            current_level = self.prompt_level.currentText().strip().upper()
    
            is_basic = (current_level == "BASIC")
            is_detailed = (current_level == "DETAILED")
            is_expert = (current_level == "EXPERT")
    
            self.clear_structured_ai_result()
    
            result = str(data.get("result", "UNKNOWN")).upper()
            confidence = str(data.get("confidence", "UNKNOWN")).upper()
            requirement_id = str(data.get("requirement_id", "TBD"))
            tc_id = str(data.get("tc_id", "TBD"))
            risk = str(data.get("risk", "UNKNOWN")).upper()
    
            header = QGroupBox("🤖 AI Validation Result")
            header_layout = QGridLayout(header)
            header_layout.setSpacing(8)
    
            result_label = QLabel(
                f"RESULT\n{self.get_result_display_text(result)}"
            )
            result_label.setStyleSheet("""
                QLabel {
                    color: #173b4f;
                    background-color: #eef6f7;
                    font-size: 15pt;
                    font-weight: bold;
                    padding: 12px;
                    border: 1px solid #b8c5cf;
                    border-radius: 8px;
                }
            """)
    
            confidence_label = QLabel(f"CONFIDENCE\n{confidence}")
            confidence_label.setStyleSheet("""
                QLabel {
                    color: #173b4f;
                    background-color: #f4f8fa;
                    font-size: 11pt;
                    font-weight: bold;
                    padding: 12px;
                    border: 1px solid #b8c5cf;
                    border-radius: 8px;
                }
            """)
    
            risk_label = QLabel(f"RISK\n{risk}")
            risk_label.setStyleSheet("""
                QLabel {
                    color: #173b4f;
                    background-color: #f4f8fa;
                    font-size: 11pt;
                    font-weight: bold;
                    padding: 12px;
                    border: 1px solid #b8c5cf;
                    border-radius: 8px;
                }
            """)
    
            header_layout.addWidget(result_label, 0, 0)
            header_layout.addWidget(confidence_label, 0, 1)
            header_layout.addWidget(risk_label, 0, 2)
    
            header_layout.addWidget(
                QLabel(f"Requirement ID\n{requirement_id}"),
                1, 0
            )
            header_layout.addWidget(
                QLabel(f"TC ID\n{tc_id}"),
                1, 1
            )
    
            self.structured_result_layout.addWidget(header)
    
            self.add_result_section("Executive Summary", data.get("summary", ""))
            self.add_factor_section(
                "✅ PASS Factors",
                data.get("pass_factors", []),
                factor_type="PASS"
            )
            self.add_factor_section(
                "❌ FAIL Factors",
                data.get("fail_factors", []),
                factor_type="FAIL"
            )
    
            if is_detailed or is_expert:
                self.add_evidence_coverage_section(data.get("evidence_coverage", {}))
                self.add_confidence_reason_section(
                    data.get("confidence", "UNKNOWN"),
                    data.get("confidence_reason", [])
                )
                self.add_result_list_section("Observations", data.get("observations", []))
                self.add_result_list_section("Test Gap Analysis", data.get("gaps", []))
                self.add_result_list_section(
                    "Recommended Verification",
                    data.get("recommended_verification", [])
                )
    
            event_timeline = data.get("event_timeline", [])
            if is_expert or event_timeline:
                self.add_event_timeline_section(event_timeline)
    
            if is_expert:
                self.add_result_list_section("Potential Root Cause", data.get("root_cause", []))
    
            next_actions = data.get("next_actions", [])
            if is_expert or next_actions:
                self.add_next_actions_section(next_actions)
    
            self.structured_result_layout.addStretch()

    def add_evidence_coverage_section(self, evidence_coverage):
            if not isinstance(evidence_coverage, dict):
                evidence_coverage = {}
    
            required_items = evidence_coverage.get("required_items", 0)
            verified_items = evidence_coverage.get("verified_items", 0)
            coverage_percent = evidence_coverage.get("coverage_percent", 0)
            missing_items = evidence_coverage.get("missing_items", [])
    
            try:
                required_items = int(required_items)
            except (TypeError, ValueError):
                required_items = 0
    
            try:
                verified_items = int(verified_items)
            except (TypeError, ValueError):
                verified_items = 0
    
            try:
                coverage_percent = int(coverage_percent)
            except (TypeError, ValueError):
                coverage_percent = 0
    
            coverage_percent = max(0, min(coverage_percent, 100))
    
            if isinstance(missing_items, str):
                missing_items = [missing_items]
            elif not isinstance(missing_items, list):
                missing_items = []
    
            group = QGroupBox("📊 Evidence Coverage")
            layout = QVBoxLayout(group)
    
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(coverage_percent)
            progress_bar.setFormat("%p%")
            progress_bar.setMinimumHeight(28)
            progress_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #edf3f6;
                    color: #263746;
                    border: 1px solid #b8c5cf;
                    border-radius: 7px;
                    text-align: center;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #16858a;
                    border-radius: 6px;
                }
            """)
            layout.addWidget(progress_bar)
    
            count_label = QLabel(f"Verified {verified_items} / Required {required_items}")
            count_label.setAlignment(Qt.AlignCenter)
            count_label.setStyleSheet("""
                QLabel {
                    color: #405866;
                    padding: 6px;
                    font-weight: bold;
                }
            """)
            layout.addWidget(count_label)
    
            if missing_items:
                missing_title = QLabel("Missing Evidence")
                missing_title.setStyleSheet("""
                    QLabel {
                        color: #f59e0b;
                        font-weight: bold;
                        padding-top: 6px;
                    }
                """)
                layout.addWidget(missing_title)
    
                for index, item in enumerate(missing_items, start=1):
                    item_text = (
                        item.get("description") or item.get("item") or str(item)
                        if isinstance(item, dict) else str(item)
                    )
    
                    item_label = QLabel(f"{index}. {item_text}")
                    item_label.setWordWrap(True)
                    item_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    item_label.setStyleSheet("""
                        QLabel {
                            color: #263746;
                            padding: 3px 8px;
                        }
                    """)
                    layout.addWidget(item_label)
            else:
                no_missing_label = QLabel("누락된 Evidence가 없습니다.")
                no_missing_label.setStyleSheet("""
                    QLabel {
                        color: #22c55e;
                        padding: 6px;
                    }
                """)
                layout.addWidget(no_missing_label)
    
            self.structured_result_layout.addWidget(group)

    def add_result_section(self, title, content):
            if content is None:
                content = ""
    
            content = str(content).strip() or "내용 없음"
    
            group = QGroupBox(title)
            layout = QVBoxLayout(group)
    
            label = QLabel(content)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setStyleSheet("""
                QLabel {
                    color: #263746;
                    padding: 8px;
                }
            """)
            layout.addWidget(label)
    
            self.structured_result_layout.addWidget(group)

    def add_result_list_section(self, title, items):
            if items is None:
                items = []
    
            if isinstance(items, str):
                items = [items]
    
            group = QGroupBox(title)
            layout = QVBoxLayout(group)
    
            if not items:
                label = QLabel("내용 없음")
                label.setStyleSheet("""
                    QLabel {
                        color: #687d8a;
                        padding: 8px;
                    }
                """)
                layout.addWidget(label)
            else:
                for index, item in enumerate(items, start=1):
                    label = QLabel(f"{index}. {item}")
                    label.setWordWrap(True)
                    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    label.setStyleSheet("""
                        QLabel {
                            color: #263746;
                            padding: 5px;
                        }
                    """)
                    layout.addWidget(label)
    
            self.structured_result_layout.addWidget(group)

    def add_factor_section(self, title, items, factor_type="PASS"):
            if items is None:
                items = []
    
            if isinstance(items, str):
                items = [items]
    
            if not isinstance(items, list):
                items = []
    
            factor_type = str(factor_type).strip().upper()
    
            style_mapping = {
                "PASS": {
                    "icon": "✅",
                    "title_color": "#167a43",
                    "border_color": "#78bd91",
                    "background_color": "#eaf7ef"
                },
                "FAIL": {
                    "icon": "❌",
                    "title_color": "#b4232c",
                    "border_color": "#e3a0a5",
                    "background_color": "#fff0f1"
                },
                "INFO": {
                    "icon": "ℹ️",
                    "title_color": "#176b87",
                    "border_color": "#91b9d7",
                    "background_color": "#edf5fb"
                }
            }
    
            selected_style = style_mapping.get(factor_type, style_mapping["INFO"])
    
            group = QGroupBox(title)
            group.setStyleSheet(f"""
                QGroupBox {{
                    color: {selected_style["title_color"]};
                    background-color: {selected_style["background_color"]};
                    border: 1px solid {selected_style["border_color"]};
                    border-radius: 8px;
                    margin-top: 12px;
                    padding-top: 12px;
                    font-weight: bold;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 5px;
                }}
            """)
    
            layout = QVBoxLayout(group)
            layout.setContentsMargins(12, 16, 12, 12)
            layout.setSpacing(5)
    
            if not items:
                empty_message = "확인된 실패 요인이 없습니다." if factor_type == "FAIL" else "확인된 통과 요인이 없습니다."
                label = QLabel(empty_message)
                label.setStyleSheet("""
                    QLabel {
                        color: #687d8a;
                        padding: 6px;
                        font-weight: normal;
                    }
                """)
                layout.addWidget(label)
            else:
                for item in items:
                    item_text = (
                        item.get("factor") or item.get("description") or item.get("reason") or str(item)
                        if isinstance(item, dict) else str(item)
                    ).strip()
    
                    if not item_text:
                        continue
    
                    label = QLabel(f'{selected_style["icon"]} {item_text}')
                    label.setWordWrap(True)
                    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    label.setStyleSheet("""
                        QLabel {
                            color: #263746;
                            padding: 5px 8px;
                            font-weight: normal;
                        }
                    """)
                    layout.addWidget(label)
    
            self.structured_result_layout.addWidget(group)

    def add_confidence_reason_section(self, confidence, reasons):
            if reasons is None:
                reasons = []
    
            if isinstance(reasons, str):
                reasons = [reasons]
    
            if not isinstance(reasons, list):
                reasons = []
    
            confidence = str(confidence).strip().upper()
            confidence_colors = {
                "HIGH": "#167a43",
                "MEDIUM": "#9a6500",
                "LOW": "#b4232c",
                "UNKNOWN": "#5f7480"
            }
            confidence_color = confidence_colors.get(confidence, "#687d8a")
    
            group = QGroupBox("🧠 Confidence Reason")
            layout = QVBoxLayout(group)
            layout.setContentsMargins(12, 16, 12, 12)
    
            confidence_label = QLabel(f"AI Confidence: {confidence}")
            confidence_label.setStyleSheet(f"""
                QLabel {{
                    color: {confidence_color};
                    background-color: #f3f7f9;
                    border: 1px solid #b8c5cf;
                    border-radius: 6px;
                    padding: 8px;
                    font-weight: bold;
                }}
            """)
            layout.addWidget(confidence_label)
    
            if not reasons:
                empty_label = QLabel("Confidence 판단 근거가 제공되지 않았습니다.")
                empty_label.setWordWrap(True)
                empty_label.setStyleSheet("""
                    QLabel {
                        color: #687d8a;
                        padding: 8px;
                    }
                """)
                layout.addWidget(empty_label)
            else:
                for index, reason in enumerate(reasons, start=1):
                    reason_text = (
                        reason.get("reason") or reason.get("description") or str(reason)
                        if isinstance(reason, dict) else str(reason)
                    ).strip()
    
                    if not reason_text:
                        continue
    
                    label = QLabel(f"{index}. {reason_text}")
                    label.setWordWrap(True)
                    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    label.setStyleSheet("""
                        QLabel {
                            color: #263746;
                            padding: 5px 8px;
                        }
                    """)
                    layout.addWidget(label)
    
            self.structured_result_layout.addWidget(group)

    def get_timeline_status_style(self, status):
            status = str(status).strip().upper()
            style_mapping = {
                "VERIFIED": {"icon": "✅", "color": "#22c55e", "border": "#78bd91"},
                "PARTIAL": {"icon": "⚠️", "color": "#f59e0b", "border": "#92400e"},
                "FAILED": {"icon": "❌", "color": "#ef4444", "border": "#e3a0a5"},
                "MISSING": {"icon": "⭕", "color": "#f97316", "border": "#e4b084"},
                "UNKNOWN": {"icon": "❓", "color": "#687d8a", "border": "#aebbc4"}
            }
            return style_mapping.get(status, style_mapping["UNKNOWN"])

    def get_action_priority_style(self, priority):
            styles = {
                "CRITICAL": {"icon": "🔴", "color": "#f87171", "border": "#991b1b", "background": "#fff0f1"},
                "HIGH": {"icon": "🟠", "color": "#fb923c", "border": "#e4b084", "background": "#fff4ea"},
                "MEDIUM": {"icon": "🟡", "color": "#facc15", "border": "#d7bd6f", "background": "#fff9e8"},
                "LOW": {"icon": "🟢", "color": "#4ade80", "border": "#78bd91", "background": "#eaf7ef"},
                "UNKNOWN": {"icon": "⚪", "color": "#687d8a", "border": "#aebbc4", "background": "#f1f4f6"}
            }
            return styles.get(str(priority).strip().upper(), styles["UNKNOWN"])

    def get_action_status_display(self, status):
            displays = {
                "OPEN": {"text": "OPEN", "color": "#38bdf8"},
                "IN_PROGRESS": {"text": "IN PROGRESS", "color": "#f59e0b"},
                "BLOCKED": {"text": "BLOCKED", "color": "#ef4444"},
                "COMPLETED": {"text": "COMPLETED", "color": "#22c55e"},
                "CANCELLED": {"text": "CANCELLED", "color": "#687d8a"},
                "UNKNOWN": {"text": "UNKNOWN", "color": "#687d8a"}
            }
            status = str(status).strip().upper().replace(" ", "_").replace("-", "_")
            return displays.get(status, displays["UNKNOWN"])

    def add_next_actions_section(self, action_items):
            if action_items is None:
                action_items = []
    
            if isinstance(action_items, str):
                action_items = [action_items]
    
            if not isinstance(action_items, list):
                action_items = []
    
            normalized_items = []
    
            for item in action_items:
                if isinstance(item, str):
                    action_text = item.strip()
                    if not action_text:
                        continue
                    normalized_items.append({
                        "priority": "UNKNOWN",
                        "action": action_text,
                        "owner": "TBD",
                        "status": "OPEN"
                    })
                elif isinstance(item, dict):
                    normalized_items.append(item)
    
            group = QGroupBox("📌 Next Actions")
            main_layout = QVBoxLayout(group)
            main_layout.setContentsMargins(12, 16, 12, 12)
            main_layout.setSpacing(8)
    
            if not normalized_items:
                empty_label = QLabel("추가로 수행할 Next Action이 없습니다.")
                empty_label.setWordWrap(True)
                empty_label.setStyleSheet("""
                    QLabel {
                        color: #687d8a;
                        padding: 8px;
                    }
                """)
                main_layout.addWidget(empty_label)
                self.structured_result_layout.addWidget(group)
                return
    
            priority_order = {
                "CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4
            }
            normalized_items.sort(
                key=lambda x: priority_order.get(str(x.get("priority", "UNKNOWN")).strip().upper(), 4)
            )
    
            for item in normalized_items:
                priority = str(item.get("priority", "UNKNOWN")).strip().upper()
                action = str(item.get("action", "TBD")).strip() or "TBD"
                owner = str(item.get("owner", "TBD")).strip() or "TBD"
                status = str(item.get("status", "OPEN")).strip().upper()
    
                priority_style = self.get_action_priority_style(priority)
                status_display = self.get_action_status_display(status)
    
                card = QGroupBox()
                card.setStyleSheet(f"""
                    QGroupBox {{
                        background-color: {priority_style["background"]};
                        border: 1px solid {priority_style["border"]};
                        border-radius: 8px;
                        padding: 8px;
                    }}
                """)
    
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(10, 8, 10, 8)
                card_layout.setSpacing(6)
    
                title_label = QLabel(f'{priority_style["icon"]} {priority} | {action}')
                title_label.setWordWrap(True)
                title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                title_label.setStyleSheet(f"""
                    QLabel {{
                        color: {priority_style["color"]};
                        border: none;
                        font-weight: bold;
                        font-size: 10pt;
                        padding: 2px;
                    }}
                """)
                card_layout.addWidget(title_label)
    
                detail_layout = QHBoxLayout()
    
                owner_label = QLabel(f"Owner: {owner}")
                owner_label.setWordWrap(True)
                owner_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                owner_label.setStyleSheet("""
                    QLabel {
                        color: #405866;
                        border: none;
                        padding: 4px;
                    }
                """)
    
                status_label = QLabel(f'Status: {status_display["text"]}')
                status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                status_label.setStyleSheet(f"""
                    QLabel {{
                        color: {status_display["color"]};
                        background-color: #f3f7f9;
                        border: 1px solid #b8c5cf;
                        border-radius: 5px;
                        padding: 4px 8px;
                        font-weight: bold;
                    }}
                """)
    
                detail_layout.addWidget(owner_label, 1)
                detail_layout.addWidget(status_label)
    
                card_layout.addLayout(detail_layout)
                main_layout.addWidget(card)
    
            self.structured_result_layout.addWidget(group)

    def add_event_timeline_section(self, timeline_items):
            if timeline_items is None:
                timeline_items = []
    
            if isinstance(timeline_items, str):
                timeline_items = [{
                    "order": 1,
                    "event": timeline_items,
                    "status": "UNKNOWN",
                    "evidence": "TBD",
                    "timestamp": "TBD",
                    "timestamp_type": "TBD"
                }]
    
            if not isinstance(timeline_items, list):
                timeline_items = []
    
            group = QGroupBox("🕒 Event Timeline")
            main_layout = QVBoxLayout(group)
            main_layout.setContentsMargins(12, 16, 12, 12)
            main_layout.setSpacing(6)
    
            if not timeline_items:
                empty_label = QLabel("확인된 Event Timeline이 없습니다.")
                empty_label.setStyleSheet("""
                    QLabel {
                        color: #687d8a;
                        padding: 8px;
                    }
                """)
                main_layout.addWidget(empty_label)
                self.structured_result_layout.addWidget(group)
                return
    
            sorted_items = sorted(
                timeline_items,
                key=lambda x: (x.get("order", 9999) if isinstance(x, dict) else 9999)
            )
    
            for position, item in enumerate(sorted_items):
                if not isinstance(item, dict):
                    continue
    
                order = item.get("order", position + 1)
                event = str(item.get("event", "TBD")).strip()
                status = str(item.get("status", "UNKNOWN")).strip().upper()
                evidence = str(item.get("evidence", "TBD")).strip()
                timestamp = str(item.get("timestamp", "TBD")).strip()
                timestamp_type = str(item.get("timestamp_type", "TBD")).strip().upper()
    
                allowed_types = {"EVENT_TIME", "OBSERVED_TIME", "TBD"}
                if timestamp_type not in allowed_types:
                    timestamp_type = "TBD"
    
                if timestamp.upper() == "TBD":
                    timestamp_type = "TBD"
                elif timestamp_type == "TBD":
                    timestamp_type = "OBSERVED_TIME"
    
                status_style = self.get_timeline_status_style(status)
    
                event_card = QWidget()
                event_card.setStyleSheet(f"""
                    QWidget {{
                        background-color: #f3f7f9;
                        border: 1px solid {status_style["border"]};
                        border-radius: 8px;
                    }}
                """)
    
                event_layout = QVBoxLayout(event_card)
                event_layout.setContentsMargins(12, 10, 12, 10)
                event_layout.setSpacing(5)
    
                title_label = QLabel(f'{status_style["icon"]} {order}. {event}')
                title_label.setWordWrap(True)
                title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                title_label.setStyleSheet(f"""
                    QLabel {{
                        color: {status_style["color"]};
                        border: none;
                        font-weight: bold;
                        font-size: 10pt;
                    }}
                """)
                event_layout.addWidget(title_label)
    
                detail_label = QLabel(
                    f"Status: {status}\n"
                    f"Timestamp: {timestamp}\n"
                    f"Time Type: {timestamp_type}\n"
                    f"Evidence: {evidence}"
                )
                detail_label.setWordWrap(True)
                detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                detail_label.setStyleSheet("""
                    QLabel {
                        color: #405866;
                        border: none;
                        padding-left: 22px;
                    }
                """)
                event_layout.addWidget(detail_label)
    
                main_layout.addWidget(event_card)
    
                if position < len(sorted_items) - 1:
                    connector = QLabel("↓")
                    connector.setAlignment(Qt.AlignCenter)
                    connector.setStyleSheet("""
                        QLabel {
                            color: #78909d;
                            border: none;
                            font-size: 16pt;
                            font-weight: bold;
                        }
                    """)
                    main_layout.addWidget(connector)
    
            self.structured_result_layout.addWidget(group)

    def get_result_display_text(self, result):
            result = str(result).strip().upper()
            mapping = {
                "PASS": "✅ PASS",
                "FAIL": "❌ FAIL",
                "PARTIAL": "⚠️ PARTIAL",
                "INCONCLUSIVE": "❓ INCONCLUSIVE",
                "EVIDENCE INSUFFICIENT": "⚠️ EVIDENCE INSUFFICIENT",
                "UNKNOWN": "❓ UNKNOWN"
            }
            return mapping.get(result, f"❓ {result}")

    def clear_structured_ai_result(self):
            if not hasattr(self, "structured_result_layout"):
                return
    
            while self.structured_result_layout.count():
                item = self.structured_result_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

    def clear_ai_result(self):
            self.ai_result.clear()
            self.current_ai_result_data = {}
            self.clear_structured_ai_result()

    def import_ai_result(self):
            file_name, _ = QFileDialog.getOpenFileName(
                self,
                "Import AI Analysis Result",
                "",
                "Result Files (*.json *.txt);;JSON Files (*.json);;Text Files (*.txt);;All Files (*.*)"
            )
    
            if not file_name:
                return
    
            try:
                with open(file_name, "r", encoding="utf-8-sig") as file:
                    file_content = file.read().strip()
    
                if not file_content:
                    QMessageBox.warning(self, "Import Result", "선택한 파일에 결과 내용이 없습니다.")
                    return
    
                if file_name.lower().endswith(".json"):
                    if file_content.startswith("```json"):
                        file_content = file_content[7:].strip()
                    elif file_content.startswith("```"):
                        file_content = file_content[3:].strip()
    
                    if file_content.endswith("```"):
                        file_content = file_content[:-3].strip()
    
                    result_data = json.loads(file_content)
    
                    if not self.apply_ai_result_data(result_data):
                        QMessageBox.warning(
                            self,
                            "JSON Format Error",
                            "JSON 최상위 구조는 Object여야 합니다."
                        )
                        return
                else:
                    self.ai_result.setPlainText(file_content)
                    self.current_ai_result_data = {}
                    self.clear_structured_ai_result()
    
                QMessageBox.information(
                    self,
                    "Import Complete",
                    f"AI 분석 결과를 불러왔습니다.\n\n{os.path.basename(file_name)}"
                )
    
            except json.JSONDecodeError as error:
                QMessageBox.warning(
                    self,
                    "JSON Format Error",
                    f"JSON 형식이 올바르지 않습니다.\n\n{error}"
                )
            except Exception as error:
                QMessageBox.critical(
                    self,
                    "Import Result Error",
                    f"AI 분석 결과 파일을 불러오는 중 오류가 발생했습니다.\n\n{type(error).__name__}: {error}"
                )

    def paste_and_save_json(self):
            clipboard_text = QApplication.clipboard().text().strip()
    
            if not clipboard_text:
                QMessageBox.warning(self, "Save JSON", "클립보드에 저장할 내용이 없습니다.")
                return
    
            json_text = self.extract_json_from_text(clipboard_text)
    
            if not json_text:
                QMessageBox.warning(
                    self,
                    "JSON Not Found",
                    "클립보드 내용에서 유효한 JSON을 찾지 못했습니다.\n\nAI의 JSON 결과를 복사했는지 확인하세요."
                )
                return
    
            try:
                result_data = json.loads(json_text)
            except json.JSONDecodeError as error:
                QMessageBox.warning(
                    self,
                    "JSON Format Error",
                    f"JSON 형식이 올바르지 않습니다.\n\n{error}"
                )
                return
    
            if not self.apply_ai_result_data(result_data):
                return
    
            result_data = self.current_ai_result_data
    
            tc_name = self.tc.text().strip() or "Validation_Result"
            invalid_chars = '<>:"/\\|?*'
            safe_file_name = "".join(
                "_" if c in invalid_chars else c
                for c in tc_name
            ).strip().rstrip(". ")
    
            if not safe_file_name:
                safe_file_name = "Validation_Result"
    
            file_name = f"{safe_file_name}_result.json"
    
            default_path = os.path.join(
                os.path.expanduser("~"),
                "Desktop",
                file_name
            )
    
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save AI Result JSON",
                default_path,
                "JSON Files (*.json);;All Files (*.*)"
            )
    
            if not file_path:
                return
    
            if not file_path.lower().endswith(".json"):
                file_path += ".json"
    
            base_path = file_path
            counter = 2
    
            while os.path.exists(file_path):
                name_without_ext = os.path.splitext(base_path)[0]
                file_path = f"{name_without_ext}_{counter}.json"
                counter += 1
    
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(result_data, file, ensure_ascii=False, indent=4)
    
                QMessageBox.information(
                    self,
                    "JSON Saved",
                    f"AI 분석 결과가 JSON 파일로 저장되었습니다.\n\n{file_path}"
                )
            except Exception as error:
                QMessageBox.critical(
                    self,
                    "JSON Save Error",
                    f"JSON 파일 저장 중 오류가 발생했습니다.\n\n{type(error).__name__}: {error}"
                )

    def validate_ai_result_schema(self, *args, **kwargs):
        return _core_validate_ai_result_schema(*args, **kwargs)

    def apply_ai_result_data(self, result_data, show_warning=True):
            """
            현재 선택된 Mode에 맞게 AI JSON 결과를 검증하고 저장한다.
            """
    
            mode = self.mode.currentText()
    
            # 모든 모드의 최상위 JSON은 Object여야 함
            if isinstance(result_data, list) and "TC Generation" in mode:
                result_data = {"test_cases": result_data}
            if not isinstance(result_data, dict):
                if show_warning:
                    QMessageBox.warning(self, "JSON Format Error", "JSON 최상위 구조는 Object여야 합니다.")
                return False
    
            # =================================================
            # 1. TC Generation
            # =================================================
            if "TC Generation" in mode:
                is_valid, errors, warnings, normalized_data = (self.validate_result_by_mode(result_data))
    
                if not is_valid:
                    if show_warning:
                        QMessageBox.warning(self, "TC Generation JSON 오류", "\n".join(errors))
                    return False
    
                self.current_ai_result_data = normalized_data
                self.apply_signal_mapping_to_tc()
                if self.dbc_file_paths:
                    self.apply_dbc_combined_autocorrection(show_message=False)
                    normalized_data = self.current_ai_result_data
    
                self.ai_result.setPlainText(
                    json.dumps(normalized_data, ensure_ascii=False, indent=4))
    
                self.clear_structured_ai_result()
    
                if warnings and show_warning:
                    QMessageBox.information(self, "JSON 처리 안내", "\n".join(warnings))
    
                if (
                    show_warning
                    and hasattr(self, "auto_tc_review")
                    and self.auto_tc_review.isChecked()
                ):
                    self.prepare_generated_tc_auto_review(normalized_data)
    
                return True
    
            # =================================================
            # 2. TC Review
            # =================================================
            if "TC Review" in mode:
                is_valid, errors, warnings, normalized_data = (self.validate_result_by_mode(result_data))
    
                if not is_valid:
                    if show_warning:
                        QMessageBox.warning(self, "TC Review JSON 오류","\n".join(errors))
                    return False
    
                self.current_ai_result_data = normalized_data
    
                self.ai_result.setPlainText(json.dumps(normalized_data,ensure_ascii=False,indent=4))
    
                # TC Review는 Validation Analysis 전용 구조화 UI를 사용하지 않음
                self.clear_structured_ai_result()
    
                if warnings and show_warning:
                    QMessageBox.information(self, "JSON 처리 안내", "\n".join(warnings))
    
                return True
    
            # =================================================
            # 3. Validation Analysis
            # =================================================
            is_valid, errors, warnings, normalized_data = (
                self.validate_ai_result_schema(result_data)
            )
    
            if not is_valid:
                if show_warning:
                    QMessageBox.warning(self, "Validation JSON 오류", "\n".join(errors))
                return False
    
            self.current_ai_result_data = normalized_data
    
            self.ai_result.setPlainText(
                json.dumps(normalized_data, ensure_ascii=False, indent=4))
    
            self.display_structured_ai_result(normalized_data)
    
            if warnings and show_warning:
                QMessageBox.information(self,"JSON 처리 안내","\n".join(warnings))
    
            return True

    def extract_json_from_text(self, *args, **kwargs):
        return _core_extract_json_from_text(*args, **kwargs)

    def repair_common_json_errors(self, *args, **kwargs):
        return _core_repair_common_json_errors(*args, **kwargs)

    def paste_ai_result(self):
            clipboard_text = (
                QApplication.clipboard().text().strip()
            )
            clipboard_text = self.restore_tc_generation_light_aliases(clipboard_text)
    
            if not clipboard_text:
                QMessageBox.warning(self, "Paste Result", "클립보드에 붙여넣을 텍스트가 없습니다.")
                return
    
            json_text = self.extract_json_from_text(clipboard_text)
    
            if not json_text:
                repaired_text = self.repair_common_json_errors(clipboard_text)
    
                json_text = self.extract_json_from_text(repaired_text)
    
            if json_text:
                try:
                    result_data = json.loads(json_text)
    
                    if self.apply_ai_result_data(result_data):
                        QMessageBox.information(self, "Paste Complete", "JSON 결과를 정상적으로 처리했습니다.")
                        return
    
                except json.JSONDecodeError as error:
                    QMessageBox.warning(
                        self,
                        "JSON Format Error",
                        f"JSON을 처리할 수 없습니다.\n\n"
                        f"{error}\n\n"
                        f"오류 위치: {error.lineno}행 "
                        f"{error.colno}열"
                    )
                    return
    
            self.ai_result.setPlainText(clipboard_text)
            self.current_ai_result_data = {}
            self.clear_structured_ai_result()
    
            QMessageBox.warning(
                self,
                "JSON Not Found",
                "응답에서 유효한 JSON을 찾지 못했습니다."
            )

    def set_gemini_button_busy(self, is_busy):
            for btn_name in ("gemini_analyze_btn", "u_gemini_btn"):
                btn = getattr(self, btn_name, None)
                if btn is not None:
                    btn.setEnabled(not is_busy)
                    if btn_name == "u_gemini_btn":
                        btn.setText("✦ Gemini 실행 중..." if is_busy else "✦ Gemini API 실행")
                    else:
                        btn.setText("✦  Gemini 분석 중..." if is_busy else "✦  Gemini Analysis")

    def request_gemini_analysis(self):
            if not ENABLE_GEMINI:
                QMessageBox.information(self, "Gemini Disabled", "이 배포본에서는 Gemini API 기능이 비활성화되어 있습니다.")
                return
            if hasattr(self, "gemini_worker") and self.gemini_worker.isRunning():
                return
            if genai is None:
                QMessageBox.warning(
                    self, "패키지 확인",
                    "google-genai 패키지가 필요합니다.\n\n설치 명령:\npip install google-genai",
                )
                return
            if not get_gemini_api_key():
                QMessageBox.warning(
                    self, "API Key 확인",
                    "GEMINI_API_KEY가 설정되지 않았습니다.\n프로그램 폴더의 .env 또는 Try_API.env 파일에 GEMINI_API_KEY를 설정하세요.",
                )
                return
            self.generated_prompt = ""
            self.generate_prompt()
            api_prompt = self.generated_prompt
            if not api_prompt:
                return
            api_prompt += "\n\n중요: 최종 응답에는 유효한 JSON Object를 반드시 포함하고, JSON 뒤에는 설명을 추가하지 마라."
            active_model = get_gemini_model()
            status_msg = f"Gemini ({active_model}) 모델이 {self.mode.currentText()} 작업을 처리 중입니다..."
            self.ai_result.setPlainText(status_msg)
            if hasattr(self, "_u_sync_current_mode_only"):
                self._u_sync_current_mode_only()
            self.current_ai_result_data = {}
            self.set_gemini_button_busy(True)
            self.gemini_worker = GeminiWorker(api_prompt, self.attachments)
            self.gemini_worker.finished.connect(self.handle_gemini_result)
            self.gemini_worker.failed.connect(self.handle_gemini_error)
            self.gemini_worker.start()

    def handle_gemini_result(self, response_text):
            try:
                restored_text = self.restore_tc_generation_light_aliases(response_text)
                json_text = self.extract_json_from_text(restored_text)
                if not json_text:
                    repaired = self.repair_common_json_errors(restored_text)
                    json_text = self.extract_json_from_text(repaired)
                if not json_text:
                    raise ValueError("Gemini 응답에서 JSON을 찾지 못했습니다.")
                result_data = json.loads(json_text)
                if not self.apply_ai_result_data(result_data):
                    self.ai_result.setPlainText(restored_text)
                    return
                if hasattr(self, "_u_sync_current_mode_only"):
                    self._u_sync_current_mode_only()
                QMessageBox.information(
                    self, "Gemini Complete",
                    f"{self.mode.currentText()} 결과가 정상 처리되었습니다.\nExport XLSX로 저장할 수 있습니다.",
                )
            except (json.JSONDecodeError, ValueError) as error:
                self.ai_result.setPlainText(response_text)
                self.current_ai_result_data = {}
                self.clear_structured_ai_result()
                if hasattr(self, "_u_sync_current_mode_only"):
                    self._u_sync_current_mode_only()
                QMessageBox.warning(self, "Gemini Result Error", str(error))
            finally:
                self.set_gemini_button_busy(False)

    def handle_gemini_error(self, error_message):
            self.ai_result.setPlainText(f"Gemini 분석에 실패했습니다.\n\n{error_message}")
            if hasattr(self, "_u_sync_current_mode_only"):
                self._u_sync_current_mode_only()
            self.set_gemini_button_busy(False)
            QMessageBox.critical(
                self,
                "Gemini API Error",
                f"Gemini 분석에 실패했습니다.\n\n{error_message}",
            )


