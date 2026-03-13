# ZEP Core v0.1

**Zero Echo Pipe — 프로그램 간 경량 통신 프로토콜**

**스키마:** `zep.v0.1`

---

## 1. 목적

C++, Python, C#가 동일한 메시지를 읽고 쓰며, call-response 왕복을 동일하게 처리하는 최소 프로토콜. 파일(JSONL)과 소켓(Frame) 두 가지 wire format을 지원한다.

## 2. 메시지

### 2.0 Wire Format

프로토콜 의미론(§2.1~§3)은 직렬화 형식에 무관하다. v0.1은 두 가지 wire format을 정의한다.

| Profile | 용도 | 메시지 경계 |
|---------|------|-----------|
| JSONL | 파일 transport, 디버깅 | LF 구분 |
| Frame | 소켓 transport | 4바이트 길이 접두사 |

**JSONL Profile:** UTF-8. BOM 금지. LF 종료. CR 금지. compact JSON. 1 메시지 = 1 JSON + 1 LF.

**Frame Profile:** UTF-8. 1 메시지 = [4바이트 big-endian 길이][JSON 바이트열]. LF 불필요.

양쪽 모두 권장 최대 페이로드 1MB.

### 2.1 Envelope

| 필드 | 필수 | 타입 | 규칙 |
|------|------|------|------|
| `id` | 모든 | string | pending 집합 내 unique. 전역 unique 권장 |
| `session` | 모든 | string | peer pair 간 논리적 대화 컨텍스트. transport 연결과 무관 |
| `from` | 모든 | string | `[a-z][a-z0-9_-]{0,63}` |
| `to` | 모든 | string | 동일 |
| `type` | 모든 | string | `call` / `response` / `error` / `event` |
| `timestamp` | 모든 | string | `YYYY-MM-DDTHH:MM:SS.sssZ` UTC 고정. 정보성 필드 — 순서 판정용 아님 |
| `meta` | 모든 | object | 필수. 최소 `schema` 포함 |
| `meta.schema` | 모든 | string | `"zep.v0.1"` |
| `method` | call, event | string | `[a-z_][a-z0-9_.]{0,127}`. `_` 시작은 프로토콜 예약 |
| `params` | call, event | object | JSON 객체만 |
| `reply_to` | response, error | string | 원본 call의 `id` |
| `result` | response | any | 임의 JSON 값 |
| `error` | error | object | `code`(string) + `message`(string) + `retryable`(bool) 필수. `data` 선택 |
| `timeout_ms` | call 선택 | integer | 송신자 로컬 대기 힌트. 수신자 강제 의무 없음 |

미정의 최상위 필드는 무시할 수 있다 (MAY).

### 2.2 예시

**call:**
```json
{"id":"m1","session":"s1","from":"agent","to":"engine","type":"call","timestamp":"2026-03-11T12:00:00.123Z","meta":{"schema":"zep.v0.1"},"method":"get_status","params":{"verbose":true}}
```

**response:**
```json
{"id":"m2","session":"s1","from":"engine","to":"agent","type":"response","timestamp":"2026-03-11T12:00:00.200Z","meta":{"schema":"zep.v0.1"},"reply_to":"m1","result":{"health":100}}
```

**error:**
```json
{"id":"m3","session":"s1","from":"engine","to":"agent","type":"error","timestamp":"2026-03-11T12:00:00.200Z","meta":{"schema":"zep.v0.1"},"reply_to":"m1","error":{"code":"METHOD_NOT_FOUND","message":"Unknown method","retryable":false}}
```

**event:**
```json
{"id":"m4","session":"s1","from":"engine","to":"agent","type":"event","timestamp":"2026-03-11T12:00:01.000Z","meta":{"schema":"zep.v0.1"},"method":"status.changed","params":{"health":80}}
```

## 3. 상태 머신

### 3.1 송신자 (call 기준)

```
pending → completed   (response 수신)
pending → failed      (error 수신)
pending → timeout     (timeout_ms 초과)
```

### 3.2 수신자

1. JSON 파싱 실패 → 폐기 + 로그.
2. `id`, `from`, `to`, `session`, `type` 파싱 성공 → reply route 있음 → 나머지 검증 실패 시 `MALFORMED_MESSAGE` error 회신.
3. reply route 구성 불가 → 폐기. error 회신 금지.
4. 정상 → 핸들러 실행 → response 또는 error.

`MALFORMED_MESSAGE` error는 reply route(`id`, `from`, `to`, `session`, `type`)를 식별할 수 있을 때만 회신 가능하다.

