# Traceability 규칙 · Hallucination Guard

[7]~[9] 단계에서 읽는다. 이 스킬에서 가장 중요한 검증 단계다.
`validate-claims.py`(Claim 층)와 `validate-traceability.py`(렌더 층)가 아래 규칙을 기계적으로 검사한다.
**error = Gate FAIL → build-report.py가 산출물을 쓰지 않는다.** warning은 사람이 읽고 판단한다.

---

## 1. 추적 사슬

```
viewer 카드 / 다이어그램 노드·엣지 / 표 행 / 흐름 단계 / 장면 / 요약 문장
        │ claims: [C..]   (또는 inference: I.. → based_on: [C..])
        ▼
Claim  ── source_location: P07 ──▶ source.units[P07] (행 번호) ──▶ source.md
        └ source_text: 원문 그대로의 구간 (P07 안에서 문자열 일치)
```
어느 고리라도 끊기면 사람은 원문으로 돌아갈 수 없다(Gate 6).

---

## 2. Hallucination Guard — Renderer 금지 행동

| 금지 | 검사 방법 | 등급 |
|---|---|---|
| 원문에 없는 인과관계 생성 | `causal` 엣지 → 근거 Claim 중 `causal` 유형이 하나 이상 | error |
| 원문에 없는 계층 구조 생성 | `contains` 엣지 → `relationship`/`definition` 유형 근거 | error |
| 원문에 없는 시간 순서 생성 | `sequence` 엣지·`flow` 단계 → `procedure`/`temporal` 유형 근거 | error |
| 원문에 없는 비교 우열 생성 | `comparison` 엣지 → `comparison` 유형 근거 | error |
| source-needed Claim을 사실처럼 표현 | 렌더러가 카드·요약·표 행에 근거 상태 배지를 **강제로** 붙임 | 자동 |
| inference를 fact로 승격 | `inferred: true` 엣지는 `inference` ID 필수, 점선 + `INFERENCE` 라벨 | error |
| 불확실성 제거 | 원문 구간의 유보 표현이 `text`에서 사라지면 경고, 요약은 가장 약한 근거 배지 표시 | warning / 자동 |
| 새 숫자 생성 | `text`·요약·표 셀·추론 문장·visual 제목·열 이름의 숫자가 근거 Claim에 없음 | error |
| (예외) 숫자가 든 고유 이름 | `ASD-STE100`·`3b1b`처럼 숫자가 섞인 이름이 원문 어딘가에 그대로 있으면 Claim `text`의 숫자 검사에서 뺀다 — 대명사를 이름으로 바꿔 쓰는 STE 규칙 때문. 원문에 없는 이름(`v0.4`→`v0.5`)은 그대로 error | — |
| 원문에 없는 근거 표기 | `evidence_ref`가 원문 문구 그대로도 아니고 원문 단위 ID(P..)도 가리키지 않음 / 원문에 없는 숫자 포함 | error |
| review_note 속 새 숫자 | 원문 전체에 없는 숫자(계산값이면 계산식을 함께) | warning |
| 이름 불일치 은폐 | entity에 서로 다른 이름의 alias가 있는데 해당 Claim 어디에도 `naming-drift` 플래그가 없음 (단어 75% 이상이 겹치는 표기 변형은 제외) | warning |
| 요약에서 인과 생성 | 요약에 인과 접속 표현(그 결과·때문에·따라서·so·therefore)이 있는데 근거에 `causal` Claim 없음 | warning |
| 요약에서 유보 제거 | 근거 중 가장 약한 상태가 uncertain/conflicting인데 요약 문장에 유보 표현 없음 | warning |
| 근거 없는 노드 | 노드 `claims` 비어 있음 | error |
| 노드 라벨이 근거 Claim에 등장하지 않음 | 라벨(또는 entity 이름·alias)이 근거 Claim 문장에 없음 | warning |
| 엣지 양 끝이 근거 Claim에 함께 등장하지 않음 | 두 노드 라벨이 같은 근거 Claim에 함께 나오지 않음 | warning |

### 엣지 종류 ↔ 근거 Claim 유형

| 엣지 `kind` | 근거 Claim에 있어야 할 유형(하나 이상) |
|---|---|
| `causal` | causal |
| `sequence` | procedure, temporal |
| `contains` | relationship, definition |
| `comparison` | comparison |
| `conditional` | conditional |
| `dependency` · `data-flow` · `delegation` · `association` | relationship, procedure, causal, conditional, definition |

