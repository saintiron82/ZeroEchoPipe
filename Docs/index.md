---
title: ZEP — Zero Echo Pipe
---

# ZEP — Zero Echo Pipe

**프로그램 간 경량 통신 프로토콜** | Schema `zep.v0.1`

## 설치

```bash
pip install zep-protocol
```

## 핵심 개념

ZEP는 이기종 프로그램(C++, Python, C#)이 동일한 메시지 형식으로 통신하는 최소 프로토콜입니다.

### 메시지 흐름

```
Agent                    Engine
  │                        │
  │──── call (method) ────▶│
  │                        │── handler 실행
  │◀── response (result) ──│
  │                        │
  │──── event (fire) ─────▶│  (응답 없음)
  │                        │
```

### 4가지 메시지 타입

- **call** — 원격 메서드 호출. 응답 필수.
- **response** — call 성공 응답.
- **error** — call 실패 응답. code + message + retryable.
- **event** — 단방향 알림. 응답 없음.

## 빠른 시작

### 에이전트 정의

```python
from zep import BaseAgent, method, on_event, FileTransport

class GameEngine(BaseAgent):
    @method("get_status")
    def status(self, params):
        return {"health": 100, "fps": 60}

    @method("execute")
    def execute(self, params):
        return {"result": f"Executed: {params['command']}"}

    @on_event("log")
    def on_log(self, params):
        print(f"[LOG] {params['message']}")
```

### 서버 실행

```python
transport = FileTransport("/tmp/zep-bus")
engine = GameEngine("engine", transport, session="game01")
engine.run()  # 블로킹
```

### 클라이언트 호출

```python
transport = FileTransport("/tmp/zep-bus")
client = BaseAgent("ai_agent", transport, session="game01")
client.run(blocking=False)

status = client.call("engine", "get_status", {})
# {"health": 100, "fps": 60}

client.emit("engine", "log", {"message": "AI initialized"})
```

## Transport

### FileTransport (JSONL)

파일 기반. 디버깅에 유리. append-only JSONL.

```python
from zep import FileTransport
transport = FileTransport("/path/to/bus")
```

### SocketTransport (Frame)

Unix Domain Socket. 저지연 (~20us).

```python
from zep import SocketTransport

# 서버
server = SocketTransport("/tmp/zep.sock", is_server=True)

# 클라이언트
client = SocketTransport("/tmp/zep.sock", is_server=False)
```

## 예약 메서드

`_` 로 시작하는 메서드는 프로토콜 예약입니다.

| 메서드 | 설명 | 응답 |
|--------|------|------|
| `_capabilities` | peer 정보 조회 | name, schema, methods |
| `_ping` | 헬스체크 | pong, timestamp |
| `_shutdown` | 종료 요청 | acknowledged |

```python
caps = client.call("engine", "_capabilities", {})
# {"name": "engine", "schema": "zep.v0.1", "methods": ["get_status", "execute"]}
```

## 에러 코드

| 코드 | 설명 | 재시도 |
|------|------|--------|
| METHOD_NOT_FOUND | 메서드 없음 | No |
| INVALID_PARAMS | 파라미터 무효 | No |
| TIMEOUT | 시간 초과 | Yes |
| INTERNAL_ERROR | 내부 예외 | Yes |
| MALFORMED_MESSAGE | 명세 위반 | No |

## 적합성 테스트

모든 SDK는 `conformance/` 디렉터리의 언어 무관 테스트를 통과해야 합니다.

- parse/valid: 10개
- parse/invalid: 21개
- serialize: 7개
- scenarios: 4개

```bash
cd zep-py && python -m tests
# Ran 30 tests in 0.735s — OK
```

## 링크

- [프로토콜 명세 (zep-core-v0.1)](zep-core-v0.1.md)
- [GitHub Repository](https://github.com/saintiron/ZeroEchoPipe)
