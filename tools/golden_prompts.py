"""generate_prompt 결과를 시나리오별로 JSON 으로 덤프한다 (리팩토링 전후 비교용).

사용: python tools/golden_prompts.py <프로젝트 폴더> <출력 json>
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    from tools import qt_stub  # 테스트(패키지 임포트)
except ImportError:
    sys.path.insert(0, HERE)
    import qt_stub  # 스크립트 직접 실행


class Text:
    def __init__(self, value=""):
        self.value = value

    def text(self):
        return self.value

    def toPlainText(self):
        return self.value

    def currentText(self):
        return self.value


def build_all(project_dir: str) -> dict:
    """도메인 x 모드 x 레벨 27개 시나리오의 generate_prompt 결과를 만든다."""
    qt_stub.install()
    root = os.path.abspath(project_dir)
    if root not in sys.path:
        sys.path.insert(0, root)
    import tc_engine

    class Fake(tc_engine.TcEngineMixin):
        def __init__(self, domain, mode, level="Detailed"):
            self._domain = domain
            self.mode = Text(mode)
            self.tc = Text("TC_DOOR_001")
            self.purpose = Text("도어 잠금해제 응답시간 <= 150ms 확인")
            self.expected = Text("Sig_DrvDoorLockSt == 0x01 (<= 150ms)")
            self.prompt_level = Text(level)
            self.analysis_question = Text("지연 원인을 분석하라")
            self.analysis_purpose = Text("원인 분석")
            self.validation_preconditions = Text("IGN_ON")
            self.validation_steps = Text("1. 스위치 입력")
            self.validation_expected_results = Text("1. 전이 <= 150ms")
            self.validation_actual_results = Text("전이 210ms 관찰")
            self.generated_prompt = ""

        def get_domain_key(self):
            return self._domain

        def current_domain_profile(self):
            return {}

        def sync_structured_validation_to_legacy_fields(self):
            pass

        def is_safe_summary_mode(self):
            return False

        def is_semantic_preserve_mode(self):
            return False

        def get_tc_generation_prompt_inputs(self):
            return ("도어 잠금 기능 요구사항", "응답 150ms 이내")

        def get_blf_summary_for_prompt(self):
            return "BLF SUMMARY: Sig_DrvDoorLockSt 0x00->0x01 @20.260s"

        def get_domain_evidence_summary(self):
            return "EVIDENCE SUMMARY: 증적 2건"

        def update_prompt_preview(self):
            pass

        def save_history(self):
            pass

    results = {}
    for domain in ("automotive", "web_api", "embedded_fw"):
        for mode in ("Validation Analysis", "TC Review", "TC Generation"):
            for level in ("Basic", "Detailed", "Expert"):
                fake = Fake(domain, mode, level)
                fake.generate_prompt()
                results[f"{domain}|{mode}|{level}"] = fake.generated_prompt
    return results


def main(project_dir: str, out_path: str) -> int:
    results = build_all(project_dir)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"{len(results)} prompts -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))