---

## 3. 새로운 해석이 꼭 필요할 때

원문이 두 구성요소를 따로 설명했지만 연결을 말하지 않았고, 연결을 보여야 이해가 된다면:
1. `inferences[]`에 등록한다.
   ```json
   {"id": "I01", "label": "INFERENCE", "text": "Router의 출력이 Worker의 입력으로 쓰이는 것으로 보인다.",
    "based_on": ["C04", "C07"], "reason": "원문은 두 구성요소를 따로 설명하고 연결을 명시하지 않는다."}
   ```
2. 엣지에 `"inferred": true, "inference": "I01"`을 단다.
3. 렌더러가 점선 + `INFERENCE` 라벨로 그리고, 리포트 "AI가 추론한 부분"에 나열한다.

`INFERENCE` = 원문 진술에서 논리적으로 끌어낸 것. `INTERPRETATION` = 의미·의도·함의에 대한 해석.
원문 작성자가 스스로 끌어낸 추론은 Claim(`evidence: inference`)이고, **이 스킬이 덧붙인 해석**만 `inferences[]`에 들어간다. 둘을 섞지 않는다.

---

## 4. 요약 규칙 (`summary[]`)

- 문장마다 근거 Claim ID 1개 이상.
- 근거 Claim에 없는 숫자 금지(error).
- 근거 Claim보다 강하게 말하지 않는다. 근거가 `uncertain`이면 요약도 유보한다. 렌더러는 근거 중 가장 약한 상태를 배지로 붙인다(약함 순서: conflicting < source-needed < uncertain < inference < model-claim < opinion < supported < verified).
- 근거 Claim에 없는 평가어(혁신적, 완벽한, 핵심적인)를 넣지 않는다.

---

## 4-1. 읽기 페이지 규칙 (`narrative` · `context`)

| 검사 | 등급 |
|---|---|
| understand·visualize 모드에 `narrative` 없음 / headline·sections 없음 | error (G2) |
| 문장에 `claims`도 `context`도 없음 / 없는 ID 참조 / 없는 visual 참조 | error (G2) |
| 근거 Claim·context에 없는 숫자 | error (G3) |
| 인과 접속 표현인데 근거에 causal 없음 / 근거가 불확실·충돌인데 유보 없음 | warning (G3·G5) |
| `importance: core` Claim이 본문에 안 나옴 | warning (G1) |
| context의 term·text·reason 누락, ID 중복 | error (G4) |
| 어느 문장에서도 안 쓰는 context | warning (G4) |
| `example` 인용문이 원문(또는 해당 context)에 글자 그대로 없음 | error (G3) |
| 한 문장에 claims·context·inferences 혼합 | warning (G4) |
| 본문이 detail 아닌 Claim의 80% 미만을 다룸 | warning (G1) |

context는 원문 밖 정보다. 렌더러가 파란 바탕·"배경" 위첨자·"CONTEXT · 원문 밖" 라벨로 항상 구분해 표시한다.

## 5. 커버리지 (Gate 1)

- `paragraph`·`list-item`·`table-row`·`quote` 단위는 Claim이 하나 이상 있거나 `coverage.skipped`에 이유가 있어야 한다. 아니면 error.
- `heading`·`code` 단위는 자동으로 건너뛴다(코드 블록 속 주장이 중요하면 Claim을 만들어도 된다).
- skip 이유 예: "인사말", "앞 문단 반복(C04와 같음)", "예시 코드", "출처 목록 — supported의 evidence_ref로 사용".

---

## 6. Gate 판정

| Gate | FAIL 조건(error) |
|---|---|
| G1 Claim ID | ID 형식 오류·중복 / 주장 단위가 Claim도 skip 사유도 없음 |
| G2 시각 요소 연결 | 노드·엣지·행·단계·장면·요약에 근거 없음 / 없는 ID 참조 |
| G3 새 사실 금지 | source_text 불일치 / 새 숫자 / 엣지 종류를 뒷받침하는 Claim 유형 없음 |
| G4 Fact·Inference 구분 | inferred 엣지에 inference 없음 / inference 라벨 오류 / verified인데 verification 없음 / opinion이 verified |
| G5 불확실성 표시 | 외부 확인 없이 confidence medium·high / conflicting인데 conflicts_with·contradicted 없음 |
| G6 원문 복귀 | source_location이 존재하지 않는 단위 |

