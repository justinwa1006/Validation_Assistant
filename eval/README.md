# 프롬프트 평가

`cases/analysis_cases.jsonl` 은 **시드 예시 6건**입니다. 실제 평가에는 현업 로그/사양을 익명화한
20~30건(PASS / FAIL / 증적 부족 / 사양 수치 누락 포함)으로 교체해야 의미 있는 수치가 나옵니다.

```bash
# outputs.jsonl: {"case_id": "A01", "output": "<모델 응답 원문>"} 한 줄씩
python eval/run_eval.py --cases eval/cases/analysis_cases.jsonl --outputs outputs.jsonl
```

프롬프트를 바꿀 때마다 같은 케이스로 다시 돌려 아래 표에 기록하세요.

| 프롬프트 버전 | 케이스 수 | json_valid | schema_ok | verdict_accuracy | unsupported_number |
|---|---|---|---|---|---|
| v1 (리팩토링 이전) | - | - | - | - | - |
| v2 (근거 우선 + FAIL/INCONCLUSIVE 예시 + TBD 규칙) | - | - | - | - | - |

