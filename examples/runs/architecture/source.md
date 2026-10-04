# DocPilot 멀티 에이전트 아키텍처 설계 (v0.3 초안)

> 테스트 케이스 A — 기술 설계 문서. 가상의 사내 시스템을 설명하는 예시 문서다.

## 1. 개요

DocPilot은 사내 기술 문서를 읽고 질문에 답하는 멀티 에이전트 시스템이다. 사용자는 Slack 또는 웹 콘솔에서 질문을 보낸다.

## 2. 구성 요소

- **Orchestrator**: 사용자 질문을 받아 작업을 나누고 결과를 합친다. Orchestrator는 하위 작업을 Worker에게 위임한다.
- **Retriever**: 벡터 인덱스에서 관련 문서 조각을 찾는다. 한 번의 검색에서 최대 20개의 조각을 반환한다.
- **Worker**: Orchestrator가 넘긴 하위 작업을 처리하고 초안 답변을 만든다. Worker는 독립된 context window를 사용한다.
- **Verifier**: 초안 답변의 문장마다 인용 출처가 있는지 확인한다.
- **Index Builder**: 매일 새벽 2시에 Confluence와 GitHub 문서를 다시 색인한다.

## 3. 요청 처리 흐름

1. 사용자가 질문을 보낸다.
2. Orchestrator가 질문을 최대 4개의 하위 작업으로 나눈다.
3. 각 executor가 Retriever를 호출해 문서 조각을 받는다.
4. executor가 초안 답변을 만든다.
5. Verifier가 인용이 없는 문장을 표시한다.
6. Orchestrator가 초안들을 합쳐 최종 답변을 보낸다.

## 4. 데이터 흐름과 의존성

Retriever는 Index Builder가 만든 벡터 인덱스에 의존한다. 인덱스가 갱신되지 않으면 Retriever는 최대 24시간 지난 문서를 반환할 수 있다.

Worker 사이에는 직접 통신이 없다. 모든 중간 결과는 Orchestrator를 거친다.

## 5. 설계 판단

Worker가 독립된 context를 쓰기 때문에 Orchestrator의 context 사용량이 줄어든다. 내부 측정에서 단일 에이전트 구성 대비 Orchestrator의 평균 입력 토큰이 약 60% 감소했다(2025-08 부하 테스트, 질문 200개).

Verifier를 추가하면 환각 답변이 거의 사라질 것으로 예상한다. 이 구조는 대규모 조직에도 그대로 확장할 수 있다.

## 6. 미정 사항

- agent 수를 질문 난이도에 따라 바꿀지 아직 정하지 않았다.
- Verifier가 인용 출처의 내용까지 확인하는지는 v0.4에서 결정한다.
