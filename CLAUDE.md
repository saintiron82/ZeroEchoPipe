# ZeroEchoPipe (ZEP) — CLAUDE.md

## 프로젝트 개요

**Zero Echo Pipe** — 프로그램 간 경량 통신 프로토콜 (`zep.v0.1`).
C++, Python, C#가 동일한 메시지를 읽고 쓰며, call-response 왕복을 동일하게 처리하는 최소 프로토콜.

## 배포 정보

| 항목 | 값 |
|------|---|
| PyPI 패키지명 | `zep-protocol` |
| 설치 명령 | `pip install zep-protocol` |
| PyPI 계정 | `zeroechosoft` |
| PyPI URL | https://pypi.org/project/zep-protocol/ |
| GitHub | https://github.com/saintiron82/ZeroEchoPipe |
| GitHub Pages | https://saintiron82.github.io/ZeroEchoPipe/ |
| GitHub 계정 | `saintiron82` |
| 현재 버전 | `0.1.0` |

### 배포 방법

PyPI Trusted Publisher가 설정됨 (GitHub Actions 연동). 수동 배포:

```bash
cd zep-py
source .venv/bin/activate
pip install build twine
python -m build                    # dist/ 에 .whl + .tar.gz 생성
twine upload dist/*                # PyPI 업로드 (API 토큰 필요)
```

### 버전 올릴 때

1. `zep-py/pyproject.toml`의 `version` 수정
2. `zep-py/zep/__init__.py`의 `__version__` 수정
3. `python -m build` → `twine upload dist/*`
4. git tag: `git tag v0.x.x && git push --tags`

## 핵심 명세 (zep-core-v0.1)

- **스키마**: `zep.v0.1`
- **Wire Format 2종**: JSONL (파일, LF 구분) / Frame (소켓, 4바이트 길이 접두사)
- **메시지 타입 4종**: `call`, `response`, `error`, `event`

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
├── CLAUDE.md                        # 이 파일
├── README.md                        # PyPI/GitHub 표시용
├── .gitignore
├── Docs/
│   ├── zep-core-v0.1.md             # 프로토콜 명세
│   ├── index.md                     # GitHub Pages 메인
│   └── _config.yml                  # Jekyll 설정
├── conformance/                     # 언어 무관 Conformance Test Suite
│   ├── manifest.json                # 테스트 케이스 목록 (38개)
│   ├── CANONICAL_KEY_ORDER.md       # 직렬화 키 순서 규칙
│   ├── README.md                    # conformance 설명서
│   ├── parse/valid/                 # 유효 메시지 파싱 (10개)
│   ├── parse/invalid/               # 무효 메시지 거부 (21개)
│   ├── serialize/                   # 직렬화 정확성 (7개)
│   └── scenarios/                   # 시나리오 테스트 (4개)
│       ├── basic_roundtrip.scenario.json
│       ├── unknown_method.scenario.json
│       ├── timeout.scenario.json
│       └── session_mismatch.scenario.json
└── zep-py/                          # Python SDK
    ├── pyproject.toml               # 패키지 설정 (name: zep-protocol)
    ├── .venv/                       # 가상환경 (gitignored)
    ├── zep/
    │   ├── __init__.py              # public API re-export
    │   ├── message.py               # parse, validate, serialize, make_timestamp
    │   ├── peer.py                  # Peer (bind, call, emit, poll_once, reserved methods)
    │   ├── agent.py                 # BaseAgent + @method + @on_event 데코레이터
    │   └── transport/
    │       ├── __init__.py          # FileTransport, SocketTransport export
    │       ├── base.py              # BaseTransport ABC (send, recv, close)
    │       ├── file.py              # FileTransport (sender-split inbox, JSONL)
    │       └── socket.py            # SocketTransport (UDS, Frame Profile)
    └── tests/
        ├── __init__.py              # 패키지화
        ├── __main__.py              # 단일 진입점: python -m tests
        ├── run_conformance.py       # 레거시 conformance runner
        ├── test_conformance.py      # conformance unittest (38 subTests)
        ├── test_roundtrip.py        # peer 왕복 테스트 (6개)
        ├── test_scenario.py         # 시나리오 인터프리터 (4개)
        ├── test_socket_transport.py # 소켓 + frame 코덱 테스트 (8개)
        ├── test_peer_advanced.py    # 예약 메서드/라우팅 테스트 (6개)
        └── test_agent.py            # 에이전트 프레임워크 테스트 (6개)
