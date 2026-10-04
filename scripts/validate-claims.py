#!/usr/bin/env python3
"""Claim 층 검증 — Gate 1·3·4·5·6 의 Claim 관련 항목과 STE 문장 점검.

사용:  python3 validate-claims.py understanding/<slug>/claim-ir.json [--json]
종료 코드: error 가 있으면 1.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from uc_common import (  # noqa: E402
    CLAIM_TYPES, COMPOUND_HINT, CONFIDENCE, CONTENT_UNIT_KINDS, EVIDENCE, FLAGS, IMPORTANCE,
    PRONOUN_START, RISK, VISUALIZATION, Issues, emit, has_hedge, index, load_ir, norm, numbers,
    sentence_count, source_numbers, strip_known_identifiers, unit_ids_in, word_count,
)
from uc_common import check_ste_style, check_source, REVIEW_STATES, NARRATIVE_DEPTHS
from uc_common import _tokens  # noqa: E402

ID_RE = {
    "claim": re.compile(r"^C\d{2,}$"),
    "unit": re.compile(r"^P\d{2,}$"),
    "entity": re.compile(r"^E\d{2,}$"),
}
REQUIRED = ["id", "text", "type", "source_text", "source_location", "evidence", "confidence", "visualization"]


def check(ir: dict) -> Issues:
    iss = check_source(ir)
    meta = ir.get("meta") or {}
    for k in ("title", "mode", "source_path"):
        if not meta.get(k):
            iss.error("G6", "meta", f"meta.{k} 가 비어 있다")
    if meta.get("mode") not in (None, "understand", "inspect", "visualize"):
        iss.error("G1", "meta.mode", f"알 수 없는 mode: {meta.get('mode')}")

    units = (ir.get("source") or {}).get("units") or []
    if not units:
        iss.error("G6", "source.units", "원문 단위가 없다. segment-source.py 를 먼저 실행한다")
    claims = ir.get("claims") or []
    if not claims:
        iss.error("G1", "claims", "Claim 이 하나도 없다")

    ix = index(ir)
    ext = bool(meta.get("external_verification"))
    src_nums = source_numbers(ir)
    src_all = " ".join(u.get("text", "") for u in units)

    for stage, record in (ir.get("reviews") or {}).items():
        if stage not in {"source_to_claim", "claim_to_narrative", "coverage", "reader_flow"}:
            iss.error("G1", "reviews", f"알 수 없는 검토 단계: {stage}")
        if not isinstance(record, dict) or record.get("status") not in REVIEW_STATES:
            iss.error("G1", f"reviews.{stage}", "검토 상태 형식이 잘못됐다")
        elif record.get("status") != "not-reviewed" and not all(record.get(k) for k in ("reviewer", "method", "checked_at", "notes")):
            iss.error("G1", f"reviews.{stage}", "검토 기록에는 reviewer·method·checked_at·notes가 필요하다")
    plan = ir.get("explanation_plan")
    if plan:
        if plan.get("depth") not in NARRATIVE_DEPTHS or not all(plan.get(k) for k in ("audience", "goal", "opening_question", "questions")):
            iss.error("G1", "explanation_plan", "독자·목적·도입 질문·질문 사슬·depth(quick/standard/deep)를 채운다")
        for question in plan.get("questions") or []:
            if not question.get("question") or not question.get("claims"):
                iss.error("G2", "explanation_plan", "각 질문은 question과 claims를 가진다")
            for cid in question.get("claims") or []:
                if cid not in ix["claims"]:
                    iss.error("G2", "explanation_plan", f"없는 Claim 참조: {cid}")
    else:
        iss.warn("G1", "explanation_plan", "독자 중심 설명 기획이 없다. 기존 IR 호환을 위해 경고로 표시한다")

    # 중복 ID
    seen: set[str] = set()
    for c in claims:
        cid = c.get("id", "?")
        if cid in seen:
            iss.error("G1", cid, "Claim ID 중복")
        seen.add(cid)

    # entities
    alias_map: dict[str, str] = {}
    for e in ir.get("entities") or []:
        eid = e.get("id", "?")
        if not ID_RE["entity"].match(eid):
            iss.error("G1", eid, "entity ID 형식은 E01")
        if not e.get("name"):
            iss.error("G3", eid, "entity name 이 비어 있다")
        for a in e.get("aliases") or []:
            if norm(a).lower() != norm(e.get("name", "")).lower():
                alias_map[a] = e.get("name", "")
        for ref in e.get("claims") or []:
            if ref not in ix["claims"]:
                iss.error("G2", eid, f"없는 Claim 참조: {ref}")

    for c in claims:
        cid = c.get("id", "?")
        for f in REQUIRED:
            if f not in c or c[f] in (None, "", []):
                iss.error("G1", cid, f"필수 필드 누락: {f}")
        if not ID_RE["claim"].match(cid):
            iss.error("G1", cid, "Claim ID 형식은 C01")

        types = c.get("type") or []
        if isinstance(types, str):
            iss.error("G1", cid, "type 은 배열이어야 한다 (예: [\"fact\"])")
            types = [types]
        for t in types:
            if t not in CLAIM_TYPES:
                iss.error("G1", cid, f"알 수 없는 type: {t}")
        ev = c.get("evidence")
        if ev not in EVIDENCE:
            iss.error("G4", cid, f"알 수 없는 evidence: {ev}")
        conf = c.get("confidence")
        if conf not in CONFIDENCE:
            iss.error("G5", cid, f"알 수 없는 confidence: {conf}")
        if c.get("visualization") not in VISUALIZATION:
            iss.error("G1", cid, f"알 수 없는 visualization: {c.get('visualization')}")
        if c.get("importance") and c["importance"] not in IMPORTANCE:
            iss.error("G1", cid, f"알 수 없는 importance: {c['importance']}")
        if c.get("risk") and c["risk"] not in RISK:
            iss.error("G1", cid, f"알 수 없는 risk: {c['risk']}")
        for fl in c.get("flags") or []:
            if fl not in FLAGS:
                iss.error("G1", cid, f"알 수 없는 flag: {fl}")
        if [f for f in c.get("flags") or [] if f != "compound-split"] and not c.get("review_note"):
            iss.warn("G5", cid, "flags 가 있으면 review_note 에 이유를 한 줄 적는다")

        # G6: 원문 위치
        loc = c.get("source_location")
        unit = ix["units"].get(loc)
        if loc and not unit:
            iss.error("G6", cid, f"source_location {loc} 이 원문 단위에 없다")
        st = c.get("source_text") or ""
        if unit and st and norm(st) not in norm(unit.get("text", "")):
            iss.error("G3", cid, f"source_text 가 {loc} 원문에 그대로 있지 않다 (원문을 복사해야 한다)")

        # G3: 새 숫자
        txt = c.get("text") or ""
        new_nums = numbers(strip_known_identifiers(txt, src_all)) - numbers(st)
        if new_nums:
            iss.error("G3", cid, f"원문 구간에 없는 숫자: {sorted(new_nums)}")

        # G4/G5: 근거 상태 규칙
        ver = c.get("verification")
        if ev == "verified":
            if not ver or ver.get("result") != "confirmed":
                iss.error("G4", cid, "verified 는 verification{method, reference, result: confirmed} 이 있어야 한다")
            if not ext:
                iss.error("G4", cid, "meta.external_verification 이 false 인데 verified 가 있다")
        if ver:
            iss.warn("G4", cid, "외부 확인 기록은 작성자 제공이며 실제 조회 수행과 출처 진위는 자동 검증하지 않았다")
            for k in ("method", "reference", "result", "checked_at"):
                if not ver.get(k):
                    iss.error("G4", cid, f"verification.{k} 누락")
        if ev == "supported" and not c.get("evidence_ref"):
            iss.error("G4", cid, "supported 는 evidence_ref(원문 속 근거 문구)가 있어야 한다")
        ref = c.get("evidence_ref")
        if ref:
            quoted = any(norm(ref) in norm(u.get("text", "")) for u in units)
            pointed = [p for p in unit_ids_in(ref)]
            if pointed:
                for p in pointed:
                    if p not in ix["units"]:
                        iss.error("G6", cid, f"evidence_ref 가 없는 원문 단위 {p} 를 가리킨다")
            elif not quoted:
                iss.error("G3", cid, "evidence_ref 는 원문 문구를 그대로 복사하거나 원문 단위 ID(P..)를 가리켜야 한다")
            extra = numbers(ref) - src_nums
            if extra:
                iss.error("G3", cid, f"evidence_ref 에 원문에 없는 숫자: {sorted(extra)}")
        if c.get("review_note"):
            extra = numbers(c["review_note"]) - src_nums
            if extra:
                iss.warn("G3", cid, f"review_note 에 원문에 없는 숫자 {sorted(extra)} — 계산한 값이면 계산식을 함께 적는다")
        if ev == "conflicting":
            cw = c.get("conflicts_with") or []
            if not cw and not (ver and ver.get("result") == "contradicted"):
                iss.error("G5", cid, "conflicting 은 conflicts_with 또는 verification.result=contradicted 가 필요하다")
            for ref in cw:
                if ref not in ix["claims"]:
                    iss.error("G2", cid, f"conflicts_with 가 없는 Claim 참조: {ref}")
        if conf in ("medium", "high") and ev not in ("verified", "supported"):
            iss.error("G5", cid, f"confidence {conf} 는 verified/supported 일 때만 허용 (외부 확인 없음 → unknown)")
        if "opinion" in types and ev == "verified":
            iss.error("G4", cid, "opinion 은 verified 가 될 수 없다")
        if ev == "opinion" and "opinion" not in types:
            iss.warn("G4", cid, "evidence 가 opinion 이면 type 에도 opinion 을 단다")
        if ev == "uncertain" and not ({"uncertain", "prediction"} & set(types)):
            iss.warn("G5", cid, "evidence 가 uncertain 이면 type 에 uncertain(또는 prediction)을 단다")
        for ref in c.get("dependencies") or []:
            if ref not in ix["claims"]:
                iss.error("G2", cid, f"dependencies 가 없는 Claim 참조: {ref}")
        for ref in c.get("entities") or []:
            if ref not in ix["entities"]:
                iss.error("G2", cid, f"없는 entity 참조: {ref}")

        # G5: 유보 표현 보존
        if st and has_hedge(st, loose=True) and not has_hedge(txt, loose=True) and ev not in ("uncertain", "inference", "opinion"):
            iss.warn("G5", cid, "원문 구간에 유보 표현이 있는데 text·evidence 에서 사라졌다 (불확실성 제거 의심)")

        # STE 문장 점검 (warning)
        if txt:
            if sentence_count(txt) > 1:
                iss.warn("G1", cid, "text 가 두 문장 이상이다 — 한 Claim 한 의미")
            check_ste_style(iss, cid, txt, procedural="procedure" in types)
            # 한국어 문장 속 영어 and/because 는 대개 인용한 고유 이름("Punctuation and word counts")이다
            hint_txt = re.sub(r"\b(and|because|so)\b", " ", txt) if re.search(r"[가-힣]", txt) else txt
            if COMPOUND_HINT.search(hint_txt) and "causal" not in types and "conditional" not in types:
                iss.warn("G1", cid, "접속·이유 표현이 있다 — 두 주장이 섞였는지 확인")
            for alias, name in alias_map.items():  # noqa: B007
                if re.search(rf"(?<![\w가-힣]){re.escape(alias)}", txt, re.I) and name.lower() not in txt.lower():
                    iss.warn("G3", cid, f"alias '{alias}' 대신 대표 이름 '{name}' 을 쓴다")

    # 이름 불일치 자체가 검토 지점이다 (ste-guidelines §3)
    for e in ir.get("entities") or []:
        # "원격 팀"/"원격 근무 팀"처럼 단어 대부분(75% 이상)이 겹치는 변형은 이름 불일치로 보지 않는다
        nt = set(_tokens(e.get("name", "")))

        def variant(a: str) -> bool:
            at = set(_tokens(a))
            small = min(len(nt), len(at))
            return bool(small) and len(nt & at) / small >= 0.75

        als = [a for a in e.get("aliases") or [] if not variant(a)]
        if not als:
            continue
        users = [c for c in claims if any(norm(a).lower() in norm(c.get("source_text", "")).lower() for a in als)]
        if users and not any("naming-drift" in (c.get("flags") or []) for c in users):
            iss.warn("G3", e.get("id", "?"), f"원문이 '{e.get('name')}' 을 {als} 로도 부르는데 naming-drift 플래그가 하나도 없다")

    # G1: 커버리지
    covered = {c.get("source_location") for c in claims}
    skipped: dict[str, str] = {}
    for s in (ir.get("coverage") or {}).get("skipped") or []:
        u = s.get("unit")
        if u not in ix["units"]:
            iss.error("G6", f"coverage.{u}", "skip 대상 단위가 원문에 없다")
        if not (s.get("reason") or "").strip():
            iss.error("G1", f"coverage.{u}", "skip 이유가 비어 있다")
        skipped[u] = s.get("reason", "")
        if u in covered:
            iss.warn("G1", f"coverage.{u}", "Claim 이 있는 단위를 skip 목록에도 넣었다")
    for u in units:
        if u.get("kind") in CONTENT_UNIT_KINDS and u["id"] not in covered and u["id"] not in skipped:
            iss.error("G1", u["id"], f"Claim 도 skip 이유도 없는 원문 단위 ({u.get('kind')}, {u.get('line_start')}행): "
                                     f"\"{norm(u.get('text', ''))[:60]}\"")
    return iss


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ir")
    ap.add_argument("--json", action="store_true", help="결과를 JSON 으로 stdout 에 출력")
    args = ap.parse_args()
    ir = load_ir(args.ir)
    iss = check(ir)
    iss.print_human("validate-claims")
    if args.json:
        emit({"ok": not iss.errors, "gates": iss.gates(), "issues": iss.items})
    else:
        emit({"ok": not iss.errors, "claims": len(ir.get("claims") or []),
              "errors": len(iss.errors), "warnings": len(iss.warnings), "gates": iss.gates()})
    sys.exit(1 if iss.errors else 0)


if __name__ == "__main__":
    main()
