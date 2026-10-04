---
description: AI 출력의 근거 없는 단정·일반화·모호 표현·Fact/Inference 혼합·충돌을 우선 찾아 Inspect Report를 만든다 (understanding-compiler, inspect 모드)
argument-hint: "[파일 경로 | 붙여넣은 텍스트 | 비우면 직전 AI 답변]"
---

`understanding-compiler` 스킬을 **inspect 모드**로 실행한다.

1. Skill 도구로 `understanding-compiler` 를 불러 SKILL.md 의 파이프라인 [0]~[9] 을 그대로 따른다.
2. 모든 스크립트 호출에 `--mode inspect` 을 쓴다.
3. 입력: $ARGUMENTS
   - 파일 경로면 그 파일을 원문으로 쓴다.
   - 텍스트면 그 텍스트를 원문으로 쓴다.
   - 비어 있으면 이 대화의 직전 AI 답변을 원문으로 쓴다. 그것도 없을 때만 AskUserQuestion 으로 무엇을 검토할지 묻는다.
4. Hard Gate(gate-report.json 전부 PASS)를 통과하기 전에는 완료라고 보고하지 않는다.
