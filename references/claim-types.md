# Claim 유형 · 근거 상태 · 검토 플래그

[4] Claim Classifier, [5] Evidence/Uncertainty Analyzer 단계에서 읽는다.

---

## 1. Claim 유형 (`type[]`, 하나 이상)

| 유형 | 판단 질문 | 예 |
|---|---|---|
| `fact` | 참/거짓을 확인할 수 있는 상태 진술인가? | Claude Code는 터미널에서 실행된다. |
| `definition` | "X는 Y다"로 용어·범위를 정하는가? | Sub-agent는 Main Agent가 만든 하위 에이전트다. |
| `procedure` | 행위의 단계·순서를 말하는가? | 사용자는 먼저 저장소를 복제한다. |
| `relationship` | 두 대상 사이의 구조·소속·의존·위임을 말하는가? | Main Agent는 Task를 Sub-agent에게 위임할 수 있다. |
| `comparison` | 둘 이상을 견주어 차이·우열을 말하는가? | 방식 A는 방식 B보다 지연 시간이 짧다. |
| `temporal` | 시점·기간·전후 관계·상태 변화를 말하는가? | v2 출시 뒤 캐시 계층이 추가되었다. |
| `causal` | "때문에/그래서/~하면 ~된다"로 원인→결과를 말하는가? | Context 분리는 Main Agent의 context 사용량을 줄일 수 있다. |
| `conditional` | 조건이 붙어야만 성립하는가? | 파일이 1 MB를 넘으면 업로드가 거부된다. |
| `quantitative` | 숫자·비율·단위가 주장의 핵심인가? | 응답 시간은 평균 120 ms이다. |
| `opinion` | 평가·가치 판단·권고인가? | 이 구조는 복잡한 프로젝트에 적합하다. |
| `prediction` | 미래에 대한 진술인가? | 2027년까지 사용량은 두 배가 될 것이다. |
| `uncertain` | 원문 스스로 유보하는가?(아마·추정·~일 수 있다·likely) | 병목은 디스크 I/O일 가능성이 있다. |

규칙:
- `causal`과 상관(`relationship`)을 구분한다. 원문이 "함께 증가했다"고만 했으면 `causal`이 아니다.
- 원문이 "~할 수 있다"를 **능력**의 뜻으로 쓰면(파일을 읽을 수 있다) `uncertain`이 아니다. **가능성**의 뜻이면(줄일 수 있다, 원인일 수 있다) `uncertain`을 함께 단다.
- 평가어(적합하다, 뛰어나다, 최고의, 효율적)가 들어가면 `opinion`을 단다. 사실 부분과 섞여 있으면 Claim을 쪼갠다.
- 두 대상을 잇는 진술(A는 B를 사용한다 / 호출한다 / 거친다 / 포함한다 / 의존한다)은 `fact`이면서 `relationship`이다. 둘 다 단다. 다이어그램 엣지는 `relationship`(또는 해당 유형)이 있어야 그릴 수 있다.

---

## 2. 근거 상태 (`evidence`, 정확히 하나)

먼저 위에서부터 차례로 묻고, 처음 "예"가 나오는 상태를 고른다.

| 순서 | 질문 | 상태 | 필수 동반 필드 |
|---|---|---|---|
| 1 | 같은 문서 안의 다른 Claim과 양립할 수 없거나, 외부 확인 결과와 다른가? | `conflicting` | `conflicts_with` 또는 `verification.result: contradicted` |
| 2 | **이번 실행에서** 웹·파일·도구로 직접 확인했고 일치했는가? | `verified` | `verification{method, reference, result: confirmed}` |
| 3 | 원문이 이 주장 옆에 출처·데이터·인용·실험 결과를 제시하는가? | `supported` | `evidence_ref`(원문 속 근거 문구) |
| 4 | 평가·권고·가치 판단인가? | `opinion` | — |
| 5 | 원문이 스스로 유보하는가?(아마, 추정, 가능성, likely, may) | `uncertain` | — |
| 6 | 원문 작성자가 다른 진술에서 끌어낸 결론인가?(따라서, 그러므로, 이는 ~를 의미한다) | `inference` | `dependencies`(전제 Claim) 권장 |
| 7 | 외부 출처로 판가름할 수 있는 사실·통계·역사·제품 사양인데 출처가 없는가? | `source-needed` | — |
| 8 | 그 밖에 작성자가 근거 없이 단언한 내용(설계 결정, 일반론, 모델 자신의 설명) | `model-claim` | — |

**supported의 문턱:** 출처는 독자가 찾아갈 수 있어야 한다 — 이름·연도·URL·데이터셋·로그 이름 같은 식별자가 하나 이상. "업계 조사에 따르면", "연구에 의하면", "전문가들은"처럼 식별자 없는 출처 표기는 `supported`가 아니라 `source-needed`이고 `unsupported` 플래그를 단다. 원문 자체의 데이터(같은 문서의 표·측정 결과)를 근거로 든 경우는 `supported`이며 `evidence_ref`에 그 표·문단을 적는다.

**인용 자체가 주장일 때:** "GitLab 2023 보고서는 ~라고 밝혔다"는 *보고서가 그렇게 말했다*는 주장이다. 식별자(보고서 이름·연도)가 있으면 `supported`, `evidence_ref`는 그 인용 문구, `confidence: unknown`. 출처가 실제로 그렇게 말하는지는 이 문서 안에서 확인할 수 없으므로, 쪽·수치·링크가 없으면 `number-unclear` 또는 `review_note`로 남긴다. 식별자가 없으면 `source-needed`.

