"""
tc_engine.py - Automotive & General SW Validation Assistant Prompt & Execution Engine
Refactored to 100-Point Prompt Architecture (Multi-Domain Dynamic Few-Shot & Light Mask Protected)

[Revision] 도메인 레지스트리 기반 프롬프트 분기 + 버그 수정판
 - System Instruction / Few-Shot(Generation, Analysis) / Level Scope 를 도메인별로 분기
 - 프로필(current_domain_profile)에 key / few_shot / level_scope 를 넣으면 코드 수정 없이 덮어쓰기 가능
 - Light Mask 별칭 충돌, optimize_prompt_text 의 JSON 스키마 손상, Hex/단위 비교 오류 등 수정
"""

from __future__ import annotations
import json
import re
import textwrap
import hashlib
import math
import os
from collections import Counter
from typing import Dict, Any, List, Tuple, Optional
from PySide6.QtWidgets import QMessageBox, QApplication, QTextEdit
from PySide6.QtGui import QTextCursor, QPixmap, QTextImageFormat, QTextDocument
from PySide6.QtCore import Qt, QUrl

try:
    from .core.templating import fill_template
    from .core.prompt_builder import build_tc_review_prompt, build_validation_analysis_prompt
except ImportError:  # 패키지 밖에서 단독 실행하는 경우
    from core.templating import fill_template
    from core.prompt_builder import build_tc_review_prompt, build_validation_analysis_prompt

# ==============================================================================
# 1. 100점 프롬프트 아키텍처 핵심 상수 (System Instruction & Domain Few-Shots)
# ==============================================================================

try:
    from .prompt_data import (
        SYSTEM_BASE_INSTRUCTION,
        DEFAULT_DOMAIN_KEY,
        DOMAIN_SYSTEM_ADDENDUM,
        FEW_SHOTS,
        LEVEL_SCOPE_COMMON,
        DOMAIN_LEVEL_EXTRA,
        DOMAIN_DEFAULTS,
        SEQUENCE_MODE_RULES,
        _DOMAIN_NAME_PATTERNS,
        MAX_PROMPT_CHARS,
        PROMPT_BUDGETS,
        BLF_EXTRA_PROMPT_CHARS,
    )
except ImportError:  # 패키지 밖에서 단독 실행하는 경우
    from prompt_data import (
        SYSTEM_BASE_INSTRUCTION,
        DEFAULT_DOMAIN_KEY,
        DOMAIN_SYSTEM_ADDENDUM,
        FEW_SHOTS,
        LEVEL_SCOPE_COMMON,
        DOMAIN_LEVEL_EXTRA,
        DOMAIN_DEFAULTS,
        SEQUENCE_MODE_RULES,
        _DOMAIN_NAME_PATTERNS,
        MAX_PROMPT_CHARS,
        PROMPT_BUDGETS,
        BLF_EXTRA_PROMPT_CHARS,
    )


try:
    from .core.prompt_text import clean_prompt_block as _core_clean_prompt_block
    from .core.prompt_text import is_structural_line as _core_is_structural_line
    from .core.prompt_text import normalize_prompt_spacing as _core_normalize_prompt_spacing
    from .core.prompt_text import light_alias_suffix as _core_light_alias_suffix
    from .core.prompt_text import coerce_rule_value as _core_coerce_rule_value
    from .core.prompt_text import normalize_signal_match_name as _core_normalize_signal_match_name
    from .core.prompt_text import numbered_items as _core_numbered_items
except ImportError:  # 패키지 밖에서 단독 실행하는 경우
    from core.prompt_text import clean_prompt_block as _core_clean_prompt_block
    from core.prompt_text import is_structural_line as _core_is_structural_line
    from core.prompt_text import normalize_prompt_spacing as _core_normalize_prompt_spacing
    from core.prompt_text import light_alias_suffix as _core_light_alias_suffix
    from core.prompt_text import coerce_rule_value as _core_coerce_rule_value
    from core.prompt_text import normalize_signal_match_name as _core_normalize_signal_match_name
    from core.prompt_text import numbered_items as _core_numbered_items

try:
    from .core.prompt_text import SECTION_HEADER_RE as _SECTION_HEADER_RE, NUMBERED_PREFIX_RE as _NUMBERED_PREFIX_RE
except ImportError:
    from core.prompt_text import SECTION_HEADER_RE as _SECTION_HEADER_RE, NUMBERED_PREFIX_RE as _NUMBERED_PREFIX_RE


