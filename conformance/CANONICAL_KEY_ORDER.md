# AgentBus 직렬화 정규 키 순서 (Canonical Key Order)

**본 문서는 agentbus-protocol-spec-v0.1의 보충이다.**
**Conformance serialize suite는 이 키 순서를 기준으로 문자열 완전 일치 비교를 수행한다.**

## 공통 envelope 키 순서

모든 메시지 타입 공통:

```
id, session, from, to, type, timestamp, meta
```

## type별 추가 키 순서

### call

```
..., method, params, timeout_ms
```

`timeout_ms`는 선택 필드. 없으면 생략.

### response

```
..., reply_to, result
```

### error

```
..., reply_to, error
```

### event

```
..., method, params
```

## 중첩 객체 키 순서

### meta

```
schema, (나머지 키는 사전순)
```

### error 객체

```
code, message, retryable, data
```

`data`는 선택 필드. 없으면 생략.

## 직렬화 규칙

- compact JSON (들여쓰기 없음, 불필요한 공백 없음)
- LF(`\n`) 종료
- CR 없음
- 정수는 소수점 없이 (`10000`, `42`)
- 부동소수점은 필요 시 소수점 포함 (`23.5`, `0.87`)
- boolean은 `true`/`false`
- null은 `null`
- 문자열 내 이스케이프: JSON 표준 (`\"`, `\\`, `\n`, `\t`, `\uXXXX`)
