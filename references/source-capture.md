# 원문 확보 규칙 ([0] 단계)

원문이 빠지면 그 뒤의 추적성은 전부 의미가 없다 — 없는 부분은 Claim도, 검증도, 설명도 될 수 없다.
그래서 [0]의 목표는 "빠르게 저장"이 아니라 **"원문 전체를 손실 없이 고정"**이다.

---

## 폐쇄망 우선 규칙

외부 URL은 출처 문자열로만 보존하고 접속·다운로드하지 않는다. 아래 웹·SNS 확보 절차는 승인된 로컬 반입본의
누락 여부 점검 기준으로만 사용한다. 이미지도 승인된 로컬 파일만 읽는다. 외부 도구·패키지를 설치하지 않는다.
원문이 없으면 누락 상태를 보고하고 분석을 완료했다고 하지 않는다.

## 1. 무엇이 원문인가

| 입력 | 원문에 포함 | 포함하지 않음 |
|---|---|---|
| 파일 | 파일 전체 | — |
| 붙여넣은 텍스트 / 대화 속 답변 | 그 텍스트 전체 | — |
| 웹 글 | 본문 전체(접힌 "더 보기" 펼침), 본문 속 표·그림·캡션 | 메뉴·광고·댓글 |
| X·SNS 게시물 | 게시물 본문, **같은 작성자의 스레드 이어쓰기**, **첨부 이미지 속 글·도표**, 인용한 게시물 | 다른 사람의 답글(별도 요청 시에만) |
| PDF·슬라이드 | 본문, 표, 그림 속 글 | — |

## 2. 반드시 지킬 것

1. **원문 언어 그대로.** 플랫폼 자동 번역(X의 "번역됨" 등)을 원문으로 쓰지 않는다. "원본 보기"로 되돌린 뒤 복사한다.
2. **잘린 글 펼치기.** "더 보기", 긴 게시물 접힘, 스레드 이어쓰기를 확인한다. 같은 작성자의 연속 게시물은 원문이다.
3. **이미지는 원래 해상도로 읽는다.** 미리보기가 작다는 이유로 이미지를 빼지 않는다.
   - X 이미지: `https://pbs.twimg.com/media/<ID>?format=png&name=orig` (png가 404면 `format=jpg`)
   - 큰 이미지는 패널·영역별로 잘라 하나씩 읽는다(PIL 등).
   - 이미지 속 글·표·도표를 `source.md`에 **옮겨 적는다** — 아래 §3 형식.
4. **확보 기록을 남긴다.** `source.md` 맨 위 인용 블록에 출처 URL, 작성자, 날짜, 무엇을 포함했고 무엇을 왜 뺐는지 적는다. 이 블록은 `coverage.skipped`로 건너뛴다.
5. **못 읽은 부분은 숨기지 않는다.** 원본 해상도로도 읽을 수 없거나 접근할 수 없는 부분이 있으면 확보 기록과 최종 보고 첫 줄에 "원문 중 X는 분석하지 못했다"고 쓴다.

## 3. 이미지 옮겨 적기 형식

```markdown
## [이미지 1] Simplified Technical English 개요 (게시물 첨부)

### A. Document structure
- ASD-STE100 (Simplified Technical English) has two parts: Part 1 Writing rules and Part 2 Dictionary.
- Part 1 sections: Section 1 Words, Section 2 Noun clusters, …

### B. Anatomy of STE sentences
| Original text (not STE) | Rewritten (procedural sentence) |
|---|---|
| It is imperative that the operator ensures … | Make sure that the hydraulic reservoir is full before you start the operation. |
```

- 제목은 `[이미지 N]`으로 시작한다 → `segment-source.py`가 그 아래 단위에 `origin: image:N`을 붙이고, 리포트·뷰어가 "이미지 N에서 옮김"으로 표시한다.
- **이미지에 있는 그대로** 옮긴다. 이미지 언어(대개 영어)를 유지하고, 해석·요약·보충을 섞지 않는다. 표는 표로, 목록은 목록으로.
- 읽기 애매한 글자는 `[판독 불확실: …]`로 표시한다. 추측으로 채우지 않는다.
- 이미지가 누가 만든 것인지(작성자 직접, AI 생성, 외부 자료) 원문이 밝히지 않으면 단정하지 않는다.