class TcEngineMixin:
    """
    Validation Assistant의 Prompt Generation, BLF/DBC Local Validation, 
    Text Optimization 및 Review Pipeline을 구현한 엔진 믹스인 클래스.
    """

    def update_tc_generation_sequence_mode(self, mode: str):
        if mode not in {"AI 자동 생성", "사용자 흐름 우선", "사용자 순서 고정"}:
            mode = "사용자 흐름 우선"
        self.tc_generation_sequence_mode = mode
        is_fixed = mode == "사용자 순서 고정"
        if hasattr(self, "tc_generation_sequence_btn"):
            self.tc_generation_sequence_btn.setToolTip(
                "입력한 번호 순서를 변경하지 않습니다." if is_fixed
                else "핵심 흐름만 입력해도 AI가 상세 Step으로 확장합니다."
            )

    def store_tc_generation_page_values(self):
        if not hasattr(self, "purpose"):
            return
        if self.tc_generation_page == "execution":
            self.tc_generation_preconditions = self.purpose.toPlainText()
            self.tc_generation_observations = self.expected.toPlainText()
        elif self.tc_generation_page == "sequence":
            self.tc_generation_sequence = self.purpose.toPlainText()
            self.tc_generation_checkpoints = self.expected.toPlainText()
        else:
            self.tc_generation_requirement = self.purpose.toPlainText()
            self.tc_generation_acceptance = self.expected.toPlainText()

    def load_tc_generation_page_values(self):
        if self.tc_generation_page == "execution":
            self.purpose_label.setText("시험 전 상태 / 시험 환경")
            self.expected_label.setText("가능한 조작 / 제한 조건")
            self.purpose.setPlaceholderText("차량 초기 상태, Door 상태, Key 등록 상태, CANoe/DBC 환경을 번호로 입력하세요.")
            self.expected.setPlaceholderText("가능한 조작과 불가능한 조작, 시험 제한 조건을 입력하세요.")
            self.purpose.setPlainText(self.tc_generation_preconditions)
            self.expected.setPlainText(self.tc_generation_observations)
        elif self.tc_generation_page == "sequence":
            self.purpose_label.setText("시험 수행 순서")
            self.expected_label.setText("확인 Signal / 관찰 항목")
            self.purpose.setPlaceholderText(
                "번호 순서로 입력하세요. 예:\n"
                "1. 운전석 도어를 Open한다.\n"
                "2. 운전석 도어를 Close한다.\n"
                "3. 운전석 도어를 Lock한다.\n"
                "4. 모바일 기기를 접근 영역으로 이동한다."
            )
            self.expected.setPlaceholderText(
                "각 단계에서 확인할 Signal 또는 물리 상태를 입력하세요. 예:\n"
                "- Door Lock 초기 상태\n"
                "- Digital Key 위치 상태\n"
                "- 인증 결과\n"
                "- 실제 도어 Open 가능 여부"
            )
            self.purpose.setPlainText(self.tc_generation_sequence)
            self.expected.setPlainText(self.tc_generation_checkpoints)
        else:
            self.purpose_label.setText("기능 동작 / 요구사항")
            self.expected_label.setText("정상 동작 / 합격 기준")
            self.purpose.setPlaceholderText("기능 Trigger, 성공/실패 및 Recovery 흐름을 입력하세요.")
            self.expected.setPlaceholderText("관찰 또는 측정 가능한 PASS 기준을 입력하세요.")
            self.purpose.setPlainText(self.tc_generation_requirement)
            self.expected.setPlainText(self.tc_generation_acceptance)
        self.tc_generation_basic_btn.setChecked(self.tc_generation_page == "basic")
        self.tc_generation_execution_btn.setChecked(self.tc_generation_page == "execution")
        self.tc_generation_sequence_btn.setChecked(self.tc_generation_page == "sequence")
        if hasattr(self, "tc_generation_sequence_mode_combo"):
            self.tc_generation_sequence_mode_combo.blockSignals(True)
            self.tc_generation_sequence_mode_combo.setCurrentText(self.tc_generation_sequence_mode)
            self.tc_generation_sequence_mode_combo.blockSignals(False)

    def switch_tc_generation_page(self, page: str):
        if "TC Generation" not in self.mode.currentText():
            return
        page = page if page in {"basic", "execution", "sequence"} else "basic"
        if page != self.tc_generation_page:
            self.store_tc_generation_page_values()
            self.tc_generation_page = page
            self.load_tc_generation_page_values()

    def get_tc_generation_prompt_inputs(self) -> Tuple[str, str]:
        self.store_tc_generation_page_values()
        requirement = self.tc_generation_requirement.strip()
        if self.tc_generation_preconditions.strip():
            requirement += "\n\n[Preconditions / Test Environment]\n" + self.tc_generation_preconditions.strip()
        if self.tc_generation_observations.strip():
            requirement += "\n\n[Available Operations / Constraints]\n" + self.tc_generation_observations.strip()
        if self.tc_generation_sequence.strip():
            requirement += "\n\n[Mandatory Test Execution Sequence]\n" + self.tc_generation_sequence.strip()
        if self.tc_generation_checkpoints.strip():
            requirement += "\n\n[Signals and Observation Checkpoints]\n" + self.tc_generation_checkpoints.strip()

        if not requirement.strip():
            QMessageBox.warning(
                self,
                "입력 확인",
                "기능 동작/요구사항, 시험 전 상태, 수행 순서 중 하나 이상을 입력하세요."
            )
            return "", self.tc_generation_acceptance.strip()

        mode = self.tc_generation_sequence_mode
        sequence_exists = bool(self.tc_generation_sequence.strip())
        if mode == "사용자 순서 고정" and not sequence_exists:
            QMessageBox.warning(
                self,
                "수행 순서 입력 확인",
                "'사용자 순서 고정' 모드에서는 수행 순서를 번호로 입력해야 합니다."
            )
            return "", self.tc_generation_acceptance.strip()

        if mode == "AI 자동 생성" or (mode == "사용자 흐름 우선" and not sequence_exists):
            sequence_instruction = """
[Sequence Generation Mode: AI AUTO]
- 요구사항, 시험 전 상태, 가능한 조작과 제한 조건을 분석하여 전체 시험 수행 순서를 생성한다.
- 초기 상태 설정 -> 입력/조작(요청) -> 기능 Trigger -> 상태/응답 확인 -> 최종 동작 확인 순으로 구성한다.
- 입력/조작과 상태/응답 확인을 각각 독립된 별도 Step으로 작성한다.
- 수치 조건이 명시되지 않은 시간, 전압, 건수, 횟수 등은 TBD 표기를 유지한다.
"""
        elif mode == "사용자 흐름 우선":
            sequence_instruction = """
[Sequence Generation Mode: USER FLOW FIRST]
- [Mandatory Test Execution Sequence]의 핵심 흐름과 순서를 완벽히 유지한다.
- 축약된 흐름을 실제 수행 가능한 상세 Step으로 확장하되, 조작과 관찰 항목을 분리한다.
- 사용자가 지정한 핵심 조작은 절대로 삭제하거나 순서를 바꾸지 않는다.
"""
        else:
            sequence_instruction = """
[Sequence Generation Mode: USER SEQUENCE FIXED]
- [Mandatory Test Execution Sequence]의 번호, 항목 수, 순서를 변경하지 않는다.
- 사용자 Step을 추가, 삭제, 병합, 분할 또는 재배열하지 않는다.
- 각 Step 문장만 정량적 표현으로 명확히 정리하고 동일 번호의 Expected Result를 생성한다.
"""
        requirement += "\n" + sequence_instruction.strip()
        return requirement.strip(), self.tc_generation_acceptance.strip()

    def _numbered_items(self, *args, **kwargs):
        return _core_numbered_items(*args, **kwargs)

    def update_validation_pair_status(self):
        if not hasattr(self, 'validation_pair_status'):
            return
        pc = self._numbered_items(self.validation_preconditions.toPlainText()) if hasattr(self, 'validation_preconditions') else []
        st = self._numbered_items(self.validation_steps.toPlainText()) if hasattr(self, 'validation_steps') else []
        ex = self._numbered_items(self.validation_expected_results.toPlainText()) if hasattr(self, 'validation_expected_results') else []
        ac = self._numbered_items(self.validation_actual_results.toPlainText()) if hasattr(self, 'validation_actual_results') else []
        step_ids = {n for n, _ in st}
        expected_ids = {n for n, _ in ex}
        paired = len(step_ids & expected_ids)
        missing_ex = len(step_ids - expected_ids)
        fourth_name = "Review 기준" if hasattr(self, "mode") and "TC Review" in self.mode.currentText() else "Actual"
        self.validation_pair_status.setText(
            f"Precondition {len(pc)} | Step {len(st)} | Expected {len(ex)} | {fourth_name} {len(ac)} | 대응 {paired} | Expected 누락 {missing_ex}"
        )
        color = '#16836f' if missing_ex == 0 and st else '#a56a08'
        self.validation_pair_status.setStyleSheet(f"color:{color}; font-size:8pt; padding:2px 4px;")

    def normalize_active_validation_tab(self):
        if not hasattr(self, "validation_tabs"):
            return
        editor = self.validation_tabs.currentWidget()
        if hasattr(editor, "normalize_current_text"):
            editor.normalize_current_text()
        self.update_validation_pair_status()

    def sync_structured_validation_to_legacy_fields(self):
        if not hasattr(self, 'validation_preconditions'):
            return
        mode = self.mode.currentText() if hasattr(self, "mode") else ""
        pre = self.validation_preconditions.toPlainText().strip()
        steps = self.validation_steps.toPlainText().strip()
        expected = self.validation_expected_results.toPlainText().strip()
        fourth = self.validation_actual_results.toPlainText().strip()

        purpose_blocks = []
        if pre:
            purpose_blocks.append('[Preconditions]\n' + pre)
        if steps:
            purpose_blocks.append('[Test Steps]\n' + steps)

        if "TC Review" in mode:
            expected_blocks = []
            if expected:
                expected_blocks.append('[Expected Results]\n' + expected)
            if fourth:
                expected_blocks.append('[Review Criteria]\n' + fourth)
            self.purpose.setPlainText('\n\n'.join(purpose_blocks))
            self.expected.setPlainText('\n\n'.join(expected_blocks))
        else:
            if expected:
                purpose_blocks.append('[Expected Results]\n' + expected)
            self.purpose.setPlainText('\n\n'.join(purpose_blocks))
            self.expected.setPlainText(fourth)
        self.update_validation_pair_status()

    def extract_tc_blf_validation_rules(self) -> List[Dict[str, Any]]:
        if hasattr(self, 'validation_expected_results') and 'Validation Analysis' in self.mode.currentText():
            source = self.validation_expected_results.toPlainText()
        else:
            source = self.purpose.toPlainText() + '\n' + self.expected.toPlainText()
        pattern = re.compile(r"(?<![A-Za-z0-9_])(?P<signal>[A-Za-z][A-Za-z0-9_]{2,})\s*(?P<op>==|!=|>=|<=|=|>|<)\s*(?P<value>[A-Za-z0-9_.+\-]+)")
        rules = []
        current = 'UNSPECIFIED'
        for line_no, line in enumerate(source.splitlines(), 1):
            sm = re.search(r"(?:Step|Expected(?:\s*Result)?|Result|단계)\s*[-:#.]?\s*(\d+(?:[-.]\d+)*)", line, re.I)
            if sm:
                current = sm.group(1)
            for m in pattern.finditer(line):
                rules.append({
                    'rule_id': f'R{len(rules)+1:03d}',
                    'step': current,
                    'source_line': line_no,
                    'source_text': line.strip(),
                    'signal': m.group('signal'),
                    'operator': m.group('op'),
                    'expected': m.group('value')
                })
        return rules

    def _normalize_signal_match_name(self, *args, **kwargs):
        return _core_normalize_signal_match_name(*args, **kwargs)

    def resolve_tc_signal_to_dbc(self, requested_name: str) -> Dict[str, Any]:
        requested = str(requested_name or "").strip()
        catalog, _ = self.build_dbc_context_catalog()
        if not requested or not catalog:
            return {"requested": requested, "resolved": requested, "score": 0.0, "status": "UNRESOLVED"}
        by_name = {}
        for item in catalog:
            by_name.setdefault(item.get("signal", ""), item)
        for function_name, signal_name in (getattr(self, "signal_function_mapping", None) or {}).items():
            if requested.lower() in {str(function_name).lower(), str(signal_name).lower()} and signal_name in by_name:
                return {"requested": requested, "resolved": signal_name, "score": 1.0, "status": "DIRECT_MAPPING"}
        wanted_norm = self._normalize_signal_match_name(requested)
        exact = [name for name in by_name if self._normalize_signal_match_name(name) == wanted_norm]
        if len(exact) == 1:
            return {"requested": requested, "resolved": exact[0], "score": 1.0, "status": "NORMALIZED_EXACT"}
        wanted_tokens = set(wanted_norm.split())
        ranked = []
        for name, item in by_name.items():
            candidate_norm = self._normalize_signal_match_name(name)
            candidate_tokens = set(candidate_norm.split())
            if not wanted_tokens or not candidate_tokens:
                continue
            common = wanted_tokens & candidate_tokens
            union = wanted_tokens | candidate_tokens
            containment = len(common) / max(1, min(len(wanted_tokens), len(candidate_tokens)))
            jaccard = len(common) / max(1, len(union))
            substring = 1.0 if wanted_norm in candidate_norm or candidate_norm in wanted_norm else 0.0
            context_score = self.score_dbc_context_candidate(requested, item)
            score = 0.45 * containment + 0.25 * jaccard + 0.20 * context_score + 0.10 * substring
            ranked.append((score, name, item))
        ranked.sort(key=lambda row: row[0], reverse=True)
        if not ranked:
            return {"requested": requested, "resolved": requested, "score": 0.0, "status": "UNRESOLVED"}
        best_score, best_name, best_item = ranked[0]
        second = ranked[1][0] if len(ranked) > 1 else 0.0
        margin = best_score - second
        base = {
            "requested": requested,
            "resolved": best_name,
            "score": round(best_score, 3),
            "margin": round(margin, 3),
            "message": best_item.get("message", ""),
            "can_id": best_item.get("can_id", "")
        }
        if best_score >= 0.60 and margin >= 0.08:
            base["status"] = "FUZZY_APPLIED"
            return base
        if best_score >= 0.45:
            base["status"] = "REVIEW_REQUIRED"
            return base
        return {"requested": requested, "resolved": requested, "score": round(best_score, 3), "margin": round(margin, 3), "status": "UNRESOLVED"}

    def _coerce_rule_value(self, *args, **kwargs):
        return _core_coerce_rule_value(*args, **kwargs)

    def _compare_rule_value(self, observed: Any, operator: str, expected: Any) -> Optional[bool]:
        left = self._coerce_rule_value(observed)
        right = self._coerce_rule_value(expected)
        both_numeric = isinstance(left, float) and isinstance(right, float)
        if operator in {'=', '=='}:
            return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9) if both_numeric else left == right
        if operator == '!=':
            return (not math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)) if both_numeric else left != right
        if not both_numeric:
            return None
        return {'>': left > right, '<': left < right, '>=': left >= right, '<=': left <= right}.get(operator)

    def run_tc_blf_auto_validation(self):
        if not getattr(self, 'blf_summary_data', None):
            QMessageBox.warning(self, 'TC-BLF Auto Validation', '먼저 BLF와 DBC를 선택하고 Parse BLF Locally를 실행하세요.')
            return
        timeline = getattr(self, 'blf_full_signal_timeline', [])
        if not timeline:
            timeline = [e for e in self.blf_summary_data.get('key_timeline', []) if e.get('event_type') == 'signal_change']
        rules = self.extract_tc_blf_validation_rules()
        if not rules:
            QMessageBox.information(self, 'TC-BLF Auto Validation', "Expected Results에서 'Signal = Value' 형식의 조건을 찾지 못했습니다.\n정확한 Signal은 AUTO, 기능 설명은 DBC Mapping 후 분석하세요.")
            return
        results = []
        for rule in rules:
            resolution = self.resolve_tc_signal_to_dbc(rule['signal'])
            resolved_signal = resolution.get('resolved') or rule['signal']
            events = [e for e in timeline if str(e.get('signal', '')).lower() == str(resolved_signal).lower()]
            item = dict(rule)
            item['observations'] = []
            item['signal_resolution'] = resolution
            item['resolved_signal'] = resolved_signal
            if not events:
                item.update(
                    result='INCONCLUSIVE',
                    confidence='LOW',
                    reason=('DBC Decode Timeline에서 대상 Signal을 찾지 못했습니다.' + (f" 후보 {resolved_signal}은 임계값/후보 차이 부족으로 검토가 필요합니다." if resolution.get('status') == 'REVIEW_REQUIRED' else '')),
                    cause_candidates=['DBC/BLF 버전 확인', 'Signal Filter 및 분석 구간 확인', 'DBC Context Match로 Signal Mapping 확인']
                )
            else:
                matched = []
                for e in events:
                    ok = self._compare_rule_value(e.get('to'), rule['operator'], rule['expected'])
                    item['observations'].append({'time_sec': e.get('time_sec'), 'message': e.get('message'), 'from': e.get('from'), 'to': e.get('to'), 'matched': ok})
                    if ok is True:
                        matched.append(e)
                if matched:
                    item.update(result='PASS', confidence='HIGH', reason='기대 조건과 일치하는 값이 BLF에서 직접 확인되었습니다.', first_match_time_sec=matched[0].get('time_sec'))
                else:
                    item.update(result='FAIL', confidence='HIGH', reason='Signal은 수신됐지만 기대 조건과 일치하는 값이 확인되지 않았습니다.', cause_candidates=['선행 Vehicle/ECU 상태 미충족', '요청 이후 응답 또는 상태 전이 지연', 'Validity/Timeout/통신 영향', 'DBC와 SW 버전 불일치 가능성'])
            if resolution.get('status') == 'REVIEW_REQUIRED' and item.get('result') in ('PASS', 'FAIL'):
                item['confidence'] = 'LOW'
                item['reason'] = f"{item.get('reason', '')} (Signal 매핑 '{resolved_signal}'이 확정되지 않아 신뢰도를 낮춤)".strip()
            results.append(item)
        counts = Counter(r['result'] for r in results)
        report = {
            'engine': 'TC-BLF Local Validation v1',
            'notice': '명확한 Signal 조건만 로컬 계산합니다. 원인 후보는 확정 원인이 아닙니다.',
            'summary': {'rules': len(results), 'PASS': counts.get('PASS', 0), 'FAIL': counts.get('FAIL', 0), 'REVIEW': counts.get('REVIEW', 0), 'INCONCLUSIVE': counts.get('INCONCLUSIVE', 0)},
            'results': results
        }
        self.tc_blf_validation_data = report
        self.blf_summary_data['tc_blf_local_validation'] = report
        self.blf_summary_preview.setPlainText(json.dumps(report, ensure_ascii=False, indent=2))
        QMessageBox.information(self, 'TC-BLF Auto Validation', f"로컬 비교 완료\nPASS {counts.get('PASS',0)} | FAIL {counts.get('FAIL',0)} | INCONCLUSIVE {counts.get('INCONCLUSIVE',0)}")

    def is_safe_summary_mode(self) -> bool:
        return (
            not hasattr(self, "ai_transmission_mode")
            or self.ai_transmission_mode.currentIndex() == 0
        )

    def is_semantic_preserve_mode(self) -> bool:
        return hasattr(self, "ai_transmission_mode") and self.ai_transmission_mode.currentIndex() == 1

    def _ensure_semantic_signal_aliases(self) -> Dict[str, str]:
        ordered = []
        for signal in list(getattr(self, "tc_related_parse_signals", []) or []) + self.mapped_signals_for_analysis():
            if signal and signal not in ordered:
                ordered.append(signal)
        catalog, _errors = self.build_dbc_context_catalog()
        tc_text = self._tc_text_for_signal_selection() if hasattr(self, "_tc_text_for_signal_selection") else ""
        for item in catalog:
            signal = item.get("signal", "")
            if signal and signal in tc_text and signal not in ordered:
                ordered.append(signal)
        self.preferred_signal_aliases = {signal: f"SIG_{index:03d}" for index, signal in enumerate(ordered, 1)}
        return dict(self.preferred_signal_aliases)

    def _semantic_rewrite_line(self, text: str, aliases: Dict[str, str]) -> str:
        line = str(text or "").strip()
        if not line:
            return ""
        for signal, alias in sorted(aliases.items(), key=lambda row: len(row[0]), reverse=True):
            line = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(signal) + r"(?![A-Za-z0-9_])", alias, line, flags=re.I)
        if not hasattr(self, "semantic_entity_aliases"):
            self.semantic_entity_aliases = {}
        protected = {
            "ON", "OFF", "OPEN", "CLOSE", "CLOSED", "LOCK", "LOCKED", "UNLOCK", "UNLOCKED",
            "ACTIVE", "INACTIVE", "REQUEST", "SUCCESS", "FAIL", "FAILED", "PASS", "CAN", "LIN",
            "UDS", "ISO", "TP", "BLF", "DBC", "AUTO", "TIMEOUT", "TRUE", "FALSE"
        }
        protected.update(aliases.values())

        def mask_identifier(match):
            token = match.group(0)
            upper = token.upper()
            if upper in protected or re.fullmatch(r"SIG_\d{3}", upper):
                return token
            if re.fullmatch(r"0x[0-9A-Fa-f]+", token):
                return token
            technical = ("_" in token or bool(re.search(r"[a-z][A-Z]|[A-Z][a-z]+[A-Z]", token)) or bool(re.search(r"\d", token)))
            if not technical:
                return token
            if token not in self.semantic_entity_aliases:
                self.semantic_entity_aliases[token] = f"LOCAL_REF_{len(self.semantic_entity_aliases)+1:03d}"
            return self.semantic_entity_aliases[token]

        return re.sub(r"\b[A-Za-z][A-Za-z0-9_]{3,}\b", mask_identifier, line)

    def build_semantic_preserved_tc_context(self) -> Tuple[str, Dict[str, str]]:
        aliases = self._ensure_semantic_signal_aliases()
        self.semantic_entity_aliases = {}
        sections = [
            ("Preconditions", getattr(self, "validation_preconditions", None)),
            ("Actions", getattr(self, "validation_steps", None)),
            ("Expected Behavior", getattr(self, "validation_expected_results", None)),
            ("Actual Observation", getattr(self, "validation_actual_results", None)),
        ]
        context = []
        for title, widget in sections:
            text = widget.toPlainText().strip() if isinstance(widget, QTextEdit) else ""
            lines = []
            for raw in text.splitlines():
                rewritten = self._semantic_rewrite_line(raw, aliases)
                if rewritten:
                    lines.append("- " + rewritten)
            context.append(f"[{title}]\n" + ("\n".join(lines) if lines else "- 정보 없음"))
        rules = self.extract_tc_blf_validation_rules()
        if rules:
            rule_lines = []
            for rule in rules:
                signal = aliases.get(rule.get("signal"), rule.get("signal"))
                rule_lines.append(f"- {signal} {rule.get('operator')} {rule.get('expected')} (Step {rule.get('step')})")
            context.append("[Preserved Validation Criteria]\n" + "\n".join(rule_lines))
        context.append("[Signal Alias Policy]\n- 실제 DBC Signal명은 로컬에서만 관리한다.\n- AI에는 SIG_### 별칭만 제공한다.\n- 값, 비교 연산자, 시간과 단위는 원래 판정 의미를 유지한다.")
        return "\n\n".join(context), aliases

    def build_secure_blf_summary(self) -> Dict[str, Any]:
        if not self.blf_summary_data:
            return {
                "security_mode": "TC_SOURCE_OMITTED_BLF_LOCAL_SUMMARY_ONLY",
                "raw_blf_sent_to_ai": False,
                "status": "BLF_SUMMARY_NOT_AVAILABLE",
            }

        level = self.prompt_level.currentText()
        event_limits = {"Basic": 15, "Detailed": 25, "Expert": 40}
        session_limits = {"Basic": 6, "Detailed": 12, "Expert": 20}
        stats = self.blf_summary_data.get("statistics", {})
        window = self.blf_summary_data.get("analysis_window", {})
        tp = self.blf_summary_data.get("transport_protocol_summary", {})

        signal_aliases = {}
        message_aliases = {}
        state_aliases = {}

        def alias(mapping, prefix, value):
            key = str(value or "").strip()
            if not key:
                return "UNKNOWN"
            if key not in mapping:
                mapping[key] = f"{prefix}_{len(mapping) + 1:03d}"
            return mapping[key]

        def safe_state(value):
            text = str(value if value is not None else "UNKNOWN").strip()
            if text == "UNOBSERVED":
                return "UNOBSERVED"
            try:
                return float(text)
            except Exception:
                return alias(state_aliases, "STATE", text)

        safe_timeline = []
        for event in self.blf_summary_data.get("key_timeline", [])[:event_limits.get(level, 25)]:
            event_type = event.get("event_type")
            if event_type == "signal_change":
                safe_timeline.append({
                    "time_sec": event.get("time_sec"),
                    "event_type": "signal_change",
                    "message": alias(message_aliases, "MSG", event.get("message")),
                    "signal": alias(signal_aliases, "SIG", event.get("signal")),
                    "from": safe_state(event.get("from")),
                    "to": safe_state(event.get("to")),
                })
            elif event_type == "raw_payload_change":
                safe_timeline.append({
                    "time_sec": event.get("time_sec"),
                    "event_type": "raw_message_changed",
                    "can_channel": alias(message_aliases, "CAN", event.get("can_id")),
                    "payload_value_removed": True,
                })

        safe_sessions = []
        for session in tp.get("sessions", [])[:session_limits.get(level, 12)]:
            uds = session.get("uds", {}) if isinstance(session.get("uds"), dict) else {}
            safe_uds = {
                key: value for key, value in uds.items()
                if key in {
                    "response_type", "service_name", "negative_response_name",
                    "service_id", "request_service_id"
                }
            }
            safe_sessions.append({
                "protocol": session.get("protocol", "ISO-TP"),
                "channel": alias(message_aliases, "TP_CH", session.get("can_id")),
                "start_time_sec": session.get("start_time_sec"),
                "end_time_sec": session.get("end_time_sec"),
                "duration_ms": session.get("duration_ms"),
                "frame_count": session.get("frame_count"),
                "status": session.get("status"),
                "issues": session.get("issues", []),
                "uds": safe_uds,
                "payload_removed": True,
            })

        return {
            "security_mode": "TC_SOURCE_OMITTED_BLF_LOCAL_SUMMARY_ONLY",
            "raw_blf_sent_to_ai": False,
            "tc_source_included": False,
            "file_names_included": False,
            "real_signal_names_included": False,
            "raw_payload_included": False,
            "analysis_window": {
                "start_sec": window.get("start_sec", 0),
                "end_sec": window.get("end_sec"),
                "time_reference": "local_log_start_equals_zero",
            },
            "parse_quality": {
                "selected_messages": stats.get("selected_messages", 0),
                "decoded_messages": stats.get("decoded_messages", 0),
                "decode_errors": stats.get("decode_errors", 0),
            },
            "key_timeline": safe_timeline,
            "transport_protocol_summary": {
                "mode": tp.get("mode", "Off"),
                "session_count": tp.get("session_count", len(safe_sessions)),
                "sessions": safe_sessions,
            },
            "analysis_instruction": (
                "TC 원문과 기대값은 제공되지 않았다. 로그에서 직접 확인되는 상태 전이, "
                "지연, 오류, 미완료 세션만 관찰 사실로 정리하고 PASS/FAIL이나 Root Cause를 확정하지 않는다."
            ),
        }

    def update_ai_transmission_mode_notice(self, *_args):
        if not hasattr(self, "ai_transmission_notice"):
            return
        index = self.ai_transmission_mode.currentIndex() if hasattr(self, "ai_transmission_mode") else 0
        if index == 0:
            text = "보안 기본 · TC 원문/Expected 원문 제외 · 익명 BLF 로컬 요약만 포함"
            style = "color:#28645f; background:#edf9f7; border:1px solid #addbd5; border-radius:4px; padding:5px; font-size:8pt;"
        elif index == 1:
            text = "의미 보존 · 문장 구조 유지 · Signal/기능/ECU 식별자 별칭 · 값/시간/단위 유지"
            style = "color:#155c75; background:#eaf7fb; border:1px solid #9ccfdf; border-radius:4px; padding:5px; font-size:8pt;"
        else:
            text = "주의 · 승인된 경우에만 TC 원문과 실제 Signal명 포함"
            style = "color:#8a4b00; background:#fff5df; border:1px solid #e7c88b; border-radius:4px; padding:5px; font-size:8pt;"
        self.ai_transmission_notice.setText(text)
        self.ai_transmission_notice.setStyleSheet(style)

    def reset_tc_generation_light_aliases(self):
        self.tc_generation_light_alias_map = {}
        self.tc_generation_light_reverse_map = {}

    def _light_alias_suffix(self, *args, **kwargs):
        return _core_light_alias_suffix(*args, **kwargs)

    def apply_tc_generation_light_mask(self, text: str, reset: bool = True) -> str:
        """
        reset=True  : 별칭 map 을 새로 시작 (단독 호출)
        reset=False : 기존 map 을 이어서 사용 (한 프롬프트 안에서 여러 입력을 연속 마스킹할 때)
        """
        if not text or not hasattr(self, "tc_generation_signal_mode"):
            return str(text or "")
        mode = self.tc_generation_signal_mode.currentIndex()
        if reset or not hasattr(self, "tc_generation_light_alias_map"):
            self.reset_tc_generation_light_aliases()
        if mode == 2:
            return str(text)
        pattern = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b")
        protected = {"PASS_FAIL", "JSON_OUTPUT", "NOT_EVALUATED", "TC_GENERATION"}

        def repl(match):
            token = match.group(0)
            if token.upper() in protected or token in self.tc_generation_light_reverse_map:
                return token  # 보호 토큰 또는 이미 변환된 별칭
            alias = self.tc_generation_light_alias_map.get(token)
            if alias is None:  # 같은 토큰은 항상 같은 별칭, 새 토큰만 번호 증가
                alias = (
                    f"SIG_{len(self.tc_generation_light_alias_map) + 1:03d}"
                    if mode == 1
                    else token + self._light_alias_suffix(token)
                )
                self.tc_generation_light_alias_map[token] = alias
                self.tc_generation_light_reverse_map[alias] = token
            return alias

        return pattern.sub(repl, str(text))

    def restore_tc_generation_light_aliases(self, text: str) -> str:
        restored = str(text or "")
        for alias, original in sorted(getattr(self, "tc_generation_light_reverse_map", {}).items(), key=lambda x: len(x[0]), reverse=True):
            restored = re.sub(rf"\b{re.escape(alias)}\b", original, restored)
        return restored

    def update_tc_generation_signal_notice(self, *_args):
        if not hasattr(self, "tc_generation_signal_notice"):
            return
        messages = [
            "원본명에 고정 코드를 추가합니다. 완전한 익명화는 아닙니다.",
            "기술 식별자를 SIG_001 형식으로 바꿉니다. 의미 이해가 낮아질 수 있습니다.",
            "사내 AI 입력 승인을 확인한 경우에만 원본을 유지하세요.",
        ]
        self.tc_generation_signal_notice.setText(messages[self.tc_generation_signal_mode.currentIndex()])

    def get_blf_summary_for_prompt(self) -> str:
        if self.is_safe_summary_mode():
            return json.dumps(
                self.build_secure_blf_summary(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        if not self.blf_summary_data:
            return "BLF 요약 없음"
        level = self.prompt_level.currentText()
        event_limits = {"Basic": 15, "Detailed": 25, "Expert": 40}
        session_limits = {"Basic": 6, "Detailed": 12, "Expert": 20}
        tp = self.blf_summary_data.get("transport_protocol_summary", {})
        sessions = tp.get("sessions", [])
        stats = self.blf_summary_data.get("statistics", {})
        source = self.blf_summary_data.get("source", {})
        compact = {
            "source": {"blf_file": source.get("blf_file", ""), "raw_file_sent_to_ai": False},
            "analysis_window": self.blf_summary_data.get("analysis_window", {}),
            "parse_quality": {
                "selected_messages": stats.get("selected_messages", 0),
                "decoded_messages": stats.get("decoded_messages", 0),
                "decode_errors": stats.get("decode_errors", 0)
            },
            "important_findings": self.blf_summary_data.get("important_findings", [])[:10],
            "key_timeline": self.blf_summary_data.get("key_timeline", [])[:event_limits.get(level, 25)],
            "transport_protocol_summary": {"mode": tp.get("mode", "Off"), "sessions": sessions[:session_limits.get(level, 12)]}
        }
        summary = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        if self.is_semantic_preserve_mode():
            self._ensure_semantic_signal_aliases()
        anonymize_widget = getattr(self, "anonymize_signals_for_ai", None)
        anonymize = bool(anonymize_widget.isChecked()) if anonymize_widget is not None else False
        if self.is_semantic_preserve_mode() or anonymize:
            aliases = getattr(self, "preferred_signal_aliases", None) or {}
            # 긴 이름부터, 식별자 경계 기준으로 치환 (Sig_Door 가 Sig_DoorLock 을 깨뜨리지 않도록)
            for signal, alias_name in sorted(aliases.items(), key=lambda row: len(row[0]), reverse=True):
                summary = re.sub(
                    r"(?<![A-Za-z0-9_])" + re.escape(signal) + r"(?![A-Za-z0-9_])", alias_name, summary
                )
        return summary

    # --------------------------------------------------------------------------
    # 도메인 레지스트리 조회 헬퍼
    # --------------------------------------------------------------------------
    def get_domain_key(self) -> str:
            """
            현재 UI 콤보박스 선택값 및 도메인 프로필을 기반으로 
            레지스트리 키('automotive', 'web_api', 'mobile_app' 등)를 정확히 추출합니다.
            """
            profile = self.current_domain_profile() or {}
            
            # 1. 프로필에 'key'가 명시되어 있으면 최우선 사용
            key = str(profile.get("key", "")).strip().lower()
            if key in FEW_SHOTS:
                return key
                
            # 2. UI 콤보박스(qa_domain 또는 mode)에서 선택된 텍스트 직접 확인
            domain_text = ""
            if hasattr(self, "qa_domain") and hasattr(self.qa_domain, "currentText"):
                domain_text = self.qa_domain.currentText()
            elif hasattr(self, "qa_domain_combo") and hasattr(self.qa_domain_combo, "currentText"):
                domain_text = self.qa_domain_combo.currentText()
            else:
                domain_text = str(profile.get("name", ""))

            # 3. 텍스트 정규식 패턴 매칭
            text_to_check = f"{profile.get('name', '')} {domain_text}"
            for domain_key, pattern in _DOMAIN_NAME_PATTERNS:
                if pattern.search(text_to_check):
                    return domain_key
                    
            # 4. 자동차 전용 툴(CANoe/DBC/BLF)을 사용하는 프로필인 경우
            if profile.get("automotive_tools"):
                return "automotive"

            return DEFAULT_DOMAIN_KEY

    def get_domain_few_shot(self, kind: str) -> str:
        """kind: 'generation' | 'analysis'. 프로필 few_shot 이 있으면 우선, 없으면 레지스트리."""
        profile = self.current_domain_profile() or {}
        custom = profile.get("few_shot")
        if isinstance(custom, dict) and custom.get(kind):
            return str(custom[kind])
        shots = FEW_SHOTS.get(self.get_domain_key(), FEW_SHOTS[DEFAULT_DOMAIN_KEY])
        return shots.get(kind, "")

    def build_system_instruction(self) -> str:
        addendum = DOMAIN_SYSTEM_ADDENDUM.get(self.get_domain_key(), "")
        return SYSTEM_BASE_INSTRUCTION + (f"\n\n{addendum}" if addendum else "")

    def get_domain_profile_value(self, field: str, default: Any = None) -> Any:
        """프로필 값이 있으면 그 값을, 없으면 도메인 기본값(DOMAIN_DEFAULTS)을, 그것도 없으면 default 를 반환."""
        profile = self.current_domain_profile() or {}
        value = profile.get(field)
        if value:
            return value
        fallback = DOMAIN_DEFAULTS.get(self.get_domain_key(), {}).get(field)
        return fallback if fallback else default

    def build_level_scope(self, level: str) -> str:
        profile = self.current_domain_profile() or {}
        level_key = level if level in ("Basic", "Detailed") else "Expert"
        custom = profile.get("level_scope")
        if isinstance(custom, dict) and custom.get(level_key):
            body = str(custom[level_key])
        else:
            extra = DOMAIN_LEVEL_EXTRA.get(self.get_domain_key(), {}).get(level_key, "")
            body = LEVEL_SCOPE_COMMON[level_key] + (f"\n{extra}" if extra else "")
        return f"[Generation Scope - {level_key} Level]\n{body}"

    @staticmethod
    def _fill_template(template: str, values: Dict[str, Any]) -> str:
        """플레이스홀더를 한 번에(single-pass) 치환한다. 구현은 core.templating 에 있다."""
        return fill_template(template, values)

    def get_domain_prompt_values(
        self, mode_override: Optional[str] = None, with_evidence: bool = True
    ) -> Tuple[str, str, str]:
        profile = self.current_domain_profile() or {}
        mode = mode_override if mode_override else (self.mode.currentText() if hasattr(self, "mode") else "")
        if "Validation Analysis" in mode:
            rule_key = "analysis_rules"
        elif "TC Review" in mode:
            rule_key = "review_rules"
        else:
            rule_key = "generation_rules"
        role = self.get_domain_profile_value("role", "Software Quality Assurance Specialist")
        rules = self.get_domain_profile_value(rule_key, [])
        rule_text = "\n".join(f"- {rule}" for rule in rules)
        evidence = ""
        if with_evidence:  # evidence 가 쓰이지 않는 모드에서는 BLF 요약 계산을 생략
            evidence = (
                self.get_blf_summary_for_prompt()
                if profile.get("automotive_tools")
                else self.get_domain_evidence_summary()
            )
        return role, rule_text, evidence

    # ==========================================================================
    # 3. 100점 프롬프트 템플릿 기반 핵심 파서 및 생성 메서드 (Refactored)
    # ==========================================================================

    def generate_tc_creation_prompt(self, feature_name: str, requirement: str, expected_behavior: str, level: str) -> str:
        """
        100점 프롬프트 엔지니어링 가이드라인이 반영된 TC Creation Prompt 생성기.
        System Instruction(+도메인 용어) + 도메인 Few-Shot + 정량적 제약 조건 결합.
        """
        system_instruction = self.build_system_instruction()
        few_shot_example = self.get_domain_few_shot("generation")

        # 사용자 입력에만 Light Mask 적용 (시스템 템플릿 마스킹 방지).
        # 별칭 map 은 이 프롬프트 생성 동안 공유해야 요구사항/기대동작 간 별칭이 충돌하지 않는다.
        self.reset_tc_generation_light_aliases()
        masked_req = self.apply_tc_generation_light_mask(requirement, reset=False)
        masked_exp = self.apply_tc_generation_light_mask(expected_behavior, reset=False)

        seq_mode = getattr(self, "tc_generation_sequence_mode", "사용자 흐름 우선")
        sequence_rule = SEQUENCE_MODE_RULES.get(seq_mode, SEQUENCE_MODE_RULES["사용자 흐름 우선"])
        level_scope = self.build_level_scope(level)
        role_text, rule_text, _ = self.get_domain_prompt_values("TC Generation", with_evidence=False)

        prompt = f"""{system_instruction}

{few_shot_example}

[Domain Role]
{role_text}

[Domain Rules]
{rule_text}

{level_scope}

[Sequence Mode Rules: {seq_mode}]
{sequence_rule}

[Target Feature Input]
Feature Name: {feature_name}
Requirement: {masked_req}
Expected Behavior: {masked_exp}
Prompt Level: {level}
"""
        return prompt

    def build_generated_tc_review_prompt(self, generated_data: Dict[str, Any]) -> str:
        """
        생성된 TC JSON 결과를 독립적 Reviewer 관점에서 2차 재검토하는 Prompt 생성기.
        """
        profile = self.current_domain_profile() or {}
        role = self.get_domain_profile_value("role", "Software Quality Assurance Specialist")
        review_rules = "\n".join(f"- {rule}" for rule in self.get_domain_profile_value("review_rules", []))
        generated_json = json.dumps(generated_data, ensure_ascii=False, indent=2)

        return self.clean_prompt_block(f"""{self.build_system_instruction()}

너는 {role}이다.
방금 생성된 Test Case 전체를 독립적인 Lead SQA Reviewer 관점에서 다시 검토하라.

[Domain Review Rules]
{review_rules}

[Generated Test Cases to Review]
{generated_json}

[Review & Verification Instructions]
1. 생성된 모든 TC에 대해 요구사항 추적성, 정량적 측정 가능성, 스텝 1:1 대칭성을 검증한다.
2. 모호한 정성적 문구("적절히", "확인할 것")가 존재할 경우 정량적 수치(ms, V, 0xHEX, HTTP Status)로 수정안을 작성한다.
3. steps와 expected_results 항목 수가 일치하지 않는 경우 배열 개수를 수정한다.

[Output Format Instructions]
결과 전체를 하나의 ```json 코드 블록 안에 출력하라. 코드 블록 밖에는 어떠한 설명도 작성하지 마라.

{{
  "review_summary": {{
    "total_count": 0,
    "pass_count": 0,
    "needs_improvement_count": 0,
    "overall_comment": "한국어로 작성된 전체 총평"
  }},
  "reviewed_test_cases": [
    {{
      "tc_id": "TC_GEN_001",
      "original_title": "테스트케이스 제목",
      "review_result": "PASS",
      "score": 95,
      "issues": [],
      "missing_conditions": [],
      "recommendations": [],
      "revised_preconditions": [],
      "revised_steps": [],
      "revised_expected_results": [],
      "risk": "HIGH"
    }}
  ]
}}
""")

    def prepare_generated_tc_auto_review(self, generated_data: Dict[str, Any], show_message: bool = True) -> bool:
        if not isinstance(generated_data, dict) or not generated_data.get("test_cases"):
            return False
        review_prompt = self.build_generated_tc_review_prompt(generated_data)
        self.generated_prompt = review_prompt
        self.update_prompt_preview()
        QApplication.clipboard().setText(review_prompt)
        self.pending_generated_tc_data = generated_data
        if show_message:
            QMessageBox.information(
                self,
                "TC Auto Review Ready",
                "생성된 TC를 기반으로 2차 Review Prompt를 자동 생성했습니다.\n\n"
                "Review Prompt가 클립보드에 복사되었으며 Prompt Preview에도 표시됩니다.\n"
                "사용 중인 AI에 붙여넣고, Review JSON 결과를 Paste 버튼으로 가져오세요."
            )
        return True

    def normalize_prompt_spacing(self, *args, **kwargs):
        return _core_normalize_prompt_spacing(*args, **kwargs)

    def _is_structural_line(self, *args, **kwargs):
        return _core_is_structural_line(*args, **kwargs)

    def optimize_prompt_text(self, text: str) -> str:
        if not text:
            return ""
        text = textwrap.dedent(text).replace("\t", "    ")
        output = []
        in_code = False
        previous_blank = False
        seen_lines = set()
        seen_sections = set()
        for raw in text.splitlines():
            line = raw.rstrip()
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                output.append(stripped)
                previous_blank = False
                continue
            if in_code:
                output.append(line)
                previous_blank = False
                continue
            if not stripped:
                if output and not previous_blank:
                    output.append("")
                previous_blank = True
                continue
            if self._is_structural_line(stripped):
                # 코드블록 밖 JSON 스키마: '}' ']' 중복 제거/들여쓰기 제거로 깨지지 않게 그대로 보존
                output.append(line)
                previous_blank = False
                continue
            if _SECTION_HEADER_RE.match(stripped):
                section_key = stripped.lower()
                if section_key in seen_sections:
                    continue
                seen_sections.add(section_key)
            normalized = re.sub(r"\s+", " ", stripped).lower()
            is_list_item = stripped.startswith("- ") or bool(_NUMBERED_PREFIX_RE.match(stripped))
            if normalized in seen_lines and not is_list_item:
                continue
            seen_lines.add(normalized)
            output.append(line.lstrip())
            previous_blank = False
        return "\n".join(output).strip()

    def update_prompt_preview(self):
        self.result.clear()
        document = self.result.document()
        cursor = self.result.textCursor()
        preview_marker = "[[EVIDENCE_PREVIEW]]"

        if not self.generated_prompt:
            cursor.insertText("생성된 Prompt가 없습니다.")
            self.result.moveCursor(QTextCursor.Start)
            return

        if preview_marker not in self.generated_prompt:
            display_prompt = self.normalize_prompt_spacing(self.generated_prompt)
            cursor.insertText(display_prompt)
            self.result.moveCursor(QTextCursor.Start)
            return

        before_evidence, after_evidence = self.generated_prompt.split(preview_marker, 1)
        before_evidence = self.normalize_prompt_spacing(before_evidence)
        after_evidence = self.normalize_prompt_spacing(after_evidence)

        cursor.insertText(before_evidence.rstrip() + "\n\n")

        if not self.attachments:
            cursor.insertText("첨부된 이미지 없음")
        else:
            available_width = self.result.viewport().width() - 50
            image_width = max(250, min(available_width, 650))

            for index, file_path in enumerate(self.attachments, start=1):
                file_name = os.path.basename(file_path)
                cursor.insertText(f"Evidence {index}: {file_name}\n")

                if not os.path.exists(file_path):
                    cursor.insertText("[이미지 파일을 찾을 수 없습니다.]\n\n")
                    continue

                pixmap = QPixmap(file_path)
                if pixmap.isNull():
                    cursor.insertText("[이미지를 불러올 수 없습니다.]\n\n")
                    continue

                scaled_pixmap = pixmap.scaled(
                    image_width,
                    360,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )

                path_digest = hashlib.sha256(os.path.abspath(file_path).encode("utf-8")).hexdigest()[:12]
                resource_name = f"prompt_evidence_{index}_{path_digest}"
                resource_url = QUrl(resource_name)

                document.addResource(
                    QTextDocument.ImageResource,
                    resource_url,
                    scaled_pixmap
                )

                image_format = QTextImageFormat()
                image_format.setName(resource_name)
                image_format.setWidth(scaled_pixmap.width())
                image_format.setHeight(scaled_pixmap.height())

                cursor.insertImage(image_format)
                cursor.insertText("\n\n")

        cursor.insertText("\n\n" + after_evidence.lstrip())
        self.result.moveCursor(QTextCursor.Start)

    def clean_prompt_block(self, *args, **kwargs):
        return _core_clean_prompt_block(*args, **kwargs)

    def generate_prompt(self):
        """
        Validation Analysis, TC Review, TC Generation 모드 통합 프롬프트 빌더.
        """
        mode = self.mode.currentText()
        if "Validation Analysis" in mode or "TC Review" in mode:
            self.sync_structured_validation_to_legacy_fields()
        tc = self.tc.text().strip()
        purpose = self.purpose.toPlainText().strip()
        expected = self.expected.toPlainText().strip()

        if "Validation Analysis" in mode and hasattr(self, "validation_preconditions"):
            pre = self.validation_preconditions.toPlainText().strip()
            steps = self.validation_steps.toPlainText().strip()
            expected_result = self.validation_expected_results.toPlainText().strip()
            actual_result = self.validation_actual_results.toPlainText().strip()
            blocks = []
            if pre:
                blocks.append("[Preconditions]\n" + pre)
            if steps:
                blocks.append("[Test Steps]\n" + steps)
            if expected_result:
                blocks.append("[Expected Results]\n" + expected_result)
            purpose = "\n\n".join(blocks)
            expected = actual_result

        analysis_question = (
            self.analysis_question.toPlainText().strip()
            if hasattr(self, "analysis_question")
            else ""
        )

        level = self.prompt_level.currentText()

        if not tc:
            QMessageBox.warning(self, "입력 확인", "TC Name 또는 Feature Name을 입력하세요.")
            return

        if "TC Generation" in mode:
            purpose, expected = self.get_tc_generation_prompt_inputs()
            if not purpose:
                return  # 입력 오류 안내는 get_tc_generation_prompt_inputs 에서 이미 표시됨

        if not purpose:
            QMessageBox.warning(self, "입력 확인", "Purpose 또는 Requirement를 입력하세요.")
            return

        # 보안 기본 모드 처리
        if "Validation Analysis" in mode and self.is_safe_summary_mode():
            tc = "LOCAL_TC_REFERENCE_OMITTED"
            purpose = "TC 원문은 보안 정책 확인 전이므로 제공하지 않음. Preconditions/Steps는 로컬에 보관됨."
            local_rules = self.extract_tc_blf_validation_rules()
            selected_signal_count = len(list(getattr(self, "tc_related_parse_signals", []) or []))
            # 보안 기본 모드에서는 실제 Signal 명을 프롬프트에 넣지 않고 개수만 전달한다.
            signal_note = f"선택 Signal {selected_signal_count}개(실명은 로컬에서만 관리)" if selected_signal_count else "Signal 미확정"
            expected = f"Actual Result 원문 제외. 로컬 Expected 조건 {len(local_rules)}개 비교 적용됨. {signal_note}"
            analysis_question = "제공된 익명화 BLF 요약만 분석하고 PASS/FAIL 판정을 확정하지 않는다."

        elif "Validation Analysis" in mode and self.is_semantic_preserve_mode():
            semantic_context, semantic_aliases = self.build_semantic_preserved_tc_context()
            tc_hash = hashlib.sha256(tc.encode("utf-8")).hexdigest()[:10].upper()
            tc = f"LOCAL_TC_{tc_hash}"
            purpose = semantic_context
            actual_widget = getattr(self, "validation_actual_results", None)
            actual_text = actual_widget.toPlainText().strip() if isinstance(actual_widget, QTextEdit) else expected
            expected = self._semantic_rewrite_line(actual_text, semantic_aliases) or "관찰 결과 정보 없음"
            analysis_question = "의미 보존 변환된 시그널 별칭(SIG_###)과 수치를 바탕으로 비교 분석을 수행한다."

        # ======================================================================
        # 1. Validation Analysis Prompt 빌드
        # ======================================================================
        if "Validation Analysis" in mode:
            domain_role, domain_rules, domain_evidence = self.get_domain_prompt_values(mode)
            self.generated_prompt = build_validation_analysis_prompt(
                system_instruction=self.build_system_instruction(),
                few_shot=self.get_domain_few_shot("analysis"),
                domain_role=domain_role,
                domain_rules=domain_rules,
                domain_evidence=domain_evidence,
                tc_name=tc,
                tc_information=purpose,
                actual_result=expected,  # 분석 모드에서 expected 변수에는 Actual Result 가 담겨 있다
                analysis_purpose=self.analysis_purpose.currentText() if hasattr(self, "analysis_purpose") else "전체 분석",
                analysis_question=analysis_question,
            )

        # ======================================================================
        # 2. TC Review Prompt 빌드
        # ======================================================================
        elif "TC Review" in mode:
            domain_role, domain_rules, _ = self.get_domain_prompt_values(mode, with_evidence=False)
            self.generated_prompt = build_tc_review_prompt(
                system_instruction=self.build_system_instruction(),
                domain_role=domain_role,
                domain_rules=domain_rules,
                tc_name=tc,
                purpose=purpose,
                expected=expected,
            )

        # ======================================================================
        # 3. TC Generation Prompt 빌드
        # ======================================================================
        elif "TC Generation" in mode:
            if not expected:
                expected = "요구사항에 부합하는 정량적 Expected Result 및 PASS 기준을 도출한다."
            self.generated_prompt = self.generate_tc_creation_prompt(tc, purpose, expected, level)

        else:
            QMessageBox.warning(self, "Mode Error", "지원하지 않는 Mode입니다.")
            return

        self.generated_prompt = self.clean_prompt_block(self.generated_prompt)

        if "TC Review" in mode:
            self.generated_prompt += "\n\n" + self.build_tc_review_json_instruction()

        self.generated_prompt = self.optimize_prompt_text(self.generated_prompt)
        self.update_prompt_preview()
        self.save_history()

    def build_tc_review_json_instruction(self) -> str:
        return self.clean_prompt_block("""
[JSON OUTPUT - REQUIRED]
반드시 유효한 단일 JSON Object만 출력하라. 일반 설명을 JSON 밖에 작성하지 마라.
JSON 전체를 하나의 ```json 코드 블록 안에 넣어라.

{
  "review_summary": {
    "total_count": 1,
    "pass_count": 0,
    "needs_improvement_count": 1,
    "overall_comment": "한국어 검토 총평"
  },
  "reviewed_test_cases": [
    {
      "tc_id": "TC_REV_001",
      "original_title": "",
      "review_result": "NEEDS_IMPROVEMENT",
      "score": 80,
      "requirement_coverage": "PARTIAL",
      "clarity": "POOR",
      "testability": "PARTIAL",
      "missing_conditions": ["신호/응답 지연시간 수치 미비"],
      "issues": ["정성적 표현 사용됨"],
      "recommendations": ["150ms 이내 전이 조건 추가"],
      "revised_title": "",
      "revised_precondition": "",
      "revised_steps": [],
      "revised_expected_result": "",
      "risk": "HIGH"
    }
  ]
}
""")

    def get_prompt_text_for_copy(self) -> str:
        if not self.generated_prompt:
            return ""
        if self.attachments:
            evidence_text = "\n".join(
                f"Evidence {index}: {os.path.basename(file_path)}"
                for index, file_path in enumerate(self.attachments, start=1)
            )
        else:
            evidence_text = "첨부된 이미지 없음"
        prompt_text = self.generated_prompt.replace("[[EVIDENCE_PREVIEW]]", evidence_text)
        return self.normalize_prompt_spacing(prompt_text)

    def get_prompt_budget(self) -> Tuple[int, int, str, bool]:
        """Return recommended/absolute limits for the active mode.

        Validation receives an additional allowance only when a local BLF
        summary is actually present. The absolute limit protects clipboard and
        downstream model usage without forcing a 12,000-character bottleneck.
        """
        mode = self.mode.currentText() if hasattr(self, "mode") else "TC Generation"
        recommended = PROMPT_BUDGETS.get(mode, PROMPT_BUDGETS["TC Generation"])
        has_blf = bool(getattr(self, "blf_summary_data", None)) and "Validation Analysis" in mode
        if has_blf:
            recommended += BLF_EXTRA_PROMPT_CHARS
        recommended = min(recommended, MAX_PROMPT_CHARS)
        return recommended, MAX_PROMPT_CHARS, mode, has_blf

    @staticmethod
    def compact_prompt_for_budget(prompt_text: str) -> Tuple[str, List[str]]:
        """Safely remove formatting waste without deleting evidence or rules."""
        compacted = re.sub(r"[ \t]+\n", "\n", prompt_text)
        compacted = re.sub(r"\n{3,}", "\n\n", compacted).strip()
        actions = ["반복 공백과 빈 줄 축약"] if compacted != prompt_text.strip() else []
        return compacted, actions

    def Prompt_Generation(self):
        self.generated_prompt = ""
        self.generate_prompt()
        if not self.generated_prompt:
            return
        prompt_text = self.get_prompt_text_for_copy()
        if not prompt_text.strip():
            QMessageBox.warning(self, "Copy Error", "복사할 Prompt가 없습니다.")
            return
        prompt_text, compact_actions = self.compact_prompt_for_budget(prompt_text)
        recommended, absolute_limit, mode, has_blf = self.get_prompt_budget()
        current_length = len(prompt_text)
        if current_length > absolute_limit:
            QMessageBox.warning(
                self,
                "Prompt Too Long",
                f"{mode} 프롬프트가 절대 허용 길이({absolute_limit:,}자)를 초과했습니다.\n"
                f"현재 길이: {current_length:,}자\n\n"
                "TC, Expected/Actual, JSON 계약, Signal 및 시간 조건은 안전을 위해 임의 절단하지 않았습니다.\n"
                "반복 로그 또는 관련 없는 BLF 구간을 줄인 뒤 다시 생성하세요."
            )
            return
        QApplication.clipboard().setText(prompt_text)
        blf_note = " + BLF 추가 예산" if has_blf else ""
        compact_note = f"\n자동 정리: {', '.join(compact_actions)}" if compact_actions else ""
        if current_length > recommended:
            message = (
                f"Prompt가 클립보드에 복사되었습니다.\n"
                f"현재 길이: {current_length:,}자 / {mode} 권장 {recommended:,}자{blf_note}\n"
                f"절대 허용 길이: {absolute_limit:,}자\n\n"
                "권장 길이는 초과했지만 핵심 증적 보존을 위해 복사를 허용했습니다."
                f"{compact_note}"
            )
            QMessageBox.warning(self, "Ready - Recommended Length Exceeded", message)
        else:
            message = (
                f"Prompt가 클립보드에 복사되었습니다.\n"
                f"현재 길이: {current_length:,}자 / 권장 {recommended:,}자{blf_note}"
                f"{compact_note}"
            )
            QMessageBox.information(self, "Ready", message)

    def build_gemini_json_instruction(self) -> str:
        """Gemini API 전용 표준 JSON 스키마 지시사항 생성"""
        return self.clean_prompt_block(f"""{self.build_system_instruction()}

[Gemini API Output Rules]
1. Markdown 설명문 없이 오직 유효한 단일 JSON Object만 반환하라.
2. 모든 설명 문구는 한국어로 작성하되, 기술 식별자(Signal, ECU, API Endpoint)는 영문/Hex 표기를 유지하라.
3. Enum 값에는 선택지 전체 문자열이 아닌 단일 선택 판정값(예: "PASS") 하나만 작성하라.
""")