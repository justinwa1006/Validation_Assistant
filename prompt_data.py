"""프롬프트 데이터(시스템 지침, Few-Shot, 도메인 레지스트리, 프롬프트 규칙 상수).

tc_engine.py 에서 분리한 순수 데이터 모듈이다. Qt 에 의존하지 않으므로 단독 테스트가 가능하다.
프롬프트를 바꿀 때는 tests/test_prompt_data.py 의 구조 검사를 통과해야 한다.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401  (상수 정의부의 타입 힌트용)

SYSTEM_BASE_INSTRUCTION = """You are a Principal Software Quality Assurance (SQA) Engineer.
Your primary directive is to analyze software requirements or execution logs and output strictly structured JSON specifications.

[LANGUAGE & TERMINOLOGY POLICY]
1. ALL natural language descriptions inside JSON (e.g., tc_name, summary, steps, expected_results, pass_factors, fail_factors) MUST be written in KOREAN (한국어).
2. Domain technical identifiers (signal names, API endpoints, state values, protocol names, equipment names) MUST retain their standard English/Hex notations.

[CRITICAL OUTPUT GRAMMAR]
1. Output MUST be ONLY a single valid JSON object enclosed strictly within a ```json ... ``` markdown code block.
2. Do NOT output any introductory text, explanations, notes, or markdown headings outside the code block.
3. Enum Fields: Output ONLY a single selected string choice (e.g., "PASS"). NEVER output full choice literals like "PASS | FAIL | PARTIAL".
4. Array Symmetry: The 'expected_results' array MUST have the exact same number of elements as the 'steps' array, matching 1-to-1 by index.
5. Field Order: Write JSON fields in the same order as the examples. Evidence fields (observations, gaps, factors) come BEFORE the verdict fields (result, confidence), so the verdict is derived from the evidence you already wrote.
6. Few-shot examples show FORMAT ONLY. NEVER copy their values, signal names, timestamps or numbers into your answer; use only the values present in the user input.

[QUANTITATIVE PRECISION MANDATE]
1. Every Test Step and Expected Result MUST contain precise quantitative attributes WHEN the value is given in, or directly derivable from, the user input:
   - Physical units / API Status Codes (ms, s, V, A, Hz, deg, HTTP 200, 404)
   - Logical/Comparison operators (==, !=, >=, <=, >, <)
   - Hexadecimal/Decimal/JSON state values (e.g., 0x01, 13.5V, true, false)
2. Strictly PROHIBITED ambiguous words: "약", "대략", "적절히", "확인할 것", "상응하는", "정상적으로", "properly", "roughly", "about".

[MISSING-VALUE POLICY]
1. If a required threshold, timing, state value or signal name is NOT in the user input, DO NOT invent it. Write "TBD (사양 미정: <what must be confirmed>)" in its place.
2. Do not guess behavior for conditions the specification does not define; mark it TBD and state the open question.
3. Prefer an honest INCONCLUSIVE / INSUFFICIENT evidence status over a verdict that the evidence does not support."""

FEW_SHOT_TC_CREATION = """[FEW-SHOT EXAMPLE - TC GENERATION (AUTOMOTIVE)]
Input Feature: Driver Door Unlocking
Input Requirement: BCM must process 'SW_DrvDoorUnlock' hardwire input and transition 'Sig_DrvDoorLockSt' to UNLOCKED (0x01) within 150ms when Power State is IGN_ON (0x02).
Input Acceptance: Signal transition within 150ms and no DTC generated.

Expected Output:
```json
{
  "test_cases": [
    {
      "tc_id": "TC_GEN_001",
      "category": "Positive",
      "title": "운전석 도어 잠금해제 스위치 입력 반응시간 검증",
      "preconditions": [
        "1. 차량 전원 상태: IGN_ON (CAN Signal 'Power_State' == 0x02)",
        "2. BCM 공급 전압: 13.5V ± 0.2V 정상 범위 유지"
      ],
      "steps": [
        "1. Vector CANoe를 통해 CAN 신호 'Power_State' = 0x02 인가한다.",
        "2. 운전석 도어 잠금해제 하드와이어 스위치 'SW_DrvDoorUnlock'을 LOW (0V)로 50ms 동안 입력한다.",
        "3. CAN 버스 메시지 'BCM_DoorStatus'의 'Sig_DrvDoorLockSt' 신호 상태를 관찰한다."
      ],
      "expected_results": [
        "1. Power_State 신호가 0x02 (IGN_ON)로 정상 설정된다.",
        "2. 'SW_DrvDoorUnlock' LOW (0V) 입력이 50ms 유지되는 동안 DTC가 0건 기록된다.",
        "3. 스위치 입력 시점으로부터 150ms 이내에 'Sig_DrvDoorLockSt' 신호값이 UNLOCKED (0x01)로 전이된다."
      ],
      "risk": "HIGH",
      "risk_description": "도어 잠금해제 신호 지연 시 비상 탈출 및 승하차 편의 기능에 중대한 결함 발생"
    },
    {
      "tc_id": "TC_GEN_002",
      "category": "Boundary",
      "title": "운전석 도어 잠금해제 응답시간 경계값(150ms) 반복 검증",
      "preconditions": [
        "1. 차량 전원 상태: IGN_ON (CAN Signal 'Power_State' == 0x02)",
        "2. 'Sig_DrvDoorLockSt' 초기값: LOCKED (0x00)"
      ],
      "steps": [
        "1. 'SW_DrvDoorUnlock'을 LOW (0V)로 50ms 동안 입력한다.",
        "2. 입력 시점부터 'Sig_DrvDoorLockSt'가 UNLOCKED (0x01)로 전이되기까지의 시간을 CANoe 타임스탬프로 측정한다.",
        "3. 단계 1~2를 20회 반복하고 최대 전이 시간을 기록한다."
      ],
      "expected_results": [
        "1. 매회 'SW_DrvDoorUnlock' LOW (0V) 입력이 50ms 유지된다.",
        "2. 매회 전이 시간 <= 150ms 이다.",
        "3. 20회 중 최대 전이 시간 <= 150ms 이고 150ms 초과 횟수 == 0 이다."
      ],
      "risk": "HIGH",
      "risk_description": "경계값 부근에서 간헐적으로 요구 시간을 초과하면 사양 위반이 양산 단계에서 발견될 수 있음"
    },
    {
      "tc_id": "TC_GEN_003",
      "category": "Negative",
      "title": "ACC 전원 상태에서 도어 잠금해제 입력 시 동작 (사양 미정 항목)",
      "preconditions": [
        "1. 차량 전원 상태: ACC (CAN Signal 'Power_State' == 0x01)",
        "2. 'Sig_DrvDoorLockSt' 초기값: LOCKED (0x00)"
      ],
      "steps": [
        "1. 'SW_DrvDoorUnlock'을 LOW (0V)로 50ms 동안 입력한다.",
        "2. 500ms 동안 'Sig_DrvDoorLockSt' 값을 관찰한다."
      ],
      "expected_results": [
        "1. 'SW_DrvDoorUnlock' LOW (0V) 입력이 50ms 유지된다.",
        "2. 'Sig_DrvDoorLockSt' 값 == TBD (사양 미정: ACC 상태의 동작 기준을 요구사항에서 확인 필요)."
      ],
      "risk": "MEDIUM",
      "risk_description": "입력 사양에 IGN_ON 외 전원 상태의 기대 동작이 없어 판정 기준을 임의로 확정하지 않음"
    }
  ]
}
```"""

FEW_SHOT_TC_CREATION_WEB_API = """[FEW-SHOT EXAMPLE - TC GENERATION (WEB/API)]
Input Feature: User Authentication API
Input Requirement: POST /api/v1/auth/login must validate credentials and return HTTP 200 with JWT token within 200ms for valid credentials.
Input Acceptance: Return HTTP 200 with valid JWT payload within 200ms.

