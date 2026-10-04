# AGENTS.md — understanding-compiler

이 저장소를 실행하거나 고치는 모든 에이전트(Claude Code, Codex, Kimi, Gemini 등)를 위한 규칙이다.
실행 절차는 `SKILL.md`가 SSOT다. 이 파일은 **SKILL.md를 읽지 못하는 런타임에서의 진입 요약**과 **유지보수 규칙**을 담는다.

---

## 1. 이 스킬이 하는 일 (한 문단)

AI가 만든 긴 문서를 사람이 믿기 전에 검토할 수 있게, 원문을 Claim 단위로 쪼개 ID를 붙이고(Claim IR),
근거 상태·불확실성을 표시한 뒤, 정보 성격에 맞는 표현(텍스트·흐름·Mermaid·표·HTML 뷰어)으로 렌더링한다.
모든 시각 요소는 Claim ID → 원문 단위(P..) → 행 번호로 추적되고, 스크립트가 그 사슬을 검증한다.
결과물은 두 겹이다: 원문을 안 읽은 사람을 위한 **읽기 페이지**(기본 화면)와, 주장을 하나씩 대조하는 **검토 모드**.
요약기나 시각화 도구가 아니다. **감사 가능성이 시각적 완성도보다 우선이지만, 이해되지 않는 감사 화면은 목적을 놓친 것이다.**

## 2. 실행 요약 (SKILL.md를 읽을 수 없을 때)

```bash
S=<이 저장소 경로>
mkdir -p understanding/<slug> && cp <원문> understanding/<slug>/source.md   # 원문은 수정하지 않는다
python3 $S/scripts/segment-source.py understanding/<slug>/source.md --mode understand --kind other
# claim-ir.json 의 claims[] / entities[] / coverage.skipped[] 를 채운다 (references/ste-guidelines.md, claim-types.md)
python3 $S/scripts/validate-claims.py understanding/<slug>/claim-ir.json
# visuals[] / summary[] / inferences[] / narrative / context 를 채운다 (routing-rules.md, narrative-rules.md, traceability-rules.md)
python3 $S/scripts/validate-traceability.py understanding/<slug>/claim-ir.json
python3 $S/scripts/build-report.py understanding/<slug>/claim-ir.json --mode understand
```
`build-report.py`가 error 0으로 끝나고 `gate-report.json`의 G1~G6이 모두 PASS여야 완료다.

## 3. 절대 하지 말 것

- 외부 확인 없이 `evidence: verified` 또는 `confidence: medium/high`.
- 원문에 없는 인과·계층·순서·우열·숫자를 Claim·엣지·요약·표에 넣기.
- 원문의 유보 표현(아마, 추정, 가능성, may, likely)을 지우기.
- Mermaid·HTML을 손으로 쓰기. `visuals[]` JSON만 쓰고 렌더링은 `build-report.py`에 맡긴다.
- 해석을 Claim에 섞기. 이 스킬이 덧붙이는 해석은 `inferences[]`(INFERENCE/INTERPRETATION)에만.
- 검증기가 막는다고 검증기를 약하게 고치기. 먼저 IR이 틀렸는지 본다.

## 4. 유지보수 규칙

- **스크립트는 Python 표준 라이브러리만.** 설치 없이 어디서나 돌아가야 한다(형제 스킬과 같은 원칙).
- 필드를 추가·변경하면 세 곳을 함께 고친다: `schemas/claim-ir.schema.json` · `scripts/uc_common.py`의 enum · 해당 `references/*.md`.
- 검사 규칙을 추가하면 `references/traceability-rules.md` 표에 등급(error/warning)과 Gate를 적는다. 문서에 없는 검사는 넣지 않는다.
- error는 "원문 추적이 끊기거나 새 사실이 생긴 것이 확실한 경우"에만. 휴리스틱(라벨 언급, 유보 표현, 어절 수)은 warning.
- 예시(`examples/`)를 바꾸면 `examples/runs/`의 실행 결과를 다시 만들고 `build-report.py`가 통과하는지 확인한다.
- 버그를 고칠 때는 디버깅 순서를 따른다: 재현(어떤 IR·명령에서) → 원인 지점 특정 → 수정 → 세 예시를 다시 빌드해 재발하지 않는지 확인.
- 사용자 대상 문서·응답은 한국어. 코드 식별자·필드 이름은 영어 그대로.

## 5. 파일 지도

| 경로 | 역할 |
|---|---|
| `SKILL.md` | 실행 절차 SSOT (파이프라인 [0]~[9], Hard Gate) |
| `references/` | 단계별 상세 규칙 (STE·유형·라우팅·읽기 페이지·추적) |
| `schemas/claim-ir.schema.json` | IR 필드 정의 |
| `scripts/segment-source.py` | 원문 → 단위(P..) + IR 골격 |
| `scripts/validate-claims.py` | Claim 층 검증 |
| `scripts/validate-traceability.py` | 렌더 층 검증 |
| `scripts/build-report.py` | Gate 재검증 → report.md / viewer.html / diagrams / gate-report.json |
| `templates/` | 리포트 Markdown 2종 + 뷰어 HTML |
| `commands/` | `/understand` `/inspect` `/visualize` 슬래시 명령 |
| `examples/` | 테스트 케이스 A(설계)·B(리서치)·C(AI 답변) 입력, `runs/`에 실행 결과 |


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


### STE 참고 편집 검사 (구조 Gate의 warning)

| 검사 | 등급 | Gate |
|---|---|---|
| Claim·요약·본문 절차 20 / 설명 25 공백 단위 초과 | warning | G1 |
| 설명 text 블록 6문장 초과 | warning | G1 |
| 영어의 쉬운 대체 표현 후보 또는 절차 수동태 후보 | warning | G1 |
| Claim·요약·본문 대명사 대상 불명확 후보 | warning | G3 |
| 요약·본문의 entity alias와 대표 이름 불일치 후보 | warning | G3 |

이 검사는 공식 STE 사전·품사·단어 계수·의미 보존 검사가 아니다. warning은 의미를 대조한 뒤 수정하거나 이유를 기록한다.
