# AgentBus Protocol — Conformance Test Suite v0.1

## 이게 뭔가

**AgentBus**는 이기종 프로그램과 AI 에이전트 간의 대칭적 메시지 교환을 위한 경량 프로토콜이다.

이 저장소는 AgentBus 프로토콜의 **Conformance Test Suite** — 즉 어떤 언어의 SDK든 이 테스트를 통과하면 호환이 보장되는 검증 데이터 세트이다.

```
┌──────────────────────────────────────────┐
│  AgentBus Protocol Spec v0.1 (문서)       │
└────────────────┬─────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │  Conformance Test Suite  │  ◀── 이 저장소
    │  (언어 무관 JSON 데이터)   │
    └────────────┬────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
  C++ SDK    Python SDK    C# SDK
```

**레퍼런스는 특정 SDK가 아니라 이 테스트 데이터이다.** 각 언어 SDK는 스펙 문서와 이 데이터만 보고 독립 구현하며, 전 케이스 통과가 호환의 증명이다.

---

## 왜 필요한가

AgentBus의 핵심 목표는 **어떤 프로젝트에든 라이브러리로 넣을 수 있는 것**이다.

- C++ 게임 엔진에 헤더 몇 개로 임베드
- Python AI 오케스트레이터에 pip install
- C# Unity 클라이언트에 DLL 하나로 추가
- 그 외 어떤 언어든

이 모든 SDK가 **같은 메시지를 같은 방식으로 읽고 쓸 수 있어야** 한다. Conformance Suite가 그 기준이다.

---

## 디렉터리 구조

```
tests/conformance/
├── manifest.json                  # 전체 테스트 케이스 목록
├── CANONICAL_KEY_ORDER.md         # 직렬화 키 순서 정규화 규칙
│
├── parse/
│   ├── valid/                     # 유효 메시지 파싱 테스트
│   │   ├── call_basic.input.json
│   │   ├── call_basic.expected.json
│   │   ├── call_with_timeout.input.json
│   │   ├── call_with_timeout.expected.json
│   │   └── ...
│   │
│   └── invalid/                   # 무효 메시지 거부 테스트
│       ├── missing_id.input.json
│       ├── missing_id.expected.json
│       ├── bad_timestamp_no_ms.input.json
│       ├── bad_timestamp_no_ms.expected.json
│       └── ...
│
├── serialize/                     # 직렬화 정확성 테스트
│   ├── call_basic.fields.json
│   ├── call_basic.expected.jsonl
│   └── ...
│
└── scenarios/                     # 시나리오 테스트 (Phase 2)
    └── basic_roundtrip.scenario.json
```

---

## 테스트 카테고리

### parse/valid — 유효 메시지 파싱 (10개)

입력 메시지를 파싱하여 `expected.json`의 `parsed` 객체와 **의미적으로 동일**한지 검증한다.

| 케이스 | 검증 내용 |
|--------|----------|
| `call_basic` | 기본 call 메시지 |
| `call_with_timeout` | timeout_ms 포함 call |
| `call_empty_params` | 빈 params 객체 |
| `response_basic` | 기본 response (result가 객체) |
| `response_scalar_result` | result가 정수 (42) |
| `response_null_result` | result가 null |
| `error_basic` | 기본 error (data 없음) |
| `error_with_data` | error.data 포함 |
| `event_basic` | 기본 event |
| `extra_top_level_field` | 미정의 최상위 필드 → permissive 모드에서 유효 |

### parse/invalid — 무효 메시지 거부 (21개)

입력 메시지가 **거부되어야** 하며, `expected.json`의 에러 정보와 일치하는지 검증한다.

| 카테고리 | 케이스 수 | 검증 내용 |
|---------|----------|----------|
| 필수 필드 누락 | 8 | id, session, from, to, type, timestamp, meta, meta.schema |
| 타임스탬프 무효 | 2 | 밀리초 누락, 타임존 오프셋 |
| type 값 무효 | 1 | 허용값 외 (`request`) |
| 조건부 필드 누락 | 4 | reply_to, error.code, error.retryable, method, params |
| params 타입 위반 | 2 | 문자열, 배열 |
| 이름 규칙 위반 | 3 | 대문자 peer, 숫자 시작 peer, 하이픈 method |

### serialize — 직렬화 정확성 (7개)

필드값을 입력받아 직렬화한 결과가 `expected.jsonl`과 **문자열 완전 일치**하는지 검증한다.

| 케이스 | 검증 내용 |
|--------|----------|
| `call_basic` | call 정규 직렬화 |
| `call_with_timeout` | timeout_ms 포함 키 순서 |
| `response_basic` | response 정규 직렬화 |
| `response_scalar_result` | result가 스칼라일 때 |
| `error_basic` | error 정규 직렬화 |
| `error_with_data` | error.data 포함 키 순서 |
| `event_basic` | event 정규 직렬화 |

### scenarios — 시나리오 테스트 (Phase 2, 1개 예시)

Peer 상태 머신의 전이를 검증한다. 현재는 형식 정의용 예시 1건만 포함.

---

## 파일 형식

### parse/valid

```
*.input.json     한 줄 또는 여러 줄 JSON. 파싱 대상 메시지.
*.expected.json   {"valid": true, "parsed": { ... }}
                  parsed는 SDK 내부 모델을 정규화한 JSON 객체.
```

### parse/invalid

```
*.input.json     파싱 대상 메시지 (무효).
*.expected.json   {"valid": false, "error_code": "...", "error_field": "...", "error_detail": "..."}
```

