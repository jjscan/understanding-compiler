# Understanding Compiler

> AI가 만든 결과물을 사람이 **믿기 전에** 검토할 수 있게 만드는 Claude Code 스킬.
> 요약기도, 시각화 도구도 아니다. AI 출력과 사람의 판단 사이에 놓는 **Understanding Layer**다.

```
AI Generation → Understanding Compiler → Human Oversight → Human Decision
```

AI가 더 많은 일을 대신할수록 사람의 일은 만드는 쪽에서 **검토하고, 의심하고, 판단하는** 쪽으로 옮겨간다(Karpathy의 human oversight / understanding 논의).
이 스킬은 긴 AI 출력을 받아 다음 네 질문에 답할 수 있는 형태로 바꾼다.

1. 무엇을 주장하고 있는가? → **번호가 붙은 Claim** (C01, C02…)
2. 근거가 있는가? → **근거 상태 8종** (verified · supported · source-needed · model-claim · inference · opinion · uncertain · conflicting)
3. 어디가 불확실한가? → **REVIEW FIRST** 우선순위 목록
4. 그림의 이 화살표는 어느 주장에서 왔는가? → **모든 노드·엣지·표 행·요약 문장에 Claim ID**, Claim → 원문 단위 → 행 번호

---

## 사용

```text
/understand architecture.md            # 빠르게 이해 (기본)
/inspect                               # 직전 AI 답변의 근거 부족·일반화·충돌을 우선 탐색
/visualize research.md                 # Claim IR을 유지한 채 가장 맞는 시각 표현
```
자연어도 된다 — "이 문서를 내가 제대로 검토할 수 있게 정리해줘", "이 설계에 문제가 없는지 검토하기 쉽게 보여줘".
출력 형식은 고르지 않아도 된다. Format Router가 정보 성격에 따라 정한다.

결과는 현재 디렉터리의 `understanding/<slug>/`에 생긴다.

| 파일 | 내용 |
|---|---|
| `report.md` | Understanding / Inspect Report (한눈에 보기 → 먼저 확인할 Claim → 핵심 Claim → 관계 구조 → 비교·예외 → AI가 추론한 부분 → 원문 추적) |
| `viewer.html` | 단일 파일 뷰어. **읽기 모드(기본)**: 핵심 문장 → 쉬운 말로 다시 쓴 섹션별 설명(그림·표가 본문 속에) → 믿기 전에 확인할 것 → 원문 밖 배경 설명. 문장 위첨자를 누르면 원문 인용·근거 상태가 옆 패널에 열린다. **검토 모드**: Claim 검색, 유형·근거 필터, 원문 하이라이트, 다이어그램 노드 ↔ Claim 강조, Gate |
| `claim-ir.json` | Claim IR (모든 산출물의 SSOT) |
| `diagrams/*.mmd` | IR에서 생성된 Mermaid |
| `gate-report.json` | Hard Gate 1~6 판정과 남은 경고 |

---

## 설계 원칙

- **생성보다 이해가 먼저** — 렌더링 전에 Claim IR부터 만든다.
- **모든 출력은 원문으로 추적 가능** — 시각 요소 → Claim ID → 원문 단위(P..) → 행 번호.
- **시각화는 새 사실을 만들지 않는다** — 검증기는 인용·숫자·관계 유형의 일부 오류를 탐지한다. 의미 보존과 주장 누락은 별도 검토한다. 해석이 필요하면 `INFERENCE`로 분리해 점선으로 그린다.
- **예쁜 결과보다 감사 가능성** — Mermaid·HTML을 손으로 쓰지 않고 IR에서 기계적으로 생성한다. 그림을 못 읽어도 "연결 근거 표"로 검토할 수 있다.
- **외부 검증 없이 verified 없음** — 기본값은 `confidence: unknown`.

## 파이프라인

```
Raw AI Output → [0] 원문 고정·분절(segment-source.py) → [1] Claim Parser → [2] Language Normalizer(STE)
→ [3] Claim IR → [4] Claim Classifier → [5] Evidence/Uncertainty → validate-claims.py
→ [6] Format Router → [7] visuals·summary·inferences → validate-traceability.py
→ [8] build-report.py → [9] Hard Gate 보고
```

## Hard Gate