Expected Output:
```json
{
  "test_cases": [
    {
      "tc_id": "TC_API_001",
      "category": "Positive",
      "title": "사용자 로그인 API 정상 응답 및 토큰 발급 검증",
      "preconditions": [
        "1. 인증 서비스 정상 가동 중 (HTTP Status 200)",
        "2. 테스트용 유효 계정(user@test.com) 사전 준비 완료"
      ],
      "steps": [
        "1. POST /api/v1/auth/login 요청 바디에 올바른 ID/PW를 실어 전송한다.",
        "2. 응답 HTTP Status Code 및 Header의 Content-Type을 확인한다.",
        "3. Response Body 내 accessToken 존재 여부 및 응답 시간을 확인한다."
      ],
      "expected_results": [
        "1. HTTP Status Code == 200 OK 수신",
        "2. Response Header Content-Type == application/json",
        "3. 200ms 이내 유효한 JWT accessToken이 포함된 JSON 응답 수신"
      ],
      "risk": "HIGH",
      "risk_description": "인증 실패 시 시스템 전체 접근 불능"
    }
  ]
}
```"""

FEW_SHOT_VALIDATION_ANALYSIS = """[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS]
Input TC Name: TC_BCM_DOOR_001
Input Purpose: Verify IGN_ON state transition and door unlock signal delay < 150ms.
Input Evidence Log: Timestamp 10.000s: Power_State=0x02, Timestamp 10.050s: SW_DrvDoorUnlock=0V, Timestamp 10.130s: Sig_DrvDoorLockSt=0x01.

Expected Output:
```json
{
  "evidence_status": "SUFFICIENT",
  "evidence_coverage": {
    "required_items": 2,
    "verified_items": 2,
    "coverage_percent": 100,
    "missing_items": []
  },
  "observations": [
    "10.000s: Power_State == 0x02 수신",
    "10.050s: SW_DrvDoorUnlock == 0V 인가",
    "10.130s: Sig_DrvDoorLockSt == 0x01 전이 완료"
  ],
  "gaps": [],
  "pass_factors": [
    "스위치 입력 후 80ms 시점에 신호 전이 완료 (80ms <= 150ms)",
    "CAN 버스 에러 프레임 미발생"
  ],
  "fail_factors": [],
  "result": "PASS",
  "confidence": "HIGH",
  "confidence_reason": [
    "BLF 로그 분석 결과, 스위치 입력(10.050s) 후 80ms 시점(10.130s)에 Sig_DrvDoorLockSt 신호가 0x01로 전이됨을 확인함 (기대 기준: 150ms 이내)"
  ],
  "risk": "LOW",
  "summary": "운전석 도어 잠금해제 신호전이 응답시간이 80ms로 측정되어 요구사항(150ms 이내)을 충족함.",
  "recommended_verification": [
    "1. 전압 변동 조건(9.0V ~ 16.0V)에서의 응답시간 한계 검증 추가",
    "2. CAN 버스 로드율 80% 상태에서의 지연시간 비교 측정"
  ]
}
```"""

# ------------------------------------------------------------------------------
# 도메인 레지스트리: 새 도메인은 아래 딕셔너리에 항목만 추가하면 된다.
#   - DOMAIN_SYSTEM_ADDENDUM : 도메인 전용 용어/표기 규칙 (System Instruction 뒤에 결합)
#   - FEW_SHOTS              : 모드별 Few-Shot ("generation" | "analysis")
#   - DOMAIN_LEVEL_EXTRA     : Prompt Level 별 도메인 추가 지침
# 프로필(dict)에 "key", "few_shot", "level_scope" 가 있으면 그 값이 우선한다.
# ------------------------------------------------------------------------------

DEFAULT_DOMAIN_KEY = "automotive"

DOMAIN_SYSTEM_ADDENDUM = {
    "automotive": """[DOMAIN TERMINOLOGY - AUTOMOTIVE]
- CAN/LIN 시그널명(예: Sig_DrvDoorLockSt), ECU 전원 상태(예: IGN_ON, 0x02), UDS 서비스/NRC는 영문/Hex 원문 표기를 유지한다.
- 전압(V), 전류(A), 시간(ms), 주파수(Hz)는 단위와 허용 오차를 함께 명시한다.""",
    "web_api": """[DOMAIN TERMINOLOGY - WEB/API]
- HTTP Method, Endpoint, Status Code, Header, JSON Path 필드명은 영문 원문 표기를 유지한다.
- 응답시간(ms), 페이로드 크기(bytes), 재시도 횟수는 수치와 비교 연산자로 명시한다.""",
}

FEW_SHOT_VALIDATION_ANALYSIS_WEB_API = """[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS (WEB/API)]
Input TC Name: TC_API_AUTH_001
Input Purpose: Verify POST /api/v1/auth/login returns HTTP 200 with JWT accessToken within 200ms for valid credentials.
Input Evidence Log: 12:00:00.000 POST /api/v1/auth/login sent, 12:00:00.145 HTTP 200 received, Content-Type: application/json, body.accessToken present (length 187).

