"""프롬프트 평가 스크립트 (오프라인 채점).

사용 순서
  1. 앱에서 cases/analysis_cases.jsonl 의 각 케이스를 입력해 프롬프트를 만들고, 모델 응답을 받는다.
  2. 응답을 outputs.jsonl 에 {"case_id": "...", "output": "<모델 응답 원문>"} 한 줄씩 저장한다.
  3. python eval/run_eval.py --cases eval/cases/analysis_cases.jsonl --outputs outputs.jsonl

지표
  json_valid_rate        JSON 으로 파싱되는 비율
  schema_ok_rate         enum/필수 필드/근거-우선 순서까지 통과하는 비율
  verdict_accuracy       result 가 라벨(expected_result)과 일치하는 비율
  unsupported_number_rate 출력에 입력에 없는 숫자가 포함된 비율 (지어낸 수치 후보, 휴리스틱)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.prompt_checks import check_analysis_output, unsupported_numbers  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def score(cases: list[dict], outputs: list[dict]) -> dict:
    by_id = {row["case_id"]: row["output"] for row in outputs}
    total = len(cases)
    json_valid = schema_ok = verdict_ok = number_issue = answered = 0
    details = []
    for case in cases:
        raw = by_id.get(case["id"])
        if raw is None:
            details.append({"id": case["id"], "status": "NO_OUTPUT"})
            continue
        answered += 1
        report = check_analysis_output(raw)
        data = report["data"]
        if data is not None:
            json_valid += 1
        if report["ok"]:
            schema_ok += 1
        got = str(data.get("result", "")).upper() if isinstance(data, dict) else ""
        if got == case["expected_result"]:
            verdict_ok += 1
        extra = unsupported_numbers(raw, case["input_text"])
        if extra:
            number_issue += 1
        details.append({"id": case["id"], "expected": case["expected_result"], "got": got,
                        "problems": report["problems"], "unsupported_numbers": sorted(extra)})
    denom = answered or 1
    return {
        "cases": total, "answered": answered,
        "json_valid_rate": round(json_valid / denom, 3),
        "schema_ok_rate": round(schema_ok / denom, 3),
        "verdict_accuracy": round(verdict_ok / denom, 3),
        "unsupported_number_rate": round(number_issue / denom, 3),
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--outputs", required=True)
    parser.add_argument("--json", action="store_true", help="세부 결과까지 JSON 으로 출력")
    args = parser.parse_args()
    report = score(load_jsonl(Path(args.cases)), load_jsonl(Path(args.outputs)))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for key in ("cases", "answered", "json_valid_rate", "schema_ok_rate", "verdict_accuracy", "unsupported_number_rate"):
            print(f"{key:26s} {report[key]}")
        bad = [d for d in report["details"] if d.get("problems") or d.get("status") == "NO_OUTPUT"]
        for d in bad:
            print("-", d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