### 3.3 라우팅 대칭

response/error는 원본 call과: `to` = call.`from`, `from` = call.`to`, `session` = call.`session` (MUST).

### 3.4 Response 수신 검증

| 항목 | 불일치 시 |
|------|----------|
| reply_to가 pending에 없음 | ignore |
| from/to 역전 불일치 | ignore |
| session 불일치 | ignore |
| 동일 reply_to 중복 | 첫 번째만 채택 |

## 4. Transport

### 4.1 계약

1. 메시지 경계 보존.
2. 완전히 쓴 메시지만 노출.
3. 동일 route FIFO. 전역 순서 미보장.
4. 새 메시지 감지 (watch 또는 polling).
5. Peer 존재는 transport가 정의. 부재 시 에러.
6. exactly-once 미보장.

### 4.2 File Transport (참조 구현, JSONL Profile)

sender-split inbox. append-only JSONL. writer 1명/파일. 잠금 불필요.

```
<base_dir>/peers/<peer>/from_<sender>.jsonl
```

읽기 위치 추적은 구현 정의 (byte offset, line number, message id 등).

base path는 설정값. 하드코딩 금지.

### 4.3 Socket Transport (고속, Frame Profile)

Unix Domain Socket. length-prefix framing (4바이트 big-endian + JSON).

```
<base_dir>/zep.sock
```

동일 머신 전용. 지연 ~20μs. v0.1에서는 구현 선택 사항 (MAY).

## 5. 에러 코드

| 코드 | 설명 | 재시도 |
|------|------|--------|
| `METHOD_NOT_FOUND` | 메서드 없음 | false |
| `INVALID_PARAMS` | 파라미터 무효 | false |
| `TIMEOUT` | 시간 초과 | true |
| `INTERNAL_ERROR` | 내부 예외 | true |
| `MALFORMED_MESSAGE` | 명세 위반 | false |
| `SESSION_MISMATCH` | 세션 불일치 | false |
| `UNSUPPORTED_SCHEMA` | 미지원 스키마 | false |
| `PEER_NOT_FOUND` | peer 부재. transport가 로컬 예외로 처리할 수도, protocol error로 surface할 수도 있다 | false |

## 6. 예약 메서드

`_` 시작 메서드는 프로토콜 예약. 애플리케이션 사용 금지.

v0.1 정의: `_capabilities` — peer capability 정보 반환 (MAY).

v0.1 예약만 (미정의): `_ping`, `_shutdown`.

## 7. 직렬화 정규 키 순서

conformance serialize 테스트 및 JSONL profile에서 문자열 완전 일치용. Frame profile에서도 동일 키 순서를 권장 (SHOULD).

공통: `id, session, from, to, type, timestamp, meta`

| type | 추가 |
|------|------|
| call | `method, params, timeout_ms` |
| response | `reply_to, result` |
| error | `reply_to, error` |
| event | `method, params` |

error 내부: `code, message, retryable, data`. meta 내부: `schema` 먼저.

## 8. 적합성

유효 메시지는 파싱 성공 (MUST). 무효 메시지는 거부 (MUST). Python valid = C++ valid = C# valid (MUST).

테스트 구조:
```
tests/conformance/
  manifest.json
  parse/valid/
  parse/invalid/
  serialize/
  scenarios/
```

v0.1 필수 시나리오: `basic_roundtrip`, `unknown_method`, `timeout`, `session_mismatch`.

---

## 9. 로드맵

**원칙: 문서 → 테스트 데이터 → 최소 구현 → 교차 언어 검증 → 실사용 → 확장.**

| Phase | 목표 | 완료 기준 |
|-------|------|----------|
| 0 | Core 문서 고정 | 기능 추가 없음. conformance 작성 기준 확보 |
| 1 | Conformance Suite | manifest + parse valid/invalid + serialize + scenario 4개 |
| 2 | Message Layer 3언어 | C++/Python/C# 모두 conformance 통과 |
| 3 | Peer + Transport | send, poll_once, bind, call, emit. 교차 언어 읽기/쓰기 |
| 4 | Cross-language Roundtrip | Python↔C++↔C# 왕복. 4개 시나리오 실행 검증 |
| 5 | 첫 실사용 임베드 | Stella Engine에 삽입. method 1~2개 연결. 부족한 점 발견 |
| 6 | v0.2 판단 | 실사용 결과로 확장 필요 여부 결정 |

확장 후보 (Phase 6 이후): Commander, StateReporter, Buffer, Unix Domain Socket transport, 독자 AI Agent 프로그램, MCP Admin Server.
