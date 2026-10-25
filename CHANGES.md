# 변경 내역 (최종본)

## 2026-10-25 - Production Readiness & Async BLF / UI / Gemini Patch
- **Gemini API 정상화 (`core_runtime.py`, `ai_engine.py`, `ui_components.py`)**:
  - 하드코딩되어 있던 `ENABLE_GEMINI = False` 및 잘못된 모델명(`gemini-3.6-flash`)을 `.env` / 환경변수 기반 동적 설정(기본값 `ENABLE_GEMINI=true`, `GEMINI_MODEL=gemini-2.5-flash`)으로 정상화.
  - 통합 UI(`u_shell`) 상단 액션 바에 `✦ Gemini API 실행` 버튼(`u_gemini_btn`)을 추가하고, Validation / Generation / Review 3개 모드 모두에서 즉시 비동기 API 호출 및 구조화 결과 뷰 자동 갱신이 동작하도록 연결.
- **BLF 파서 백그라운드 스레드(`QThread`) 분리 및 멀티 DBC 개선 (`core_runtime.py`, `automotive.py`, `core/automotive_utils.py`)**:
  - 대용량 BLF 파일 첨부 및 파싱 시 메인 UI가 멈추던(Freezing) 문제를 해결하기 위해 `BlfTimeRangeWorker(QThread)`와 `BlfParseWorker(QThread)`로 완전 비동기화.
  - 파싱 진행 상황(스캔 메시지 수 및 프로그레스 바 `u_blf_progress`)을 실시간으로 UI에 표시하고, `parse_blf_locally` 함수를 297줄에서 35줄 미만의 모듈형 구조로 리팩토링(`test_complexity_budget.py`의 예외 상한 제거).
  - 다중 채널 DBC 로드 시 동일 CAN Frame ID가 존재하더라도 무조건 폐기하지 않고 보조 디코더 후보로 유지하도록 개선.
- **UI/디자인 시스템 일관성 수정 (`ui_components.py`, `ui_main.py`, `ui_design_system.py`)**:
  - `ui_components.py` 내부에 하드코딩되어 라이트 테마 전환 시 어색하게 남던 다크 인라인 스타일(`#0d1923`, `#111d28`)을 제거하고 `ui_design_system.py` 토큰 QSS가 일관되게 적용되도록 정리.
  - `ui_main.py`에서 `u_shell` 뒤쪽에 남아 탭 포커스 누수 및 불필요한 리페인트 비용을 유발하던 레거시 스플리터를 `setVisible(False)` 처리.
- **배포 패키지 위생 정리 (`run_validation_assistant.bat`, `.env.example`)**:
  - 폴더 이름을 변경해도 바로 실행되도록 `run_validation_assistant.bat` 실행 경로 수정.
  - 배포 압축본 내 불필요한 `history.json`, `__pycache__`, `.pytest_cache` 제거.


## 1. 저장소 위생
- `.gitignore`: `Try_API.env`, `*.env`(`.env.example` 제외), `history.json`, `saved_tc/*`, 테마 상태 파일 추가
- `requirements.txt`, `requirements-dev.txt`, `.env.example`, `pyproject.toml`(ruff/pytest), `.gitattributes`, GitHub Actions CI 추가
- `__pycache__/`, `history.json`(테스트 잔재) 제거, README 갱신

## 2. 프롬프트 (`prompt_data.py`, `core/prompt_builder.py`)
- 프롬프트 상수 약 700줄을 `tc_engine.py` → `prompt_data.py` 로 분리 (Qt 비의존)
- 시스템 지침: MISSING-VALUE POLICY(TBD), 정량 의무 범위 한정, 필드 순서, few-shot 값 복사 금지, 금지어 보강
- 분석 few-shot 6종: 근거 필드 → 판정 필드 순서로 재배치, FAIL / INCONCLUSIVE 예시 추가
- 자동차 생성 few-shot: 모호한 기대결과 수정, Boundary / TBD 예시 추가
- 분석 규칙: result / confidence 판정 기준, 근거 우선 작성, TBD 규칙 추가
- Validation Analysis / TC Review 프롬프트 조립을 순수 함수(`core/prompt_builder.py`)로 분리. `generate_prompt` 는 입력 수집과 후처리만 담당
- 규칙 기반 TC 리뷰: `TBD`(사양 미정)와 모호한 표현을 서로 다른 이슈로 구분