Expected Output:
```json
{
  "evidence_status": "SUFFICIENT",
  "evidence_coverage": {
    "required_items": 3,
    "verified_items": 3,
    "coverage_percent": 100,
    "missing_items": []
  },
  "observations": [
    "12:00:00.000: POST /api/v1/auth/login 요청 전송",
    "12:00:00.145: HTTP 200 응답 수신, Content-Type == application/json",
    "응답 Body: accessToken 길이 187"
  ],
  "gaps": [],
  "pass_factors": [
    "HTTP Status Code == 200 수신",
    "응답시간 145ms <= 200ms",
    "Response Body에 accessToken 존재"
  ],
  "fail_factors": [],
  "result": "PASS",
  "confidence": "HIGH",
  "confidence_reason": [
    "요청 로그(12:00:00.000)와 응답 로그(12:00:00.145)를 비교한 결과 응답시간 145ms로 측정됨 (기대 기준: 200ms 이내)"
  ],
  "risk": "LOW",
  "summary": "로그인 API가 HTTP 200과 accessToken을 145ms에 반환하여 요구사항(200ms 이내)을 충족함.",
  "recommended_verification": [
    "1. 잘못된 비밀번호 입력 시 HTTP 401 반환 및 응답시간 <= 200ms 검증 추가",
    "2. 동시 요청 100건(RPS 100) 조건에서 p95 응답시간 비교 측정"
  ]
}
```"""

FEW_SHOTS = {
    "automotive": {
        "generation": FEW_SHOT_TC_CREATION,
        "analysis": FEW_SHOT_VALIDATION_ANALYSIS,
    },
    "web_api": {
        "generation": FEW_SHOT_TC_CREATION_WEB_API,
        "analysis": FEW_SHOT_VALIDATION_ANALYSIS_WEB_API,
    },
}

LEVEL_SCOPE_COMMON = {
    "Basic": (
        "- 정상 시나리오(Positive), 기본 실패 시나리오(Basic Negative), 핵심 상태 전이(State Transition) 위주로 생성한다.\n"
        "- 각 TC는 tc_id, category, title, preconditions, steps, expected_results, risk, risk_description을 포함한다."
    ),
    "Detailed": (
        "- Positive, Negative, Boundary Value, State Transition, Timeout, Retry, Recovery 관점의 테스트 시나리오를 포함한다.\n"
        "- 시간/수치/상태값 경계 조건(Boundary Conditions)을 정량적 수치로 구체화한다."
    ),
    "Expert": (
        "- 동등 분할(Equivalence Partitioning), 경계값 분석(BVA), 결정 테이블(Decision Table), Fault Injection 조건을 포함한다."
    ),
}

DOMAIN_LEVEL_EXTRA = {
    "automotive": {
        "Detailed": "- 전압/신호값 경계 조건을 정량적 수치로 포함한다.",
        "Expert": "- Communication Loss, Power Cycle 조건을 포함하고, 차량 통신 지연시간 및 세션 타임아웃 오차범위를 정량적으로 포함한다.",
    },
    "web_api": {
        "Detailed": "- 요청 필드 길이/범위, 페이로드 크기(bytes), 응답시간(ms) 경계 조건을 포함한다.",
        "Expert": "- 인증 만료, 동시 요청, Rate Limit(HTTP 429), 5xx 장애 후 복구 조건을 포함하고, 응답시간(ms) 오차범위를 정량적으로 포함한다.",
    },
}

# ------------------------------------------------------------------------------
# 추가 도메인: mobile_app / embedded_fw / db_backend / network_protocol
# 새 도메인을 더 늘릴 때도 아래와 같은 순서로 등록한다.
#   1) Few-Shot(generation, analysis)  2) DOMAIN_SYSTEM_ADDENDUM  3) DOMAIN_LEVEL_EXTRA
#   4) DOMAIN_DEFAULTS(프로필에 role/rules 가 없을 때 쓰는 기본값)  5) _DOMAIN_NAME_PATTERNS
# ------------------------------------------------------------------------------

FEW_SHOT_TC_CREATION_MOBILE_APP = """[FEW-SHOT EXAMPLE - TC GENERATION (MOBILE APP)]
Input Feature: Push Notification Deep Link
Input Requirement: When the user taps a push notification containing 'myapp://order/12345' while the app process is terminated, the app must cold start and display the Order Detail screen within 2000ms.
Input Acceptance: Order Detail screen shows order number 12345 within 2000ms and no crash or ANR occurs.

Expected Output:
```json
{
  "test_cases": [
    {
      "tc_id": "TC_APP_001",
      "category": "Positive",
      "title": "앱 종료 상태에서 푸시 알림 딥링크 진입 시 주문 상세 화면 표시 검증",
      "preconditions": [
        "1. 단말: Android 14 (Pixel 8), 앱 버전 3.2.0 설치 및 로그인 완료",
        "2. 앱 프로세스 종료 상태 (최근 앱 목록에서 제거), 네트워크 Wi-Fi 연결 (RTT <= 50ms)",
        "3. 알림 권한 'android.permission.POST_NOTIFICATIONS' == GRANTED"
      ],
      "steps": [
        "1. 테스트 서버에서 딥링크 'myapp://order/12345'를 포함한 푸시 알림을 단말로 전송한다.",
        "2. 알림 센터에 표시된 알림을 탭하고 탭 시점부터 화면 표시까지의 시간을 측정한다.",
        "3. 표시된 화면의 제목 요소 'tv_order_title'과 주문번호 텍스트를 확인한다."
      ],
      "expected_results": [
        "1. 푸시 알림이 10s 이내 수신되어 알림 센터에 1건 표시된다.",
        "2. 앱이 Cold Start로 실행되어 주문 상세 화면(OrderDetailActivity)이 탭 시점으로부터 2000ms 이내 표시된다.",
        "3. 'tv_order_title' 요소가 visible == true 이고 주문번호 == 12345 로 표시되며, 크래시와 ANR이 0건 발생한다."
      ],
      "risk": "MEDIUM",
      "risk_description": "딥링크 처리 실패 시 알림으로 유입된 사용자가 주문 정보에 접근하지 못해 전환율 저하 발생"
    }
  ]
}
```"""

FEW_SHOT_VALIDATION_ANALYSIS_MOBILE_APP = """[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS (MOBILE APP)]
Input TC Name: TC_APP_LAUNCH_001
Input Purpose: Verify cold start to the Home screen is displayed within 2000ms on Android 14.
Input Evidence Log: Logcat 14:20:01.000 ActivityTaskManager START com.example.app/.MainActivity, 14:20:03.420 ActivityTaskManager Displayed com.example.app/.MainActivity: +2s420ms, no FATAL EXCEPTION or ANR entries, Device Pixel 8 Android 14.

