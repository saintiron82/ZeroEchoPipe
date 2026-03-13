# ZEP — Zero Echo Pipe

**프로그램 간 경량 통신 프로토콜** | Schema `zep.v0.1` | v0.3.1

서버 없음. 클라이언트 없음. 포트 없음. 경로 하나면 통신 시작.

## 설치

```bash
pip install zep-protocol
```

## 빠른 시작

### 두 프로세스가 대화하기

```python
# process_a.py — engine
from zep import BaseAgent, method, connect

class Engine(BaseAgent):
    @method("get_status")
    def handle_status(self, params):
        return {"health": 100, "level": params.get("level", 1)}

transport = connect("/tmp/zep-bus")
engine = Engine("engine", transport, session="game01")
engine.run()  # 블로킹, 메시지 대기
```

```python
# process_b.py — agent
from zep import BaseAgent, connect

transport = connect("/tmp/zep-bus")
agent = BaseAgent("agent", transport, session="game01")
agent.run(blocking=False)

result = agent.call("engine", "get_status", {"level": 5})
print(result)  # {"health": 100, "level": 5}

agent.emit("engine", "notify", {"message": "ping"})
```

양쪽 다 `connect("/tmp/zep-bus")` — 그게 전부입니다.

### 저수준 Peer 사용

```python
from zep import Peer, connect

transport = connect("/tmp/zep-bus")
peer = Peer(transport, "myapp", session="s1")
peer.bind("echo", lambda params: params)

# poll loop
while True:
    peer.poll_once()
```

## 메시지 타입

| Type | 용도 | 핵심 필드 |
|------|------|----------|
| `call` | 원격 메서드 호출 | method, params |
| `response` | call에 대한 응답 | reply_to, result |
| `error` | call에 대한 에러 | reply_to, error |
| `event` | 단방향 알림 | method, params |

## Wire Format

| Profile | 용도 | 형식 |
|---------|------|------|
| JSONL | 파일 전송, 디버깅 | UTF-8 compact JSON + LF |
| Frame | Pipe/소켓 전송 | 4바이트 big-endian 길이 + JSON |

## 예약 메서드

| 메서드 | 설명 |
|--------|------|
| `_capabilities` | peer 정보 반환 (이름, 스키마, 등록된 메서드) |
| `_ping` | 헬스체크 |
| `_shutdown` | graceful 종료 요청 |

## 프로젝트 구조

```
ZeroEchoPipe/
├── conformance/          # 언어 무관 적합성 테스트 (38개 + 시나리오 4개)
├── Docs/                 # 프로토콜 명세
│   └── zep-core-v0.1.md
└── zep-py/               # Python SDK
    ├── zep/
    │   ├── message.py    # parse, validate, serialize
    │   ├── peer.py       # Peer (call, emit, poll, reserved methods)
    │   ├── agent.py      # BaseAgent + @method + @on_event
    │   └── transport/    # PipeTransport (메인), FileTransport (폴백)
    └── tests/            # 38개 테스트
```

## 테스트

```bash
cd zep-py
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m tests
```

```
Ran 38 tests in 1.328s
OK
```

## 로드맵

- [x] 프로토콜 명세 v0.1
- [x] Conformance Test Suite (38개 + 시나리오 4개)
- [x] Python SDK (Message + Peer + Transport + Agent)
- [ ] Windows Named Pipe 지원
- [ ] C++ SDK
- [ ] C# SDK
- [ ] Cross-language Roundtrip
- [ ] Stella Engine 임베드

## 라이선스

MIT
