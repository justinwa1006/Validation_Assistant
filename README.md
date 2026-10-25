# 🚗 Automotive Validation Assistant

PySide6 기반의 차량용 SW(CANoe/CAN, Controller Log 등) 검증 및 AI Test Case 분석 지원 도구입니다.

## 🌟기술적 특징 (Key Engineering Highlights)

### 1. SQA 검증 스코어링 & UI 시각화
- AI 분석 결과(TOTAL SCORE) 점수 구간대별(80점 이상 / 50점 이상 / 미만) Dynamic QSS Property 적용으로 검증 상태의 직관적 시각화 지원.
- 비동기 처리 및 토스트(Toast) 메시지 시스템 도입으로 검증 진행 상황 Feedback 개선.

### 2. 모듈 독립성 및 경로 안정성 확보
- `Path(__file__).resolve().parent` 기반의 상대/절대 경로 자동 해소 로직을 구축하여 CWD(현재 작업 디렉토리) 변경에 독립적인 런처 구현.

## 📁 프로젝트 구조 (Architecture)

- `unified_launcher.py`: 통합 런처 (실시간 테마 패치, 단축키 이벤트 핸들링, Entry Point)
- `engine.py`: Validation Assistant 핵심 제어 및 AI 분석 통합 엔진
- `ui_design_system.py`: QSS 테마 관리, Dynamic Property, Toast 시스템
- `ui_main.py` & `ui_components.py`: PySide6 컴포넌트 및 도메인 UI 레이아웃
- `tc_engine.py` & `ai_engine.py`: Test Case 생성/검증 및 AI 결과 파싱
- `prompt_data.py`: 시스템 지침, 도메인 레지스트리, Few-Shot 등 프롬프트 데이터 (Qt 비의존, 테스트 대상)
- `core/`: Qt 비의존 순수 로직 (템플릿 치환, 원자적 저장, JSON 추출/복구, 결과 스키마 검증, 프롬프트 조립, UDS 디코드 등)
- `unified_window.py`: 통합 런처용 윈도우(서브클래스). 기존 런타임 몽키패치를 대체
- `tests/`: 단위 테스트, golden 프롬프트 회귀 테스트, 헤드리스 UI 구성 테스트
- `tools/`: Qt 스텁(`qt_stub.py`)과 리팩토링 전후 비교 도구 (`record_ui.py`, `golden_prompts.py`)
- `eval/`: 프롬프트 평가 스크립트와 시드 케이스

## 🛠 Tech Stack
- **Language**: Python 3.10+
- **GUI Framework**: PySide6 (Qt for Python)
- **Data & Export**: OpenPyXL, JSON
- **Domain**: Automotive SQA, Vector CANoe Log Validation

## 🚀 실행
```bash
pip install -r requirements.txt
cp .env.example .env     # GEMINI_API_KEY 입력 (.env / Try_API.env 는 git 제외)
python -m Validation_Assistant_Refactored.unified_launcher
```

## 🧪 테스트
```bash
pip install -r requirements-dev.txt
python -m pytest -q          # GUI(PySide6) 없이 실행됨
```

## 🧠 프롬프트 설계 원칙
- **근거 우선 출력**: JSON 필드 순서를 `observations/gaps/factors → result/confidence` 로 고정해 판정이 근거에서 도출되게 함.
- **TBD 정책**: 입력에 없는 임계값/신호명은 지어내지 않고 `TBD (사양 미정: ...)` 로 표기.
- **Few-Shot 균형**: PASS 뿐 아니라 FAIL / INCONCLUSIVE 예시를 포함해 앵커링을 방지.
- **인젝션 방어**: 템플릿은 single-pass 치환(`core/templating.py`)이라 사용자 입력 속 플레이스홀더가 재치환되지 않음.
- **보안 모드**: 익명화 요약 / 의미 보존 별칭(`SIG_###`) / 마스킹으로 원문 시그널 노출 최소화.
- 프롬프트 변경은 `tests/test_prompt_data.py` 구조 검사와 `eval/` 평가를 통과해야 함.

## 🔍 리팩토링 안전장치
- `tests/test_golden_prompts.py`: 도메인 3 x 모드 3 x 레벨 3 = 27개 프롬프트가 기준(`tests/golden/prompts.json`)과 같은지 검사합니다.
  의도한 프롬프트 변경이면 `UPDATE_GOLDEN=1 python -m pytest tests/test_golden_prompts.py` 로 기준을 갱신하고 diff 를 리뷰하세요.
- `tests/test_complexity_budget.py`: 새 함수가 120줄을 넘지 못하게 하고, 기존 대형 함수는 줄어들 때만 허용합니다.
- `tests/test_ui_structure.py`: 스텁 Qt 로 윈도우 구성 코드가 끝까지 실행되는지 확인합니다 (실제 렌더링 검증은 아님).