Expected Output:
```json
{
  "evidence_status": "SUFFICIENT",
  "evidence_coverage": {
    "required_items": 2,
    "verified_items": 2,
    "coverage_percent": 100,
    "missing_items": []
  },
  "observations": [
    "14:20:01.000: MainActivity START 기록",
    "14:20:03.420: MainActivity Displayed +2s420ms 기록",
    "단말/OS: Pixel 8, Android 14 확인"
  ],
  "gaps": [
    "단말 온도 및 백그라운드 프로세스 수 정보가 로그에 없음"
  ],
  "pass_factors": [
    "FATAL EXCEPTION 및 ANR 로그 0건"
  ],
  "fail_factors": [
    "Cold Start 2420ms > 2000ms (420ms 초과)"
  ],
  "result": "FAIL",
  "confidence": "HIGH",
  "confidence_reason": [
    "Logcat의 Displayed 로그에서 Cold Start 시간이 2420ms로 측정됨 (기대 기준: 2000ms 이내)"
  ],
  "risk": "MEDIUM",
  "summary": "Cold Start 시간이 2420ms로 측정되어 요구사항(2000ms 이내)을 420ms 초과함.",
  "recommended_verification": [
    "1. 동일 조건에서 Cold Start를 10회 반복 측정하여 평균과 최대값이 2000ms 이내인지 확인",
    "2. 저사양 단말(RAM 4GB 이하) 및 Android 12 조건에서 Cold Start 시간 비교 측정"
  ]
}
```"""

FEW_SHOT_TC_CREATION_EMBEDDED_FW = """[FEW-SHOT EXAMPLE - TC GENERATION (EMBEDDED FIRMWARE)]
Input Feature: UART RX Interrupt Response
Input Requirement: The MCU (168MHz) must raise the UART2 RXNE interrupt after the last byte of an 8-byte frame is received at 115200bps, and the ISR must set GPIO PA5 to HIGH within 50us after the end of the last stop bit.
Input Acceptance: PA5 rises within 50us and no framing or overrun error occurs.

Expected Output:
```json
{
  "test_cases": [
    {
      "tc_id": "TC_FW_001",
      "category": "Positive",
      "title": "UART2 수신 완료 인터럽트 ISR의 GPIO 응답시간 검증",
      "preconditions": [
        "1. 보드 공급 전압 3.3V ± 0.1V, 시스템 클럭 168MHz, 펌웨어 v1.4.2 기록 완료",
        "2. UART2 설정: 115200bps, 8N1, GPIO PA5 초기 레벨 LOW (<= 0.4V)",
        "3. 로직 애널라이저 2채널(UART2_RX, PA5) 연결, 샘플링 레이트 24MHz"
      ],
      "steps": [
        "1. 보드를 Power On 하고 GPIO PA5의 레벨을 측정한다.",
        "2. 호스트에서 UART2_RX로 0x01~0x08 8바이트 프레임을 115200bps로 전송한다.",
        "3. 로직 애널라이저로 마지막 바이트(0x08)의 stop bit 종료 시점과 PA5 Rising Edge 시점 간 간격을 측정한다."
      ],
      "expected_results": [
        "1. PA5 레벨 == LOW (<= 0.4V)로 측정된다.",
        "2. 8바이트가 모두 수신되어 수신 카운터 == 8 이고, 에러 플래그 SR.FE == 0, SR.ORE == 0 이다.",
        "3. PA5 Rising Edge가 stop bit 종료로부터 50us 이내 발생하고 (간격 <= 50us), PA5 레벨 >= 2.4V 이다."
      ],
      "risk": "HIGH",
      "risk_description": "ISR 응답 지연 시 후속 프레임 수신 누락 및 제어 주기 위반 발생"
    }
  ]
}
```"""

FEW_SHOT_VALIDATION_ANALYSIS_EMBEDDED_FW = """[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS (EMBEDDED FIRMWARE)]
Input TC Name: TC_FW_UART_001
Input Purpose: Verify GPIO PA5 rises within 50us after the end of the last stop bit of an 8-byte UART2 frame.
Input Evidence Log: Logic analyzer capture (24MHz) t=0.000000s end of last stop bit on UART2_RX, t=0.000032s PA5 rising edge to 3.3V. Serial log: rx_count=8, SR.FE=0, SR.ORE=0.

Expected Output:
```json
{
  "evidence_status": "SUFFICIENT",
  "evidence_coverage": {
    "required_items": 2,
    "verified_items": 2,
    "coverage_percent": 100,
    "missing_items": []
  },
  "observations": [
    "0.000000s: UART2_RX 마지막 stop bit 종료",
    "0.000032s: PA5 Rising Edge, 레벨 3.3V",
    "시리얼 로그: rx_count == 8, SR.FE == 0, SR.ORE == 0"
  ],
  "gaps": [],
  "pass_factors": [
    "PA5 응답시간 32us <= 50us",
    "rx_count == 8, SR.FE == 0, SR.ORE == 0"
  ],
  "fail_factors": [],
  "result": "PASS",
  "confidence": "HIGH",
  "confidence_reason": [
    "로직 애널라이저 캡처에서 마지막 stop bit 종료(0.000000s) 후 32us 시점(0.000032s)에 PA5 Rising Edge가 확인됨 (기대 기준: 50us 이내)"
  ],
  "risk": "LOW",
  "summary": "PA5 응답시간이 32us로 측정되어 요구사항(50us 이내)을 충족함.",
  "recommended_verification": [
    "1. 공급 전압 경계(3.0V, 3.6V) 조건에서 PA5 응답시간 측정 추가",
    "2. 연속 프레임 1000회 전송 시 최대 응답시간(us) 및 프레임 누락 건수 측정"
  ]
}
```"""

FEW_SHOT_TC_CREATION_DB_BACKEND = """[FEW-SHOT EXAMPLE - TC GENERATION (DB / BACKEND)]
Input Feature: Order Save Transaction
Input Requirement: When an order is created, one row in 'orders' and N rows in 'order_items' must be saved in a single transaction. If saving any order_items row fails, the whole transaction including 'orders' must be rolled back.
Input Acceptance: On failure, row counts of both tables do not increase and the API returns HTTP 422.

Expected Output:
```json
{
  "test_cases": [
    {
      "tc_id": "TC_DB_001",
      "category": "Negative",
      "title": "order_items 저장 실패 시 주문 트랜잭션 전체 롤백 검증",
      "preconditions": [
        "1. DB: PostgreSQL 15, 격리 수준 READ COMMITTED, orders 및 order_items 테이블 row 수 각각 0건",
        "2. order_items.product_id 에 FK 제약(products.id) 설정, products.id == 9999 레코드는 존재하지 않음"
      ],
      "steps": [
        "1. POST /api/v1/orders 요청에 items=[{product_id: 1, qty: 1}, {product_id: 9999, qty: 1}]를 담아 전송한다.",
        "2. 응답의 HTTP Status Code와 에러 코드를 확인한다.",
        "3. SELECT COUNT(*) FROM orders; 와 SELECT COUNT(*) FROM order_items; 를 실행한다."
      ],
      "expected_results": [
        "1. 서버 로그에 트랜잭션 BEGIN 이 1건 기록된다.",
        "2. HTTP Status Code == 422 이고 에러 코드 == FK_VIOLATION 이며 응답시간 <= 500ms 이다.",
        "3. orders COUNT == 0, order_items COUNT == 0 이고 서버 로그에 ROLLBACK 이 1건 기록된다."
      ],
      "risk": "HIGH",
      "risk_description": "부분 저장 시 주문 헤더만 존재하는 고아 데이터가 발생하여 정산 불일치 초래"
    }
  ]
}
```"""

FEW_SHOT_VALIDATION_ANALYSIS_DB_BACKEND = """[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS (DB / BACKEND)]
Input TC Name: TC_DB_BATCH_001
Input Purpose: Verify the nightly settlement batch copies all rows from staging.settlement_raw to settlement within 600s with identical row counts.
Input Evidence Log: Batch log 02:00:00 JOB_START settle_daily, 02:08:41 JOB_END status=SUCCESS elapsed=521s. Query result: SELECT COUNT(*) FROM staging.settlement_raw = 1000000, SELECT COUNT(*) FROM settlement = 999987.