## 3. 구조 (코드)
- `self` 를 쓰지 않던 메서드 약 16개를 `core/` 순수 함수로 이동 (믹스인에는 위임 메서드만 남김):
  `json_tools`, `result_schema`, `tc_review`, `automotive_utils`, `text_utils`, `prompt_text`
- `validate_ai_result_schema` 195줄 → 단계별 헬퍼(최장 54줄)로 분해
- `init_ui` 833줄 → 11개 `_init_ui_part_NN` 단계 + 14줄 조립 함수 (지역 변수는 인자/반환으로 전달)
- 런처 몽키패치 제거 → `unified_window.create_window_class` 서브클래스로 대체
- TC / history JSON 저장을 원자적 쓰기로 교체, `pass` 로 삼키던 예외 핸들러 10곳을 로깅으로 교체
- `core_runtime.py` 끝의 잘못된 `main()` 호출 블록 제거, 주요 함수에 타입 힌트 추가(core/)

## 4. 검증 장치
- 단위 테스트 80개 (`tests/`)
- golden 프롬프트 회귀 테스트 27 시나리오, 함수 길이 래칫 테스트, 헤드리스 UI 구성 테스트
- 평가 스크립트 + 합성 시드 케이스 20건 (`eval/`)
- 리팩토링 동치성 확인 (모두 통과):
  - `init_ui` 분해 전후: 스텁 Qt 위젯 호출 기록 1,702건 동일
  - 프롬프트 조립 분리 전후: 27개 시나리오 프롬프트 문자열 동일
  - `validate_ai_result_schema` 분해 전후: 무작위 30,000 입력 결과 동일

## 하지 않은 것 / 한계 (정직한 목록)
- **GUI 실제 실행 검증 불가**: 이 작업 환경에 PySide6 가 없어 스텁 Qt 로만 확인했습니다. 적용 후 앱을 직접 실행해 주세요.
- **믹스인 해체는 하지 않았습니다.** 6개 믹스인이 공유하는 `self.*` 상태(약 400개)는 그대로입니다. 순수 함수로 뺄 수 있는 부분만 분리했습니다.
- `parse_blf_locally`(297줄) 등 대형 UI/파싱 함수 9개는 남아 있습니다 (`test_complexity_budget.py` 에 상한 등록).
  BLF 샘플과 python-can/cantools 로 동작을 검증할 수 없어 손대지 않았습니다.
- `except Exception` 약 39곳은 유지했습니다. 조용히 삼키는 `pass` 핸들러만 로깅으로 바꿨고, 나머지는 개별 검토하지 않았습니다.
- Gemini `response_schema` 도입은 하지 않았습니다. 실제 API 로 호출 검증을 할 수 없는 변경이라 기존 검증 로직을 유지했습니다.
- 평가 케이스 20건은 **합성 데이터**입니다. 실제 로그/사양 기반으로 교체하고 `eval/README.md` 표를 채워야 프롬프트 개선 효과를 수치로 보일 수 있습니다.
- CI 의 ruff 는 이 환경에서 실행하지 못했습니다 (미사용 import 등은 직접 점검). 첫 실행에서 경고가 나올 수 있습니다.
- 타입 힌트는 `core/` 와 새 모듈 위주이고, 기존 믹스인 메서드 전체에는 적용하지 않았습니다.


## 2026-10-12 - 95 Plus quality release

- Extracted responsive behavior into `ui_responsive.py` to reduce UI coupling.
- Preserved engine-owned Analysis Result and Structured Result positions.
- Removed obsolete splitter restore/timer paths that caused startup errors.
- Added DPI-aware Compact, Standard, and Wide control sizing.
- Added scroll overflow for Automotive Log Analysis and collapsible Screenshot Evidence.
- Restored the 20-case analysis evaluation fixture.
- Added regression tests for responsive UI contracts and removed-callback failures.
- Full test suite: 88 tests passed.