```

## 현재 구현 상태

### 완료

- [x] 프로토콜 명세 v0.1 확정
- [x] Conformance Test Suite (parse 10 valid + 21 invalid + 7 serialize + 4 scenarios)
- [x] Python SDK Message Layer (parse/validate/serialize)
- [x] Python SDK Peer (bind/call/emit/poll_once + 예약 메서드 + 라우팅 검증)
- [x] Python SDK FileTransport (sender-split inbox, JSONL)
- [x] Python SDK SocketTransport (Unix Domain Socket, Frame Profile)
- [x] Python SDK BaseAgent (@method/@on_event 데코레이터, 양방향 통신)
- [x] 테스트 베드 (30개 unittest, 단일 진입점)
- [x] 패키징 (pyproject.toml, pip install zep-protocol)
- [x] PyPI 배포 (v0.1.0)
- [x] GitHub 저장소 + Pages 문서 사이트

### 미완료

- [ ] C++ SDK
- [ ] C# SDK
- [ ] Cross-language Roundtrip (Phase 4)
- [ ] 실사용 임베드 (Phase 5 — Stella Engine)
- [ ] GitHub Actions CI/CD (publish.yml 자동 배포)

## 로드맵

| Phase | 목표 | 상태 |
|-------|------|------|
| 0 | Core 문서 고정 | 완료 |
| 1 | Conformance Suite | 완료 (42개) |
| 2 | Message Layer 3언어 | Python 완료, C++/C# 미착수 |
| 3 | Peer + Transport + Agent | Python 완료, C++/C# 미착수 |
| 4 | Cross-language Roundtrip | 미착수 |
| 5 | Stella Engine 임베드 | 미착수 |
| 6 | v0.2 판단 | 미착수 |

## 개발 규칙

### 코드 컨벤션

- Python: 표준 라이브러리만 사용 (외부 의존성 없음)
- 모든 SDK는 conformance suite를 독립적으로 통과해야 함
- Conformance test data가 레퍼런스 — 특정 SDK가 아님
- `_` 시작 메서드는 프로토콜 예약. 애플리케이션 bind 금지

### 프로토콜 준수

- 미정의 최상위 필드는 무시 가능 (MAY) — permissive 파싱
- 직렬화는 정규 키 순서 엄수 (문자열 완전 일치 테스트)
- JSONL: UTF-8, BOM 금지, LF 종료, CR 금지, compact JSON
- Frame: 4바이트 big-endian 길이 + JSON 바이트열
- 최대 페이로드 권장 1MB

### Transport 규칙

**FileTransport (JSONL Profile)**
- 경로: `<base_dir>/peers/<peer>/from_<sender>.jsonl`
- append-only, writer 1명/파일
- base path는 설정값 (하드코딩 금지)
- 읽기 위치 추적은 구현 정의 (byte offset)
- macOS/Linux 전용 (fcntl 사용)

**SocketTransport (Frame Profile)**
- 경로: `<base_dir>/zep.sock` (Unix Domain Socket)
- 서버 1개 + 클라이언트 N개
- frame_encode/frame_decode로 메시지 경계 보존
- 동일 머신 전용, 지연 ~20us

### 예약 메서드 (구현 완료)

| 메서드 | 설명 | 응답 |
|--------|------|------|
| `_capabilities` | peer 정보 반환 | name, schema, methods, custom caps |
| `_ping` | 헬스체크 | pong, timestamp |
| `_shutdown` | graceful 종료 요청 | acknowledged |

### 라우팅 대칭 (§3.3)

response/error는 원본 call의 to↔from 역전, session 동일 (MUST).
Peer._verify_routing()에서 3가지 검증 (from, to, session).

### 테스트 실행

```bash
cd zep-py
source .venv/bin/activate    # 또는 python3 -m venv .venv && pip install -e .
python -m tests              # 30 tests, ~0.7초
```

개별 실행:
```bash
python -m tests.test_conformance       # conformance 38개
python -m tests.test_roundtrip         # peer 왕복 6개
python -m tests.test_scenario          # 시나리오 4개
python -m tests.test_socket_transport  # 소켓 8개
python -m tests.test_peer_advanced     # 예약 메서드 6개
python -m tests.test_agent             # 에이전트 6개
```