Expected Output:
```json
{
  "evidence_status": "SUFFICIENT",
  "evidence_coverage": {
    "required_items": 3,
    "verified_items": 3,
    "coverage_percent": 100,
    "missing_items": []
  },
  "observations": [
    "02:00:00: JOB_START settle_daily 기록",
    "02:08:41: JOB_END status == SUCCESS, elapsed == 521s 기록",
    "COUNT 비교: staging.settlement_raw == 1000000, settlement == 999987"
  ],
  "gaps": [
    "누락된 13건의 키 목록과 스킵 또는 에러 처리 로그가 없음"
  ],
  "pass_factors": [
    "배치 처리시간 521s <= 600s",
    "배치 종료 상태 == SUCCESS"
  ],
  "fail_factors": [
    "건수 불일치: 1,000,000 != 999,987 (13건 누락)"
  ],
  "result": "FAIL",
  "confidence": "HIGH",
  "confidence_reason": [
    "소스 테이블 1,000,000건 대비 타깃 테이블 999,987건으로 13건 불일치함 (기대 기준: 소스 건수 == 타깃 건수)"
  ],
  "risk": "HIGH",
  "summary": "배치가 SUCCESS로 종료되었으나 타깃에 13건이 누락되어 정합성 요구사항을 충족하지 못함.",
  "recommended_verification": [
    "1. NOT EXISTS 조회로 소스 대비 타깃에 없는 13건의 키를 추출하여 누락 원인 확인",
    "2. 배치 종료 시 소스/타깃 건수 비교 단계를 추가하고 불일치 건수 > 0 이면 status == FAILED 로 종료되는지 검증"
  ]
}
```"""

FEW_SHOT_TC_CREATION_NETWORK_PROTOCOL = """[FEW-SHOT EXAMPLE - TC GENERATION (NETWORK / PROTOCOL)]
Input Feature: MQTT Keep Alive
Input Requirement: With Keep Alive set to 60s and no other packets sent, the MQTT v3.1.1 client must send PINGREQ at 60s ± 1s intervals and receive PINGRESP from the broker within 1000ms.
Input Acceptance: PINGREQ interval is 60s ± 1s, PINGRESP delay is within 1000ms, and the TCP connection stays open.

Expected Output:
```json
{
  "test_cases": [
    {
      "tc_id": "TC_NET_001",
      "category": "Positive",
      "title": "Keep Alive 주기 PINGREQ 전송 및 PINGRESP 수신 검증",
      "preconditions": [
        "1. 브로커: Mosquitto 2.0, 포트 1883, 클라이언트 CONNECT 설정 Keep Alive == 60s, Clean Session == 1",
        "2. 네트워크 지연 <= 20ms, 패킷 손실률 == 0%, Wireshark로 클라이언트 NIC 패킷 캡처 시작"
      ],
      "steps": [
        "1. 클라이언트가 CONNECT 패킷을 전송하고 CONNACK 수신 후 구독과 발행 없이 대기한다.",
        "2. 패킷 캡처에서 CONNACK 이후 첫 PINGREQ(0xC0) 전송 시각을 확인한다.",
        "3. PINGREQ 전송 시각부터 PINGRESP(0xD0) 수신 시각까지의 지연을 측정한다."
      ],
      "expected_results": [
        "1. CONNACK Return Code == 0x00 을 수신하고 연결 상태 == Connected 이다.",
        "2. CONNACK 수신 후 PINGREQ(0xC0)가 59s <= 간격 <= 61s 범위에서 전송된다.",
        "3. PINGRESP(0xD0)가 PINGREQ 후 1000ms 이내 수신되고, TCP RST 및 FIN 패킷이 0건이다."
      ],
      "risk": "MEDIUM",
      "risk_description": "Keep Alive 실패 시 단말이 오프라인으로 오인되어 명령 수신 불가"
    }
  ]
}
```"""

FEW_SHOT_VALIDATION_ANALYSIS_NETWORK_PROTOCOL = """[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS (NETWORK / PROTOCOL)]
Input TC Name: TC_NET_MQTT_001
Input Purpose: Verify the client sends PINGREQ at 60s +- 1s and receives PINGRESP within 1000ms with Keep Alive 60s.
Input Evidence Log: pcap No.12 t=0.000s CONNACK RC=0x00, No.31 t=60.012s PINGREQ (0xC0), No.32 t=60.047s PINGRESP (0xD0), no TCP RST or FIN in capture window 0s~120s.

Expected Output:
```json
{
  "evidence_status": "SUFFICIENT",
  "evidence_coverage": {
    "required_items": 3,
    "verified_items": 3,
    "coverage_percent": 100,
    "missing_items": []
  },
  "observations": [
    "0.000s: CONNACK Return Code == 0x00 수신",
    "60.012s: PINGREQ (0xC0) 전송",
    "60.047s: PINGRESP (0xD0) 수신"
  ],
  "gaps": [],
  "pass_factors": [
    "PINGREQ 간격 60.012s (59s <= 간격 <= 61s)",
    "PINGRESP 지연 35ms <= 1000ms",
    "캡처 구간 0s~120s 동안 TCP RST 및 FIN 0건"
  ],
  "fail_factors": [],
  "result": "PASS",
  "confidence": "HIGH",
  "confidence_reason": [
    "pcap에서 CONNACK(0.000s) 후 60.012s에 PINGREQ가 전송되고 35ms 뒤(60.047s) PINGRESP가 수신됨 (기대 기준: 60s ± 1s, 1000ms 이내)"
  ],
  "risk": "LOW",
  "summary": "PINGREQ 간격 60.012s, PINGRESP 지연 35ms로 측정되어 요구사항을 충족함.",
  "recommended_verification": [
    "1. 패킷 손실률 5% 조건에서 PINGRESP 지연 및 재전송 횟수 측정 추가",
    "2. 브로커 응답 차단 시 Keep Alive의 1.5배(90s) 이내 연결 종료 및 재연결 동작 검증 추가"
  ]
}
```"""

FEW_SHOTS.update({
    "mobile_app": {
        "generation": FEW_SHOT_TC_CREATION_MOBILE_APP,
        "analysis": FEW_SHOT_VALIDATION_ANALYSIS_MOBILE_APP,
    },
    "embedded_fw": {
        "generation": FEW_SHOT_TC_CREATION_EMBEDDED_FW,
        "analysis": FEW_SHOT_VALIDATION_ANALYSIS_EMBEDDED_FW,
    },
    "db_backend": {
        "generation": FEW_SHOT_TC_CREATION_DB_BACKEND,
        "analysis": FEW_SHOT_VALIDATION_ANALYSIS_DB_BACKEND,
    },
    "network_protocol": {
        "generation": FEW_SHOT_TC_CREATION_NETWORK_PROTOCOL,
        "analysis": FEW_SHOT_VALIDATION_ANALYSIS_NETWORK_PROTOCOL,
    },
})

FEW_SHOT_VALIDATION_ANALYSIS_EDGE_AUTOMOTIVE = """[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS - FAIL CASE]
Input TC Name: TC_BCM_DOOR_002
Input Purpose: Verify door unlock signal delay <= 150ms after unlock switch input.
Input Evidence Log: Timestamp 20.000s: Power_State=0x02, Timestamp 20.050s: SW_DrvDoorUnlock=0V, Timestamp 20.260s: Sig_DrvDoorLockSt=0x01.