| Gate | 조건 |
|---|---|
| G1 | 모든 핵심 주장에 Claim ID (주장 있는 원문 단위는 Claim이 있거나 skip 이유가 있어야 함) |
| G2 | 모든 시각 요소가 하나 이상의 Claim과 연결 |
| G3 | 인용·숫자·관계 유형의 구조 검사 (source_text 원문 대조 · 새 숫자 · 엣지 종류↔Claim 유형) |
| G4 | Fact와 Inference 구분 |
| G5 | 불확실한 내용은 불확실하다고 표시 |
| G6 | 사용자가 원문으로 돌아갈 수 있음 |

하나라도 FAIL이면 `build-report.py`는 산출물을 쓰지 않는다.

---

## 설치

형제 스킬과 같이 심링크로 전역 등록한다.

```bash
S=/Users/futurewave/Documents/dev/vibelabs-skills/understanding-compiler
ln -s "$S" ~/.claude/skills/understanding-compiler
for c in understand inspect visualize; do ln -s "$S/commands/$c.md" ~/.claude/commands/$c.md; done
```
스크립트는 Python 3 표준 라이브러리만 쓴다. 뷰어의 다이어그램은 Python 표준 라이브러리로 생성한 SVG를 포함해 외부망 없이 표시한다. Mermaid 원본과 연결 근거 표도 보존한다. 원형 배치는 순서·위계를 뜻하지 않는다.

## 구조

```
understanding-compiler/
├── SKILL.md                  실행 절차 (SSOT)
├── AGENTS.md                 다른 에이전트 런타임용 요약 + 유지보수 규칙
├── commands/                 /understand /inspect /visualize
├── references/
│   ├── claim-types.md        유형 12종 · 근거 상태 8종 · 검토 플래그
│   ├── routing-rules.md      Format Router
│   ├── narrative-rules.md    읽기 페이지 · 배경 설명(CONTEXT)
│   ├── ste-guidelines.md     Claim 분해 · STE 정규화 · 이름 통일
│   └── traceability-rules.md Hallucination Guard · Gate 상세
├── schemas/claim-ir.schema.json
├── scripts/
│   ├── segment-source.py     원문 → 단위(P..) + IR 골격
│   ├── validate-claims.py    Claim 층 검증
│   ├── validate-traceability.py  렌더 층 검증
│   ├── build-report.py       Gate 재검증 → report.md · viewer.html · diagrams · gate-report.json
│   └── uc_common.py
├── templates/                understanding-report.md · inspect-report.md · viewer.html
└── examples/
    ├── architecture.md       Case A 기술 설계 문서
    ├── research-report.md    Case B 리서치 보고서
    ├── ai-output.md          Case C AI의 긴 답변
    └── runs/                 세 케이스의 실행 결과 (claim-ir.json · report.md · viewer.html)
```

## 범위 (v1)와 확장

v1은 Markdown + Mermaid + HTML까지 만든다. 애니메이션은 **스토리보드**(장면 ↔ Claim 매핑)만 만든다.
확장 후보: Manim 애니메이션 · Claim graph · 출처 인용 검증 · 웹 리서치 검증 · 문서 diff · AI 답변 비교 · 모델 간 Claim 비교 · Claim 모순 탐지 · Claim provenance graph.

## 참고

- 기획 배경 정리: <https://mems.vibelabs.kr/p/oY2jFBItPgfyr1TJN1M7Co4qj9wxeR_t> — Karpathy의 "텍스트(STE) → 다이어그램 → HTML → 영상" 논의를 "형식의 위계가 아니라, 이 형식이 주장을 확인·반박하게 해주는가"로 재해석.
- ASD-STE100 Simplified Technical English — 이 스킬은 STE를 준수하지 않고 원칙만 참고한다(약 80% 엄격도).


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


## 폐쇄망 사용

기본 실행 계약은 [폐쇄망 지침](references/closed-network.md)이다. 빌드·검증은 인터넷과 LLM API를 호출하지 않는다.
IR 작성은 승인된 사내 LLM API를 쓰는 Host에서 수행한다. API 클라이언트는 이 저장소에 포함되지 않는다.
뷰어의 CDN 코드를 제거하고 외부 연결을 차단하는 CSP를 넣었다. 실제 Host/API 설정과 로그·보존 정책은 별도 검증이 필요하다.