**연구 보고서의 자체 데이터:** 표·측정 결과 행은 `supported`(`evidence_ref` = 데이터 출처 표기, 예: "리뷰 시스템 로그 기준")이고, 조사 방법 진술(표본 수·기간)은 `model-claim`이다. `supported`는 "출처·데이터가 제시됨"이지 "참임"이 아니다 — 리포트 배지도 그렇게 표시한다.

**충돌의 양쪽:** 두 Claim이 양립할 수 없으면 **양쪽 모두** `conflicting`으로 두고 서로를 `conflicts_with`에 적는다. 원래 성격(opinion, prediction 등)은 `type`에 남는다. 어느 쪽이 맞는지 판정하지 않는다 — 그것이 사람이 할 일이다.

`model-claim`과 `source-needed`의 차이: source-needed는 "출처를 찾으면 끝나는" 주장이고, model-claim은 "원문이 그렇게 말한다는 것만 보장되는" 주장이다. 설계 문서의 설계 결정("Orchestrator는 Worker 3개를 둔다")은 model-claim이다 — 틀린 게 아니라 작성자가 정한 것이다.

### confidence 규칙
- 외부 확인을 하지 않았으면 기본값은 `unknown`.
- `medium`/`high`는 `verified` 또는 `supported`일 때만 허용한다.
- `low`는 근거가 약하다는 판단을 명시할 때 쓴다(예: supported인데 출처가 블로그 하나).
- `opinion`은 `verified`가 될 수 없다.

### 금지
- 확인하지 않은 Claim을 `verified`로 올리기.
- `inference`를 `fact`처럼 다시 쓰기("~로 보인다" → "~이다").
- 원문의 유보 표현을 지우기.

---

## 3. 검토 플래그 (`flags[]`, inspect 모드에서 특히 중요)

| 플래그 | 뜻 | 신호 |
|---|---|---|
| `unsupported` | 강한 단정인데 근거가 없다 | "항상", "반드시", "확실히" + 출처 없음 |
| `overgeneralization` | 일부 사례를 전체로 일반화 | "모든", "대부분의 기업", "누구나", "언제나" |
| `vague` | 검토할 수 없을 만큼 모호 | "상당히", "크게", "여러", "최적의", 측정 기준 없는 "개선" |
| `fact-inference-mix` | 한 문장에 사실과 추론이 섞여 원문이 둘을 구분하지 않음 | "~했고, 따라서 ~일 것이다" |
| `naming-drift` | 같은 대상을 여러 이름으로 부름(혹은 다른 대상인지 불분명) | worker / agent / executor |
| `missing-condition` | 조건·범위가 빠져 과장될 위험 | "빠르다"(무엇보다? 어떤 부하에서?) |
| `number-unclear` | 숫자의 단위·기준·시점이 없음 | "30% 개선"(무엇 대비?) |
| `hedge-dropped-in-source` | 원문 안에서 같은 내용의 확신 강도가 바뀜 (유보→단정, 단정→유보, 나오는 순서와 무관) | P04 "가능성" → P11 "원인이다" / "필수다" → "불가능에 가깝다" |
| `overclaim` | 결론·해석·권고가 원문 자신의 데이터·한계가 허용하는 것보다 강함 | 상관→인과, 대리 지표→본래 대상, 희망 팀 자료→"모든 팀", 한계 절과 맞지 않는 단정 |
| `compound-split` | 원문 한 문장을 여러 Claim으로 쪼갰음(기록용) | — |
| `outdated-risk` | 시점에 민감한데 기준 시점이 없음 | 가격, 버전, "최신" |

`flags`가 있으면 `review_note`에 한 줄로 이유를 적는다. 리포트의 REVIEW FIRST에 그대로 노출된다.

---

## 4. 중요도·위험

- `importance: core` — 이 Claim이 틀리면 문서의 결론이 무너진다. 문서당 대개 3~10개.
- `risk: high` — 틀렸을 때 비용이 크다(보안, 비용, 법, 데이터 손실, 의사결정 근거).

REVIEW FIRST 우선순위 점수(build-report.py가 계산):
`conflicting 100 · source-needed 70 · inference 55 · uncertain 55 · model-claim 35 · opinion 30 · supported 10 · verified 0`
+ `risk high 30 / medium 10` + `core 10` + `근거 없는 causal·prediction 10` + `source-needed 수치 10` + `confidence low 15` + `플래그 1개당 20`(compound-split 제외).
점수 50 이상을 우선 검토로 올리고, 최대 12개까지 보여준다.
의도: 설계 문서의 평범한 설계 결정(model-claim + core = 45)은 올라오지 않고, 플래그·위험·근거 없는 인과가 붙은 Claim이 올라온다. 무언가 꼭 검토해야 한다면 점수를 조작하지 말고 `flags`·`risk`를 정확히 단다.


외부 확인 기록의 `method`, `reference`, `result`, `checked_at`는 필수다.
`verified`는 작성자가 기록한 확인 결과이며 실제 수행과 출처 진위를 스크립트가 인증하지 않는다.
근거·확실성·충돌은 함께 존재할 수 있다. 기존 evidence 배지만으로 전체 판단을 대신하지 말고
`type[]`, `confidence`, `conflicts_with`와 별도의 `reviews` 기록을 함께 확인한다.
