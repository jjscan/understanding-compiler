# Format Router 규칙

[6] 단계에서 읽는다. 질문은 하나다 — **"이 형식이 독자(와 감독 에이전트)가 이 Claim을 확인하거나 반박하는 데 도움이 되는가?"**
위계는 텍스트 → 다이어그램 → HTML → 영상이 아니다. 예뻐 보이는 형식이 아니라 확인하기 쉬운 형식을 고른다.

---

## 1. Claim 단위 라우팅 (`visualization` 필드)

| Claim 성격 | `visualization` | 들어갈 visual |
|---|---|---|
| definition, fact, opinion, 단독 주장 | `text` | 없음 — 카드·목록으로 자동 표시 |
| procedure (순서가 핵심) | `flow` | `kind: flow` 의 `steps` |
| relationship · dependency · 구조 · 데이터 흐름 | `diagram` | `kind: diagram` 의 `nodes`/`edges` |
| comparison · 예외 목록 · 같은 속성을 가진 다수 항목 | `table` | `kind: table` 의 `rows` |
| quantitative 비교(숫자 2개 이상을 견줌) | `table` | `kind: table` (v1은 차트 대신 표) |
| temporal 상태 변화 · 메커니즘(움직임이 이해를 바꿈) | `animation` | `kind: animation` 의 `scenes` (스토리보드) |

한 Claim이 여러 visual에 들어가도 된다. 하지만 `visualization`은 **가장 이해에 도움이 되는 하나**만 적는다.

---

## 2. 형식별 언제 쓰나 / 쓰지 않나

### 구조화 텍스트 (기본값)
- 모든 Claim은 어차피 번호 문장으로 보인다. 이것이 최종 판정 기준이다.
- 다른 형식이 확인을 쉽게 만들지 못하면 텍스트로 둔다.

### 번호 흐름 (`flow`)
- 원문이 **순서를 명시**할 때만(먼저, 다음, 그 뒤, 1단계, then). 나열 순서를 실행 순서로 바꾸지 않는다.
- 단계는 7개 이하로. 넘으면 하위 흐름으로 나눈다.

### 다이어그램 (`diagram`)
- Larkin & Simon(1987): 다이어그램은 **위치가 추론의 색인이 될 때**만 텍스트보다 낫다. 즉 "누가 누구에게 연결되는가"를 눈으로 따라가야 할 때.
- 노드 3개 미만이면 만들지 않는다(텍스트가 낫다). 12개를 넘으면 개요도 + 세부도로 나눈다.
- LLM은 라벨과 화살표를 자주 잘못 놓는다 → 노드·엣지를 JSON으로만 쓰고 렌더링은 스크립트에 맡긴다. 엣지 표가 함께 출력되므로 그림을 못 읽어도 검토할 수 있다.
- 방향: 계층·위임은 `TD`, 데이터 흐름·파이프라인은 `LR`.

### 표 / 인터랙티브 HTML (`table`)
- Moreno & Mayer(2007): 상호작용은 애니메이션이나 장식이 아니라 **독자가 순서를 고르고, 멈추고, 거르는 것**이다.
- 같은 속성(열)을 가진 항목이 3개 이상이거나, 예외·조건이 여러 개일 때.
- 비교 우열은 원문이 말한 방향으로만. 원문이 "A가 더 빠르다"만 말했으면 "B가 더 느리다" 열을 추가하지 않는다. 원문이 값을 주지 않은 칸은 `—`(원문에 없음)으로 둔다.
- viewer.html 자체가 인터랙티브 HTML이다(검색·필터·원문 대조). 별도 HTML을 손으로 만들지 않는다.

### 애니메이션 후보 (`animation`)
- **기본값으로 만들지 않는다.** 아래 셋이 모두 참일 때만 후보로 올린다.
  1. 시간의 흐름이나 상태 변화가 주장의 핵심이다.
  2. 정적인 그림 한 장(전/후 2컷 포함)으로는 그 변화를 보일 수 없다.
  3. 해당 Claim이 `temporal` 또는 `causal`(메커니즘) 유형이다.
- Leahy & Sweller: 긴 내레이션 + 애니메이션은 일시적 정보 효과(transient information effect) 때문에 세부가 사라진다. 장면은 20~60초, 화면 자막 = 내레이션 문장, 멈출 수 있어야 한다.
- v1은 스토리보드(`scenes[]`: caption·motion·seconds·claims)까지만 만든다. 실제 영상(Manim 등)은 사용자가 요청할 때 장기 확장으로 다룬다.

---

## 3. 문서 종류별 기본값

| `meta.source_kind` | 자주 필요한 visual |
|---|---|
| `design-doc` | 구성요소 diagram(contains/delegation) + 데이터 흐름 diagram(data-flow) + 의존성 |
| `research-report` | 수치 table(값·단위·출처·근거 상태 열) + 결론→근거 연결 diagram(필요할 때만) |
| `ai-answer` | 대개 visual 없이 카드 + inspect 플래그. 단계가 있으면 flow |

---

## 4. 모드별 차이

| 모드 | 라우팅 방침 |
|---|---|
| `understand` | 핵심 구조 visual 1~2개. 나머지는 텍스트 |
| `inspect` | visual 최소화. 대신 flags·review_note·conflicts_with를 촘촘히 |
| `visualize` | 위 규칙이 허용하는 모든 visual. 단 엣지 하나하나가 Claim으로 뒷받침되어야 한다 |
