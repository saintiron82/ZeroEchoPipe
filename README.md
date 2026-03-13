# ZEP — Zero Echo Pipe

**프로그램 간 경량 통신 프로토콜** | Schema `zep.v0.1`

C++, Python, C#가 동일한 메시지를 읽고 쓰며, call-response 왕복을 동일하게 처리하는 최소 프로토콜.

## 설치

```bash
pip install zep-protocol
```

## 빠른 시작

### 두 에이전트가 대화하기

```python
from zep import BaseAgent, method, on_event, FileTransport

class MyAgent(BaseAgent):
    @method("greet")
    def handle_greet(self, params):
        return {"reply": f"Hello, {params['name']}!"}

    @on_event("notify")
    def handle_notify(self, params):
        print(f"Got: {params['message']}")

# 서버 에이전트
transport = FileTransport("/tmp/zep-bus")
agent = MyAgent("myagent", transport, session="demo")
agent.run()  # 블로킹
```

```python
# 클라이언트
from zep import BaseAgent, FileTransport

transport = FileTransport("/tmp/zep-bus")
client = BaseAgent("client", transport, session="demo")
client.run(blocking=False)

result = client.call("myagent", "greet", {"name": "World"})
print(result)  # {"reply": "Hello, World!"}

client.emit("myagent", "notify", {"message": "ping"})
```

### 소켓 전송 (저지연)

```python
from zep import BaseAgent, SocketTransport

# 서버
server_transport = SocketTransport("/tmp/zep.sock", is_server=True)
agent = MyAgent("myagent", server_transport, session="demo")
agent.run(blocking=False)

# 클라이언트
client_transport = SocketTransport("/tmp/zep.sock", is_server=False)
client = BaseAgent("client", client_transport, session="demo")
result = client.call("myagent", "greet", {"name": "World"})
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
| Frame | 소켓 전송 | 4바이트 big-endian 길이 + JSON |

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
    │   └── transport/    # FileTransport, SocketTransport
    └── tests/            # 30개 테스트
```

## 테스트

```bash
cd zep-py
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m tests
```

```
Ran 30 tests in 0.735s
OK
```

## 로드맵

- [x] 프로토콜 명세 v0.1
- [x] Conformance Test Suite (38개 + 시나리오 4개)
- [x] Python SDK (Message + Peer + Transport + Agent)
- [ ] C++ SDK
- [ ] C# SDK
- [ ] Cross-language Roundtrip
- [ ] Stella Engine 임베드

## 라이선스

MIT
