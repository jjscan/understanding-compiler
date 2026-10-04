---
description: Claim IR을 유지한 채 다이어그램·흐름·표로 시각화하고 모든 요소를 원문 Claim으로 추적한다 (understanding-compiler, visualize 모드)
argument-hint: "[파일 경로 | 붙여넣은 텍스트 | 비우면 직전 AI 답변]"
---

`understanding-compiler` 스킬을 **visualize 모드**로 실행한다.

1. Skill 도구로 `understanding-compiler` 를 불러 SKILL.md 의 파이프라인 [0]~[9] 을 그대로 따른다.
2. 모든 스크립트 호출에 `--mode visualize` 을 쓴다.
3. 입력: $ARGUMENTS
   - 파일 경로면 그 파일을 원문으로 쓴다.
   - 텍스트면 그 텍스트를 원문으로 쓴다.
   - 비어 있으면 이 대화의 직전 AI 답변을 원문으로 쓴다. 그것도 없을 때만 AskUserQuestion 으로 무엇을 검토할지 묻는다.
4. Hard Gate(gate-report.json 전부 PASS)를 통과하기 전에는 완료라고 보고하지 않는다.