| 필드 | 설명 |
|------|------|
| `valid` | 항상 `false` |
| `error_code` | 표준 에러 코드 (예: `MALFORMED_MESSAGE`) |
| `error_field` | 문제가 된 필드 경로 (예: `timestamp`, `error.code`, `meta.schema`) |
| `error_detail` | 사람이 읽을 수 있는 설명 |

### serialize

```
*.fields.json     정규 키 순서로 된 입력 필드값 (한 줄 compact JSON).
*.expected.jsonl  정규 직렬화 결과 (한 줄 compact JSON + LF).
```

serialize suite는 **문자열 완전 일치 비교**이다. 의미적 동등이 아니라 바이트 단위로 같아야 한다.

### scenarios

```
*.scenario.json   시나리오 정의 (steps + expected state).
```

---

## 비교 규칙

| suite | 비교 방법 | 이유 |
|-------|----------|------|
| parse/valid | **의미적 비교** (키 순서 무관, 값 동등) | 파싱 결과는 내부 모델이므로 순서 무관 |
| parse/invalid | **error_code + error_field 일치** | error_detail은 참고용 (완전 일치 불필요) |
| serialize | **문자열 완전 일치** | cross-language 직렬화 호환 보장 |

---

## 정규 키 순서 (Canonical Key Order)

serialize suite의 문자열 완전 일치를 위해 직렬화 시 키 순서가 고정되어 있다.

**공통 envelope:**

```
id → session → from → to → type → timestamp → meta
```

**type별 추가:**

```
call/event:  → method → params → timeout_ms (선택)
response:    → reply_to → result
error:       → reply_to → error
```

**중첩 객체:**

```
meta:   schema → (나머지 사전순)
error:  code → message → retryable → data (선택)
```

상세 규칙은 `CANONICAL_KEY_ORDER.md` 참조.

---

## SDK 구현자를 위한 가이드

### 1단계: manifest 읽기

```python
import json
manifest = json.load(open("tests/conformance/manifest.json"))
```

### 2단계: parse/valid 러너 작성

```python
for case_path in manifest["suites"]["parse_valid"]:
    input_msg = read(f"{case_path}.input.json")
    expected = json.load(open(f"{case_path}.expected.json"))

    parsed = your_sdk.parse(input_msg)      # SDK의 파싱 함수
    assert parsed.to_dict() == expected["parsed"]
```

```cpp
for (auto& path : manifest["suites"]["parse_valid"]) {
    auto input = read_file(path + ".input.json");
    auto expected = json::parse(read_file(path + ".expected.json"));

    auto parsed = agentbus::parse(input);
    assert(parsed.to_json() == expected["parsed"]);
}
```

```csharp
foreach (var path in manifest["suites"]["parse_valid"]) {
    var input = File.ReadAllText($"{path}.input.json");
    var expected = JsonDocument.Parse(File.ReadAllText($"{path}.expected.json"));

    var parsed = AgentBus.Message.Parse(input);
    Assert.Equal(expected["parsed"], parsed.ToJson());
}
```

### 3단계: parse/invalid 러너 작성

```python
for case_path in manifest["suites"]["parse_invalid"]:
    input_msg = read(f"{case_path}.input.json")
    expected = json.load(open(f"{case_path}.expected.json"))

    try:
        your_sdk.parse(input_msg)
        assert False, "should have been rejected"
    except ValidationError as e:
        assert e.error_code == expected["error_code"]
        assert e.error_field == expected["error_field"]
```

### 4단계: serialize 러너 작성

```python
for case_path in manifest["suites"]["serialize"]:
    fields = json.load(open(f"{case_path}.fields.json"))
    expected_line = read(f"{case_path}.expected.jsonl")

    msg = your_sdk.Message.from_dict(fields)
    serialized = msg.serialize()               # compact JSON + LF
    assert serialized == expected_line          # 문자열 완전 일치
```

### 5단계: 모든 케이스 통과 확인

```
parse/valid:   10/10 passed
parse/invalid: 21/21 passed
serialize:      7/7  passed
---
CONFORMANCE: PASSED
```

이 결과가 나오면 해당 SDK는 AgentBus v0.1 호환이다.

---

## 관련 문서

| 문서 | 설명 |
|------|------|
| `agentbus-protocol-spec-v0.1.md` | 영문 프로토콜 명세 (정식본) |
| `agentbus-protocol-spec-v0.1-ko.md` | 한국어 프로토콜 명세 (정식본) |
| `agentbus-protocol-spec-v0.1-ko-compact.md` | 한국어 간소화 명세 (퀵레퍼런스) |
| `CANONICAL_KEY_ORDER.md` | 직렬화 키 순서 정규화 규칙 |

---

## 로드맵

```
Phase 1 ✅  프로토콜 스펙 v0.1 확정
Phase 2 ✅  Conformance Test Suite (parse/serialize) ◀ 현재
Phase 3     각 언어 SDK Message Layer 구현 + conformance 통과
Phase 4     Peer + FileTransport 구현 (3개 언어)
Phase 5     Cross-language 왕복 테스트
Phase 6     실전 프로젝트 임베드 + Extension 설계
```

---

## 현재 상태 (v0.1)

**포함됨:**

- 메시지 파싱/검증/직렬화 conformance (38개 케이스)
- 정규 키 순서 규칙
- 시나리오 형식 정의 (1개 예시)

**아직 포함되지 않음 (향후 Extension):**

- State Sync (snapshot/patch/version)
- Command Execution (batch/atomic/precondition)
- Binary Transport Profile (MessagePack/FlatBuffers)
- Capability Negotiation

이들은 Core 프로토콜 위에 확장으로 추가될 예정이다.

---

## 라이선스

TBD