warning은 Gate를 막지 않지만 `gate-report.json`과 리포트 하단에 남는다. 완료 보고 때 남은 warning 수를 말한다.
의도한 warning은 사라지게 고치지 말고 이유를 남긴다 — Claim은 `review_note`, 노드·엣지·요약 문장은 `note`.

라벨 판정(`label_mentioned`): 노드 라벨 전체가 근거 문장에 있거나, 한 근거 문장 안에 라벨 토큰(조사 제거)의 절반 이상이 나오면 인정한다. entity의 이름·alias도 같은 방식으로 본다. 라벨을 통과시키려고 원문에 없는 말로 바꾸지 말고, 원문 표현을 라벨로 쓴다.


## 구조 검사와 내용 검토의 경계

G1~G6 PASS는 **구조·참조 검사 통과**다. 의미 정확성, 문단 안의 모든 주장 추출, 생략의 정당성,
외부 확인의 실제 수행과 참고 URL의 진위를 보장하지 않는다. `verified`는 작성자가 제공한 외부 확인 기록이며 자동 인증이 아니다.
`gate-report.json`의 `validation`과 Markdown/HTML에 이 범위와 검토 상태를 함께 표시한다.
검토를 수행하지 않았으면 `not-reviewed`로 남긴다. 모델 검토와 사람 검토는 `reviewer`·`method`에 명시한다.

- `reviews.source_to_claim`: 인용과 다시 쓴 Claim의 의미·조건·유보·단위 보존.
- `reviews.claim_to_narrative`: 설명 문장이 Claim보다 강해지거나 새 연결을 만들지 않았는가.
- `reviews.coverage`: 한 문단의 복수 주장 누락과 `coverage.skipped`의 생략 정당성.
- `reviews.reader_flow`: 질문 사슬, 문단 사이 비약, 용어 소개 순서와 독자 목적.

각 기록은 `status: not-reviewed | needs-revision | reviewed`를 가진다. 검토한 기록에는
`reviewer`, `method`, `checked_at`, `notes`가 필수다. 이 기록 자체도 작성자 보고이며 자동 검증 결과가 아니다.
`needs-revision`이면 IR을 수정한 뒤 다시 검토한다. 미검토 산출물은 구조 검사 통과까지만 보고한다.

### 추가 검사 규칙

| 검사 | 등급 | Gate |
|---|---|---|
| IR 파일 기준 상대 경로의 실제 source 파일을 읽을 수 없음 | error | G6 |
| 동일 분절기로 재생성한 단위와 IR의 텍스트·행 번호·순서·메타데이터 불일치 | error | G6 |
| 검토 단계·상태가 잘못되거나 수행 기록 필수 필드 누락 | error | G1 |
| 설명 기획의 필수 필드·깊이 값 누락/오류 | error | G1 |
| 설명 기획 질문에 question·claims 없음 또는 없는 Claim 참조 | error | G2 |
| 기존 IR에 설명 기획 없음 | warning | G1 |
| 외부 확인 기록에 checked_at 등 필수 필드 없음 | error | G4 |
| 외부 확인 기록의 실제 수행·진위는 검사하지 않음 | warning | G4 |

실제 파일 대조는 Claim 검증과 빌드 모두에서 수행한다. 자동 PASS에 의미 검증을 섞지 않는다.

| source_path가 IR 작업 폴더 밖을 가리킴 (상대 경로·절대 경로·심링크 포함) | error | G6 |


### STE 참고 편집 검사 (구조 Gate의 warning)

| 검사 | 등급 | Gate |
|---|---|---|
| Claim·요약·본문 절차 20 / 설명 25 공백 단위 초과 | warning | G1 |
| 설명 text 블록 6문장 초과 | warning | G1 |
| 영어의 쉬운 대체 표현 후보 또는 절차 수동태 후보 | warning | G1 |
| Claim·요약·본문 대명사 대상 불명확 후보 | warning | G3 |
| 요약·본문의 entity alias와 대표 이름 불일치 후보 | warning | G3 |

이 검사는 공식 STE 사전·품사·단어 계수·의미 보존 검사가 아니다. warning은 의미를 대조한 뒤 수정하거나 이유를 기록한다.