Expected Output:
```json
{
  "evidence_status": "SUFFICIENT",
  "evidence_coverage": {
    "required_items": 2,
    "verified_items": 2,
    "coverage_percent": 100,
    "missing_items": []
  },
  "observations": [
    "20.000s: Power_State == 0x02 수신",
    "20.050s: SW_DrvDoorUnlock == 0V 인가",
    "20.260s: Sig_DrvDoorLockSt == 0x01 전이 (입력 후 210ms)"
  ],
  "gaps": [],
  "pass_factors": [
    "Power_State == 0x02 조건 충족"
  ],
  "fail_factors": [
    "전이 시간 210ms > 기준 150ms (60ms 초과)"
  ],
  "result": "FAIL",
  "confidence": "HIGH",
  "confidence_reason": [
    "필요 증적 2/2 확인, 측정값(210ms)이 기준(150ms)을 명확히 초과함"
  ],
  "risk": "HIGH",
  "summary": "운전석 도어 잠금해제 전이 시간이 210ms로 측정되어 요구사항(150ms 이내)을 충족하지 못함.",
  "recommended_verification": [
    "1. 동일 조건 20회 반복 측정으로 초과가 재현되는지 확인 (초과 횟수 == 0 여부)",
    "2. 입력 시점과 BCM 내부 처리 시점을 분리 측정할 수 있는지 확인 (TBD: 측정 지점 사양)"
  ]
}
```

[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS - INSUFFICIENT EVIDENCE CASE]
Input TC Name: TC_BCM_DOOR_003
Input Purpose: Verify door unlock signal delay <= 150ms after unlock switch input.
Input Evidence Log: Timestamp 30.050s: SW_DrvDoorUnlock=0V. (Sig_DrvDoorLockSt log not provided)

Expected Output:
```json
{
  "evidence_status": "INSUFFICIENT",
  "evidence_coverage": {
    "required_items": 2,
    "verified_items": 1,
    "coverage_percent": 50,
    "missing_items": ["Sig_DrvDoorLockSt 전이 시점 로그"]
  },
  "observations": [
    "30.050s: SW_DrvDoorUnlock == 0V 인가"
  ],
  "gaps": [
    "Sig_DrvDoorLockSt 전이 시점이 없어 응답시간(<= 150ms)을 계산할 수 없음"
  ],
  "pass_factors": [],
  "fail_factors": [],
  "result": "INCONCLUSIVE",
  "confidence": "LOW",
  "confidence_reason": [
    "필요 증적 1/2만 확인되어 PASS/FAIL 어느 쪽도 증적으로 뒷받침되지 않음"
  ],
  "risk": "MEDIUM",
  "summary": "응답 신호 로그가 없어 응답시간을 판정할 수 없음. 증적 보완 후 재판정 필요.",
  "recommended_verification": [
    "1. 동일 구간의 Sig_DrvDoorLockSt 로그(타임스탬프 포함)를 첨부하여 재분석"
  ]
}
```"""

FEW_SHOT_VALIDATION_ANALYSIS_EDGE_COMMON = """[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS - FAIL CASE (DOMAIN-NEUTRAL)]
Input TC Name: TC_GENERIC_RESP_001
Input Purpose: Verify the response completes within 200ms.
Input Evidence Log: request sent at T+0ms, response received at T+480ms, status OK.

Expected Output:
```json
{
  "evidence_status": "SUFFICIENT",
  "evidence_coverage": {
    "required_items": 2,
    "verified_items": 2,
    "coverage_percent": 100,
    "missing_items": []
  },
  "observations": [
    "T+0ms: 요청 전송",
    "T+480ms: 응답 수신, 상태 OK"
  ],
  "gaps": [],
  "pass_factors": [
    "응답 상태 OK 확인"
  ],
  "fail_factors": [
    "응답 시간 480ms > 기준 200ms (280ms 초과)"
  ],
  "result": "FAIL",
  "confidence": "HIGH",
  "confidence_reason": [
    "필요 증적 2/2 확인, 측정값(480ms)이 기준(200ms)을 명확히 초과함"
  ],
  "risk": "MEDIUM",
  "summary": "응답은 정상 수신되었으나 480ms가 소요되어 기준(200ms 이내)을 충족하지 못함.",
  "recommended_verification": [
    "1. 동일 조건 20회 반복 측정으로 지연이 재현되는지 확인 (200ms 초과 횟수 == 0 여부)"
  ]
}
```

[FEW-SHOT EXAMPLE - VALIDATION ANALYSIS - INSUFFICIENT EVIDENCE CASE (DOMAIN-NEUTRAL)]
Input TC Name: TC_GENERIC_RESP_002
Input Purpose: Verify the response completes within 200ms.
Input Evidence Log: request sent at T+0ms. (response log not provided)

Expected Output:
```json
{
  "evidence_status": "INSUFFICIENT",
  "evidence_coverage": {
    "required_items": 2,
    "verified_items": 1,
    "coverage_percent": 50,
    "missing_items": ["응답 수신 시점 로그"]
  },
  "observations": [
    "T+0ms: 요청 전송"
  ],
  "gaps": [
    "응답 수신 시점이 없어 응답 시간(<= 200ms)을 계산할 수 없음"
  ],
  "pass_factors": [],
  "fail_factors": [],
  "result": "INCONCLUSIVE",
  "confidence": "LOW",
  "confidence_reason": [
    "필요 증적 1/2만 확인되어 판정을 뒷받침하지 못함"
  ],
  "risk": "MEDIUM",
  "summary": "응답 수신 로그가 없어 판정할 수 없음. 증적 보완 후 재판정 필요.",
  "recommended_verification": [
    "1. 응답 수신 타임스탬프가 포함된 로그를 첨부하여 재분석"
  ]
}
```"""


# 분석 few-shot 에 FAIL / INCONCLUSIVE 예시를 덧붙인다 (PASS 예시 하나만 있으면 모델이 PASS 로 앵커링됨).
FEW_SHOTS["automotive"]["analysis"] += "\n\n" + FEW_SHOT_VALIDATION_ANALYSIS_EDGE_AUTOMOTIVE
for _domain_key, _shots in FEW_SHOTS.items():
    if _domain_key != "automotive":
        _shots["analysis"] += "\n\n" + FEW_SHOT_VALIDATION_ANALYSIS_EDGE_COMMON


DOMAIN_SYSTEM_ADDENDUM.update({
    "mobile_app": """[DOMAIN TERMINOLOGY - MOBILE APP]
