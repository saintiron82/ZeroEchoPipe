# ZeroEchoPipe (ZEP) — CLAUDE.md

## 프로젝트 개요

**Zero Echo Pipe** — 프로그램 간 경량 통신 프로토콜 (`zep.v0.1`).
C++, Python, C#가 동일한 메시지를 읽고 쓰며, call-response 왕복을 동일하게 처리하는 최소 프로토콜.

## 핵심 명세 (zep-core-v0.1)

- **스키마**: `zep.v0.1`
- **Wire Format 2종**: JSONL (파일, LF 구분) / Frame (소켓, 4바이트 길이 접두사)
- **메시지 타입 4종**: `call`, `response`, `error`, `event`
- **대상 언어**: C++, Python, C#

### Envelope 필수 필드

`id`, `session`, `from`, `to`, `type`, `timestamp`, `meta` (meta.schema 필수)

### 타입별 추가 필드

| type | 필수 | 선택 |
|------|------|------|
| call | method, params | timeout_ms |
| response | reply_to, result | - |
| error | reply_to, error(code+message+retryable) | error.data |
| event | method, params | - |

### 검증 규칙

- peer name: `[a-z][a-z0-9_-]{0,63}`
- method name: `[a-z_][a-z0-9_.]{0,127}` (`_` 시작은 프로토콜 예약)
- timestamp: `YYYY-MM-DDTHH:MM:SS.sssZ` (UTC 고정)
- params: JSON 객체만 (배열/스칼라 불가)

### 직렬화 정규 키 순서 (§7)

공통: `id, session, from, to, type, timestamp, meta`
- call: `+ method, params, timeout_ms`
- response: `+ reply_to, result`
- error: `+ reply_to, error`
- event: `+ method, params`
- meta 내부: `schema` 먼저, 나머지 사전순
- error 내부: `code, message, retryable, data`

### 에러 코드

`METHOD_NOT_FOUND`, `INVALID_PARAMS`, `TIMEOUT`, `INTERNAL_ERROR`, `MALFORMED_MESSAGE`, `SESSION_MISMATCH`, `UNSUPPORTED_SCHEMA`, `PEER_NOT_FOUND`

### 수신자 상태 머신

1. JSON 파싱 실패 → 폐기 + 로그
2. reply route 필드 파싱 성공 + 나머지 검증 실패 → `MALFORMED_MESSAGE` error 회신
3. reply route 구성 불가 → 폐기 (error 회신 금지)
4. 정상 → 핸들러 실행 → response 또는 error

### Response 수신 검증 (§3.4)

reply_to가 pending에 없음 / from-to 역전 불일치 / session 불일치 / 중복 reply_to → 전부 ignore

## 디렉터리 구조

```
ZeroEchoPipe/
├── CLAUDE.md                     # 이 파일
├── Docs/
│   └── zep-core-v0.1.md          # 프로토콜 명세
├── conformance/                  # 언어 무관 Conformance Test Suite
│   ├── manifest.json             # 테스트 케이스 목록
│   ├── CANONICAL_KEY_ORDER.md    # 직렬화 키 순서 규칙
│   ├── parse/valid/              # 유효 메시지 파싱 (10개)
│   ├── parse/invalid/            # 무효 메시지 거부 (21개)
│   ├── serialize/                # 직렬화 정확성 (7개)
│   └── scenarios/                # 시나리오 테스트
└── zep-py/                       # Python SDK
    ├── zep/
    │   ├── __init__.py           # public API re-export
    │   ├── message.py            # parse, validate, serialize, make_timestamp
    │   ├── peer.py               # Peer (bind, call, emit, poll_once)
    │   └── transport/
    │       ├── base.py           # BaseTransport ABC (send, recv, close)
    │       └── file.py           # FileTransport (sender-split inbox, JSONL)
    └── tests/
        ├── run_conformance.py    # conformance suite runner
        └── test_roundtrip.py     # peer-to-peer 왕복 테스트
```

## 현재 구현 상태

### 완료 (Phase 1-3 부분)

- [x] 프로토콜 명세 v0.1 확정
- [x] Conformance Test Suite (parse valid 10, invalid 21, serialize 7)
- [x] Python SDK Message Layer (parse/validate/serialize)
- [x] Python SDK Peer (bind/call/emit/poll_once)
- [x] Python SDK FileTransport (sender-split inbox)
- [x] Python SDK Roundtrip 테스트

### 미완료

- [ ] C++ SDK
- [ ] C# SDK
- [ ] 교차 언어 conformance 통과 검증
- [ ] Cross-language Roundtrip (Phase 4)
- [ ] Socket Transport (Frame Profile, Unix Domain Socket)
- [ ] 시나리오 테스트 러너 (basic_roundtrip, unknown_method, timeout, session_mismatch)
- [ ] 실사용 임베드 (Phase 5 — Stella Engine)

## 로드맵

| Phase | 목표 | 상태 |
|-------|------|------|
| 0 | Core 문서 고정 | 완료 |
| 1 | Conformance Suite | 완료 |
| 2 | Message Layer 3언어 | Python 완료, C++/C# 미착수 |
| 3 | Peer + Transport | Python 완료, C++/C# 미착수 |
| 4 | Cross-language Roundtrip | 미착수 |
| 5 | Stella Engine 임베드 | 미착수 |
| 6 | v0.2 판단 | 미착수 |

## 개발 규칙

### 코드 컨벤션

- Python: 표준 라이브러리만 사용 (외부 의존성 없음)
- 모든 SDK는 conformance suite를 독립적으로 통과해야 함
- Conformance test data가 레퍼런스 — 특정 SDK가 아님

### 프로토콜 준수

- 미정의 최상위 필드는 무시 가능 (MAY) — permissive 파싱
- 직렬화는 정규 키 순서 엄수 (문자열 완전 일치 테스트)
- JSONL: UTF-8, BOM 금지, LF 종료, CR 금지, compact JSON
- Frame: 4바이트 big-endian 길이 + JSON 바이트열
- 최대 페이로드 권장 1MB

### File Transport 규칙

- 경로: `<base_dir>/peers/<peer>/from_<sender>.jsonl`
- append-only, writer 1명/파일
- base path는 설정값 (하드코딩 금지)
- 읽기 위치 추적은 구현 정의

### 테스트

- conformance runner: `python zep-py/tests/run_conformance.py`
- roundtrip test: `python zep-py/tests/test_roundtrip.py`
- conformance 경로: `conformance/` (프로젝트 루트 기준)
  - 주의: run_conformance.py 내부 경로가 `tests/conformance/`로 되어 있음 — 실제 경로와 불일치 가능

### 라우팅 대칭 (§3.3)

response/error는 원본 call의 to↔from 역전, session 동일 (MUST)

### 예약 메서드

`_` 시작 메서드는 프로토콜 예약. 애플리케이션 사용 금지.
- `_capabilities`: peer capability 정보 반환 (MAY)
- `_ping`, `_shutdown`: 예약만 (미정의)