- OS/버전(Android 14, iOS 17), 화면/컴포넌트 ID, 권한명(예: android.permission.POST_NOTIFICATIONS), 딥링크 URI, API Endpoint는 영문 원문 표기를 유지한다.
- 응답시간(ms), 앱 실행시간(Cold/Warm Start), 메모리(MB), 배터리 잔량(%), 네트워크 상태(Wi-Fi/LTE/Offline)를 수치와 비교 연산자로 명시한다.""",
    "embedded_fw": """[DOMAIN TERMINOLOGY - EMBEDDED FIRMWARE / HW INTERFACE]
- 레지스터 주소(예: 0x40020000), 비트 필드, GPIO 핀명(예: PA5), 인터럽트/타이머 식별자, 통신 버스(I2C/SPI/UART)는 영문/Hex 원문 표기를 유지한다.
- 전압(V), 전류(mA), 클럭(MHz), 타이밍(us/ms), 전송속도(bps)는 허용 오차와 함께 명시한다.""",
    "db_backend": """[DOMAIN TERMINOLOGY - DB / BACKEND DATA PROCESSING]
- 테이블/컬럼명, SQL 구문, 트랜잭션 격리 수준(예: READ COMMITTED), 큐/토픽명, 배치 Job ID는 영문 원문 표기를 유지한다.
- 처리 건수(rows), 처리 시간(ms/s), 처리량(TPS), 데이터 크기(MB), 재시도 횟수를 수치와 비교 연산자로 명시한다.""",
    "network_protocol": """[DOMAIN TERMINOLOGY - NETWORK / COMMUNICATION PROTOCOL]
- 프로토콜명(TCP, UDP, MQTT, Modbus, BLE 등), 포트 번호, 패킷/프레임 필드명, 메시지 타입, 상태 머신 상태명, 에러 코드는 영문/Hex 원문 표기를 유지한다.
- 지연시간(ms), 패킷 손실률(%), 처리량(Mbps), 타임아웃(s), 재전송 횟수를 허용 오차와 함께 명시한다.""",
})

DOMAIN_LEVEL_EXTRA.update({
    "mobile_app": {
        "Detailed": "- OS 버전, 화면 방향(Portrait/Landscape), 네트워크 상태(Wi-Fi/LTE/Offline) 조합의 경계 조건을 포함한다.",
        "Expert": "- 권한 거부/철회, 백그라운드 전환 및 프로세스 종료 후 복구, 푸시 알림 수신, 저메모리 및 배터리 잔량 15% 이하 조건을 포함하고, 앱 실행시간(ms) 오차범위를 정량적으로 포함한다.",
    },
    "embedded_fw": {
        "Detailed": "- 전원 전압, 클럭, 온도 경계 조건과 타이머/인터럽트 타이밍 경계를 정량적 수치로 포함한다.",
        "Expert": "- 전원 Brown-out, Watchdog Reset, 인터럽트 중첩, 버스 오류(NACK, Framing Error), 플래시 쓰기 중 전원 차단 조건을 포함하고, 타이밍 오차범위(us)를 정량적으로 포함한다.",
    },
    "db_backend": {
        "Detailed": "- 데이터 건수(0건, 1건, 최대 건수), 컬럼 길이/범위, NULL 및 중복 키 경계 조건을 포함한다.",
        "Expert": "- 동시 트랜잭션 충돌(Deadlock, Lock Timeout), 롤백, 부분 실패 후 재처리(멱등성), 1,000,000건 이상 대용량 배치 조건을 포함하고, 처리시간(ms)과 건수 일치 기준을 정량적으로 포함한다.",
    },
    "network_protocol": {
        "Detailed": "- 패킷 크기(최소/최대 MTU), 타임아웃, 재전송 횟수, 지연 및 손실률 경계 조건을 정량적 수치로 포함한다.",
        "Expert": "- 패킷 손실/중복/순서 뒤바뀜, 연결 끊김 후 재연결, 잘못된 필드 값(Malformed Packet), 프로토콜 상태 머신의 비정상 전이 조건을 포함하고, 지연시간과 타임아웃 오차범위를 정량적으로 포함한다.",
    },
})

# 프로필(current_domain_profile)에 role / *_rules 가 없을 때 사용하는 도메인 기본값.
# 프로필에 값이 있으면 프로필이 항상 우선한다.
DOMAIN_DEFAULTS = {
    "mobile_app": {
        "role": "Mobile App (Android/iOS) Quality Assurance Specialist",
        "generation_rules": [
            "대상 OS/버전과 단말 조건(해상도, 화면 방향, 네트워크 상태)을 Precondition에 명시한다.",
            "화면 전환, 권한 요청 팝업, 백그라운드/포그라운드 전환, 푸시 알림 시나리오를 구분하여 Step으로 작성한다.",
            "UI 확인은 화면 요소 ID/텍스트와 표시 상태(visible, enabled)를 기준으로 기대 결과를 작성한다.",
            "네트워크 단절/복구와 앱 강제 종료 후 재실행 시 데이터 유지 여부를 Negative/Recovery 시나리오에 포함한다.",
        ],
        "analysis_rules": [
            "Logcat/Xcode Console 로그, 크래시 리포트, 스크린샷의 시각을 기준으로 관찰 사실과 추론을 구분한다.",
            "OS 버전과 단말 모델이 로그에서 확인되지 않으면 재현 조건 부족으로 gaps에 기록한다.",
            "ANR, Crash, 메모리 경고 등 이상 이벤트는 발생 시각과 직전 사용자 조작을 함께 정리한다.",
        ],
        "review_rules": [
            "OS/단말/네트워크 조건이 누락된 TC는 재현 불가 TC로 지적한다.",
            "'정상 표시', '잘 동작' 같은 모호한 기대 결과를 화면 요소 상태와 수치(ms, MB)로 보정한다.",
            "권한, 백그라운드, 오프라인 경계 조건 누락 여부를 점검한다.",
        ],
    },
    "embedded_fw": {
        "role": "Embedded Firmware / Hardware Interface Quality Assurance Specialist",
        "generation_rules": [
            "대상 보드, 펌웨어 버전, 전원 전압, 클럭, 측정 장비(오실로스코프, 로직 애널라이저)를 Precondition에 명시한다.",
            "입력 신호(GPIO, 버스 데이터)와 출력 관찰(레지스터 값, 핀 레벨, 버스 응답)을 별도 Step으로 분리한다.",
            "타이밍 요구는 측정 지점, 기준 에지(Rising/Falling), 허용 오차(us/ms)를 함께 기술한다.",
            "전원 Cycle, Watchdog, Reset 이후 초기값 복귀 시나리오를 Recovery로 포함한다.",
        ],
        "analysis_rules": [
            "시리얼 로그, 레지스터 덤프, 파형 캡처의 타임스탬프를 기준으로 관찰 사실과 추론을 구분한다.",
            "측정 장비 설정(샘플링 레이트, 트리거 조건)이 확인되지 않으면 gaps에 기록한다.",
            "Reset 원인 레지스터, 폴트 로그, 스택 덤프가 있으면 직접 증거로 우선 사용한다.",
        ],
        "review_rules": [
            "측정 지점, 장비, 허용 오차가 없는 타이밍 기대 결과는 측정 불가 TC로 지적한다.",
            "전원/클럭/온도 경계 조건과 Reset 후 복구 시나리오 누락을 점검한다.",
            "레지스터 값은 Hex와 비트 필드 의미를 함께 기술하도록 보정한다.",
        ],
    },
    "db_backend": {
        "role": "Database / Backend Data Processing Quality Assurance Specialist",
        "generation_rules": [
            "초기 데이터 상태(테이블별 row 수, 기준 키 값)와 DB/서비스 버전을 Precondition에 명시한다.",
            "입력 데이터, 처리 후 DB 상태(SELECT 결과의 row 수와 컬럼 값), 처리 로그를 각각 별도 Step으로 분리한다.",
            "트랜잭션 커밋/롤백, 중복 요청(멱등성), 부분 실패 시 데이터 정합성을 Negative 시나리오에 포함한다.",
            "건수와 합계 같은 정합성 기준은 소스 대비 타깃 비교식(==)으로 기술한다.",
        ],
        "analysis_rules": [
            "쿼리 로그, 실행 계획, 애플리케이션 로그의 타임스탬프를 기준으로 관찰 사실과 추론을 구분한다.",
            "처리 전/후 row 수 비교 증거가 없으면 정합성 판정은 INCONCLUSIVE로 처리하고 gaps에 기록한다.",
            "Deadlock, Lock Timeout, 롤백 로그는 발생 시각과 대상 테이블을 함께 정리한다.",
        ],
        "review_rules": [
            "초기 데이터 상태가 없는 TC는 재현 불가 TC로 지적한다.",
            "'정상 저장', '데이터 일치' 같은 모호한 기대 결과를 row 수와 컬럼 값 비교식으로 보정한다.",
            "NULL, 중복 키, 롤백, 동시성 경계 조건 누락을 점검한다.",
        ],
    },
    "network_protocol": {
        "role": "Network / Communication Protocol Quality Assurance Specialist",
        "generation_rules": [
            "프로토콜 버전, 포트, 단말/서버 역할, 네트워크 조건(대역폭, 지연, 손실률)을 Precondition에 명시한다.",
            "송신 메시지(필드 값 Hex)와 수신 응답(메시지 타입, 상태 코드)을 별도 Step으로 분리하고 패킷 캡처 확인 지점을 명시한다.",
            "타임아웃, 재전송, 연결 재수립 동작은 횟수와 시간(ms/s) 기준으로 기술한다.",
            "잘못된 필드 값, 길이 초과, 순서 오류 패킷에 대한 Negative 시나리오를 포함한다.",
        ],
        "analysis_rules": [
            "패킷 캡처(pcap)와 프로토콜 로그의 타임스탬프를 기준으로 요청-응답 지연을 계산하고 관찰 사실과 추론을 구분한다.",
            "캡처 구간과 필터 조건이 확인되지 않으면 패킷 누락 가능성을 gaps에 기록한다.",
            "재전송, 연결 리셋(RST), 타임아웃 이벤트는 발생 시각과 시퀀스 번호를 함께 정리한다.",
        ],
        "review_rules": [
            "프로토콜 버전/포트/네트워크 조건이 없는 TC는 재현 불가 TC로 지적한다.",
            "'정상 통신', '응답 수신' 같은 모호한 기대 결과를 메시지 타입, 필드 값, 지연시간(ms)으로 보정한다.",
            "타임아웃, 재전송, 재연결, Malformed Packet 경계 조건 누락을 점검한다.",
        ],
    },
}

SEQUENCE_MODE_RULES = {
    "AI 자동 생성": "- 요구사항을 분석해 Step 순서를 직접 구성하고, steps와 expected_results를 1:1로 대응시킨다.",
    "사용자 흐름 우선": "- 사용자가 지정한 핵심 흐름과 순서를 유지하며 상세 Step으로 확장하고, steps와 expected_results를 1:1로 대응시킨다.",
    "사용자 순서 고정": "- 사용자 지정 순서와 항목 수를 변경하지 않고, steps와 expected_results를 1:1로 대응시킨다.",
}

# 프로필에 "key" 가 없을 때 이름으로 도메인을 추정한다. 위에서부터 먼저 맞는 항목이 선택된다.
_DOMAIN_NAME_PATTERNS = [
    ("automotive", re.compile(r"\b(?:automotive|vehicle|ecu|bcm|can|lin|uds|autosar)\b|자동차|차량|전장", re.I)),
    ("mobile_app", re.compile(r"\b(?:mobile|android|ios)\b|모바일|안드로이드", re.I)),
    ("db_backend", re.compile(r"\b(?:db|database|sql|etl|batch)\b|데이터베이스|데이터\s*처리|배치", re.I)),
    ("network_protocol", re.compile(r"\b(?:network|protocol|tcp|udp|mqtt|modbus|ble|bluetooth)\b|네트워크|프로토콜|통신", re.I)),
    ("embedded_fw", re.compile(r"\b(?:embedded|firmware|mcu|rtos|hw|hardware)\b|펌웨어|임베디드|하드웨어", re.I)),
    ("web_api", re.compile(r"\b(?:web|api|rest|http)\b|웹", re.I)),
]
# Mode-aware prompt budgets. The legacy constant remains as the absolute cap
# for compatibility with modules that still import MAX_PROMPT_CHARS.
PROMPT_BUDGETS = {
    "TC Generation": 18000,
    "TC Review": 26000,
    "Validation Analysis": 36000,
}
BLF_EXTRA_PROMPT_CHARS = 10000
MAX_PROMPT_CHARS = 48000


# ==============================================================================
# 2. TcEngineMixin 구현부 (100% 비즈니스 로직 및 인터페이스 호환)
# ==============================================================================
