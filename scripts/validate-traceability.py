#!/usr/bin/env python3
"""렌더 층 검증 — visuals·summary·inferences·relations 가 Claim 으로 추적되는가 (Gate 2·3·4·5).

사용:  python3 validate-traceability.py understanding/<slug>/claim-ir.json [--json]
종료 코드: error 가 있으면 1.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from uc_common import (  # noqa: E402
    ATTRIBUTION_RE, CAUSAL_CONNECTIVE, COMPARATIVE_RE, EDGE_BACKING, EDGE_KINDS, SUMMARY_HEDGE_MARKERS, Issues, emit,
    entity_aliases, has_hedge, ko_counts,
    index, label_mentioned, load_ir, norm, numbers, source_numbers, weakest,
)

NODE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _refs(iss: Issues, where: str, refs, ix: dict, gate: str = "G2", required: bool = True) -> list[dict]:
    refs = refs or []
    if required and not refs:
        iss.error(gate, where, "근거 Claim 이 없다 (claims: [C..] 필요)")
    out = []
    for r in refs:
        c = ix["claims"].get(r)
        if not c:
            iss.error("G2", where, f"없는 Claim 참조: {r}")
        else:
            out.append(c)
    return out


def _evidence_text(cs: list[dict]) -> str:
    return " ".join((c.get("source_text") or "") + " " + (c.get("text") or "") for c in cs)


def _check_new_numbers(iss: Issues, where: str, text: str, cs: list[dict]) -> None:
    new = numbers(text) - numbers(_evidence_text(cs))
    if new:
        iss.error("G3", where, f"근거 Claim 에 없는 숫자: {sorted(new)}")


def check(ir: dict) -> Issues:
    iss = Issues()
    ix = index(ir)
    claims = ix["claims"]
    entities = ix["entities"]

    # inferences
    for inf in ir.get("inferences") or []:
        iid = inf.get("id", "?")
        if not re.match(r"^I\d{2,}$", iid):
            iss.error("G4", iid, "inference ID 형식은 I01")
        if inf.get("label") not in ("INFERENCE", "INTERPRETATION"):
            iss.error("G4", iid, "label 은 INFERENCE 또는 INTERPRETATION")
        if not (inf.get("reason") or "").strip():
            iss.error("G4", iid, "reason(왜 이 해석이 필요한가)이 비어 있다")
        based = _refs(iss, iid, inf.get("based_on"), ix, gate="G4")
        _check_new_numbers(iss, iid, inf.get("text", ""), based)
        if any(norm(inf.get("text", "")) == norm(c.get("text", "")) for c in based):
            iss.warn("G4", iid, "근거 Claim 과 문장이 같다 — 새 해석이 아니면 inference 로 만들지 않는다")

    # relations
    for rel in ir.get("relations") or []:
        rid = rel.get("id", "?")
        if rel.get("kind") not in EDGE_KINDS:
            iss.error("G3", rid, f"알 수 없는 relation kind: {rel.get('kind')}")
        cs = _refs(iss, rid, rel.get("claims"), ix)
        _check_backing(iss, rid, rel.get("kind"), cs)

    covered_by_visual: set[str] = set()
    for v in ir.get("visuals") or []:
        vid = v.get("id", "?")
        kind = v.get("kind")
        if not re.match(r"^V\d{2,}$", vid):
            iss.error("G2", vid, "visual ID 형식은 V01")
        if kind == "diagram":
            nodes = v.get("nodes") or []
            if len(nodes) < 2:
                iss.error("G2", vid, "diagram 에 노드가 2개 미만이다")
            elif len(nodes) < 3:
                iss.warn("G2", vid, "노드 3개 미만 — 텍스트가 더 나을 수 있다 (routing-rules §2)")
            if len(nodes) > 12:
                iss.warn("G2", vid, f"노드 {len(nodes)}개 — 개요도 + 세부도로 나누는 것을 권장")
            node_map = {}
            for nd in nodes:
                nid = nd.get("id", "?")
                where = f"{vid}.node.{nid}"
                if not NODE_ID_RE.match(nid):
                    iss.error("G2", where, "노드 id 는 영문자로 시작하는 영숫자/_")
                if nid in node_map:
                    iss.error("G2", where, "노드 id 중복")
                node_map[nid] = nd
                cs = _refs(iss, where, nd.get("claims"), ix)
                covered_by_visual.update(c["id"] for c in cs)
                if nd.get("entity") and nd["entity"] not in entities:
                    iss.error("G2", where, f"없는 entity 참조: {nd.get('entity')}")
                aliases = entity_aliases(ix, nd)
                ntexts = [c.get("text", "") + " " + c.get("source_text", "") for c in cs]
                # 노드는 여러 Claim 을 묶을 수 있으므로 근거 문장 전체를 하나로도 본다
                if cs and not label_mentioned(nd.get("label", ""), ntexts + [" ".join(ntexts)], aliases):
                    iss.warn("G3", where, f"노드 라벨 '{nd.get('label')}' 이 근거 Claim 문장에 나오지 않는다")
                _check_new_numbers(iss, where, nd.get("label", ""), cs)
            for k, e in enumerate(v.get("edges") or [], 1):
                where = f"{vid}.edge{k}({e.get('from')}→{e.get('to')})"
                for end in ("from", "to"):
                    if e.get(end) not in node_map:
                        iss.error("G2", where, f"{end} 노드 '{e.get(end)}' 가 없다")
                ek = e.get("kind")
                if ek not in EDGE_KINDS:
                    iss.error("G3", where, f"알 수 없는 edge kind: {ek}")
                refs = list(e.get("claims") or [])
                rel = None
                if e.get("relation"):
                    rel = ix["relations"].get(e["relation"])
                    if not rel:
                        iss.error("G2", where, f"없는 relation 참조: {e['relation']}")
                    else:
                        refs += rel.get("claims") or []
                if e.get("inferred"):
                    inf = ix["inferences"].get(e.get("inference"))
                    if not inf:
                        iss.error("G4", where, "inferred 엣지는 inferences[] 에 등록된 inference ID 가 필요하다")
                        continue
                    refs += inf.get("based_on") or []
                    cs = _refs(iss, where, refs, ix)
                    covered_by_visual.update(c["id"] for c in cs)
                    continue  # 추론 엣지는 점선 + INFERENCE 로 그리므로 유형 대조를 하지 않는다
                if e.get("inference"):
                    iss.error("G4", where, "inference 를 달았으면 inferred: true 로 표시한다")
                cs = _refs(iss, where, refs, ix)
                covered_by_visual.update(c["id"] for c in cs)
                _check_backing(iss, where, ek, cs)
                _check_new_numbers(iss, where, e.get("label", ""), cs)
                a, b = node_map.get(e.get("from")), node_map.get(e.get("to"))
                if a and b and cs:
                    texts = [c.get("text", "") + " " + c.get("source_text", "") for c in cs]
                    if not any(label_mentioned(a.get("label", ""), [t], entity_aliases(ix, a))
                               and label_mentioned(b.get("label", ""), [t], entity_aliases(ix, b)) for t in texts):
                        iss.warn("G3", where, "두 노드가 같은 근거 Claim 에 함께 나오지 않는다 — 원문이 이 연결을 말하는지 확인")
            if v.get("steps") or v.get("rows") or v.get("scenes"):
                iss.warn("G2", vid, "diagram 에는 nodes/edges 만 쓴다")
        elif kind == "flow":
            steps = v.get("steps") or []
            if len(steps) < 2:
                iss.error("G2", vid, "flow 단계가 2개 미만이다")
            if len(steps) > 7:
                iss.warn("G2", vid, f"단계 {len(steps)}개 — 7개 이하로 나누는 것을 권장")
            for k, s in enumerate(steps, 1):
                where = f"{vid}.step{k}"
                cs = _refs(iss, where, s.get("claims"), ix)
                covered_by_visual.update(c["id"] for c in cs)
                if cs and not any({"procedure", "temporal"} & set(c.get("type") or []) for c in cs):
                    iss.error("G3", where, "flow 단계의 근거 Claim 에 procedure/temporal 유형이 없다 (원문에 없는 순서 생성)")
                _check_new_numbers(iss, where, s.get("text", ""), cs)
        elif kind == "table":
            cols = v.get("columns") or []
            rows = v.get("rows") or []
            if not cols or not rows:
                iss.error("G2", vid, "table 에 columns 와 rows 가 필요하다")
            for k, r in enumerate(rows, 1):
                where = f"{vid}.row{k}"
                cells = r.get("cells") or []
                if cols and len(cells) != len(cols):
                    iss.error("G2", where, f"셀 {len(cells)}개 ≠ 열 {len(cols)}개")
                cs = _refs(iss, where, r.get("claims"), ix)
                covered_by_visual.update(c["id"] for c in cs)
                _check_new_numbers(iss, where, " ".join(str(x) for x in cells), cs)
        elif kind == "animation":
            scenes = v.get("scenes") or []
            if not scenes:
                iss.error("G2", vid, "animation 에 scenes 가 없다")
            for k, s in enumerate(scenes, 1):
                where = f"{vid}.scene{k}"
                cs = _refs(iss, where, s.get("claims"), ix)
                covered_by_visual.update(c["id"] for c in cs)
                if cs and not any({"temporal", "causal", "procedure"} & set(c.get("type") or []) for c in cs):
                    iss.warn("G3", where, "장면의 근거에 temporal/causal/procedure 유형이 없다 — 움직임이 필요한 주장인지 확인")
                if not (s.get("motion") or "").strip():
                    iss.error("G2", where, "motion(무엇이 움직이는가)이 비어 있다")
                _check_new_numbers(iss, where, s.get("caption", ""), cs)
        else:
            iss.error("G2", vid, f"알 수 없는 visual kind: {kind}")
        # 제목·열 이름에도 새 숫자를 넣지 않는다
        # 제목·열 이름은 문서의 절 번호 등을 가리킬 수 있으므로 원문 전체와 대조한다
        new = numbers(" ".join([v.get("title", "")] + list(v.get("columns") or []))) - source_numbers(ir)
        if new:
            iss.error("G3", f"{vid}.title/columns", f"원문에 없는 숫자: {sorted(new)}")

    # visualization 지정과 실제 visual 대조
    for cid, c in claims.items():
        want = c.get("visualization")
        if want in ("diagram", "flow", "table", "animation") and cid not in covered_by_visual:
            iss.warn("G2", cid, f"visualization={want} 인데 어떤 visual 에도 들어가지 않았다")

    # summary
    seen_s = set()
    for s in ir.get("summary") or []:
        sid = s.get("id", "?")
        if sid in seen_s:
            iss.error("G2", sid, "summary ID 중복")
        seen_s.add(sid)
        _check_sentence(iss, sid, s, ix, {}, require_claims=True)

    _check_narrative(iss, ir, ix)

    if not ir.get("summary"):
        iss.warn("G2", "summary", "summary 가 비어 있다 — 한눈에 보기 요약이 리포트에 나오지 않는다")
    return iss


def _check_sentence(iss: Issues, where: str, s: dict, ix: dict, ctx: dict, require_claims: bool = False) -> list[dict]:
    """요약·설명 본문 문장 공통 검사: 근거 연결, 새 숫자, 새 인과, 유보 제거."""
    text = s.get("text", "")
    refs, krefs, irefs = s.get("claims") or [], s.get("context") or [], s.get("inferences") or []
    if sum(bool(x) for x in (refs, krefs, irefs)) > 1:
        iss.warn("G4", where, "한 문장에 원문 근거·배경 설명·해석을 섞었다 — 독자가 무엇이 원문인지 구분할 수 없다. 문장을 나눈다")
    if require_claims or not (krefs or irefs):
        cs = _refs(iss, where, refs, ix)
    else:
        cs = _refs(iss, where, refs, ix, required=False)
    for k in krefs:
        if k not in ctx:
            iss.error("G2", where, f"없는 context 참조: {k}")
    infs = []
    for i in irefs:
        inf = ix["inferences"].get(i)
        if not inf:
            iss.error("G4", where, f"없는 inference 참조: {i}")
        else:
            infs.append(inf)
    # 해석 문장의 숫자·개수는 해석이 기대는 Claim 에서만 올 수 있다
    inf_basis = _evidence_text([ix["claims"][r] for inf in infs for r in inf.get("based_on") or [] if r in ix["claims"]]) \
        + " " + " ".join(inf.get("text", "") for inf in infs)
    basis = _evidence_text(cs) + " " + inf_basis + " " + " ".join(ctx[k].get("text", "") + " " + ctx[k].get("term", "") for k in krefs if k in ctx)
    new = numbers(text) - numbers(basis)
    if new:
        iss.error("G3", where, f"근거 Claim·배경 설명에 없는 숫자: {sorted(new)}")
    for b in re.findall(r"(?<![A-Za-z0-9])C\d{2,}(?!\d)", text):
        if b not in ix["claims"]:
            iss.error("G2", where, f"문장 속 없는 Claim ID: {b}")
    types = set()
    for c in cs:
        types.update(c.get("type") or [])
    kc = ko_counts(text) - numbers(basis) - ko_counts(basis)
    if kc:
        iss.warn("G3", where, f"근거에 없는 개수 표현(한국어 수 단어) {sorted(kc)} — 원문이 그 개수를 말하는지 확인")
    if CAUSAL_CONNECTIVE.search(text):
        if cs and "causal" not in types:
            iss.warn("G3", where, "인과 접속 표현이 있는데 근거 Claim 중 causal 유형이 없다 — 원문에 없는 인과 생성 의심")
        elif not cs and krefs:
            iss.warn("G3", where, "배경 설명(context) 문장에 인과 표현이 있다 — 배경 설명은 정의·소개만 한다")
    if cs and COMPARATIVE_RE.search(text) and "comparison" not in types:
        iss.warn("G3", where, "비교·우열 표현이 있는데 근거 Claim 중 comparison 유형이 없다 — 원문에 없는 우열 생성 의심")
    # 의견·예측·작성자 추론은 누구의 말인지 밝힌다 (narrative-rules §2-2)
    if cs and any(c.get("evidence") in ("opinion", "inference") or "prediction" in (c.get("type") or []) for c in cs) \
            and not ATTRIBUTION_RE.search(text) and not SUMMARY_HEDGE_MARKERS.search(text):
        iss.warn("G4", where, "의견·예측·추론을 근거로 한 문장인데 누구의 주장인지 드러나지 않는다 — 사실처럼 읽힐 수 있다")
    # 원문 유보가 "can / ~ㄹ 수 있다"였다면 다시 쓴 문장의 "수 있다"도 유보로 인정한다.
    # conflicting 은 원문이 유보한 것이 아니라 다른 Claim 과 어긋난 것이므로 여기서 유보를 요구하지 않는다 — 점선·배지가 표시한다.
    loose = any(re.search(r"수\s?있|\bcan\b", c.get("source_text", ""), re.I) for c in cs)
    if (cs and weakest([c.get("evidence") for c in cs]) == "uncertain"
            and not has_hedge(text, loose=loose) and not SUMMARY_HEDGE_MARKERS.search(text)):
        iss.warn("G5", where, "근거가 불확실한데 문장에 유보 표현이 없다 — 불확실성 제거 의심")
    return cs


def _check_narrative(iss: Issues, ir: dict, ix: dict) -> None:
    mode = (ir.get("meta") or {}).get("mode", "understand")
    ctx: dict[str, dict] = {}
    for k in ir.get("context") or []:
        kid = k.get("id", "?")
        if not re.match(r"^K\d{2,}$", kid):
            iss.error("G4", kid, "context ID 형식은 K01")
        if kid in ctx:
            iss.error("G4", kid, "context ID 중복")
        for f in ("term", "text", "reason"):
            if not (k.get(f) or "").strip():
                iss.error("G4", kid, f"context.{f} 가 비어 있다")
        ctx[kid] = k
    nar = ir.get("narrative")
    if not nar:
        if mode in ("understand", "visualize"):
            iss.error("G2", "narrative", f"{mode} 모드에는 읽기 페이지(narrative)가 필요하다 — references/narrative-rules.md")
        return
    used_claims: set[str] = set()
    used_ctx: set[str] = set()
    used_inf: set[str] = set()
    all_src = norm(" ".join(u.get("text", "") for u in (ir.get("source") or {}).get("units") or []))

    def sent(where: str, s: dict) -> None:
        if not (s.get("claims") or s.get("context") or s.get("inferences")):
            iss.error("G2", where, "문장에 근거(claims)·배경 설명(context)·해석(inferences)이 하나도 없다")
            return
        before = len(iss.items)
        cs = _check_sentence(iss, where, s, ix, ctx)
        if s.get("note"):  # 의도한 경고면 이유가 경고 옆에 남는다
            for it in iss.items[before:]:
                if it["level"] == "warning":
                    it["msg"] += f" [note: {s['note']}]"
        used_claims.update(c["id"] for c in cs)
        used_ctx.update(s.get("context") or [])
        used_inf.update(s.get("inferences") or [])

    if nar.get("headline"):
        sent("narrative.headline", nar["headline"])
    else:
        iss.error("G2", "narrative.headline", "핵심 문장(headline)이 없다")
    seen = set()
    for sec in nar.get("sections") or []:
        nid = sec.get("id", "?")
        if not re.match(r"^N\d{2,}$", nid) or nid in seen:
            iss.error("G2", nid, "section ID 는 N01 형식이고 중복되면 안 된다")
        seen.add(nid)
        if not sec.get("blocks"):
            iss.error("G2", nid, "section 에 blocks 가 없다")
        # 섹션 제목도 문장이다 — 본문이 근거로 삼은 Claim 에 없는 개수를 제목에 넣지 않는다
        sec_basis = " ".join(_evidence_text([ix["claims"][r] for b in sec.get("blocks") or [] for st in b.get("sentences") or []
                                             for r in st.get("claims") or [] if r in ix["claims"]]).split())
        kc = ko_counts(sec.get("title", "")) - numbers(sec_basis) - ko_counts(sec_basis)
        if kc:
            iss.warn("G3", f"{nid}.title", f"제목에 근거 없는 개수 표현 {sorted(kc)}")
        for b_i, b in enumerate(sec.get("blocks") or [], 1):
            where = f"{nid}.b{b_i}"
            kind = b.get("kind")
            if kind in ("text", "points", "callout"):
                if not b.get("sentences"):
                    iss.error("G2", where, "문장이 없다")
                for s_i, s in enumerate(b.get("sentences") or [], 1):
                    sent(f"{where}.s{s_i}", s)
            elif kind == "example":
                # 예시는 지어내지 않는다 — 원문(또는 배경 설명)에 그대로 있는 문구만 인용한다
                if not b.get("items"):
                    iss.error("G2", where, "example 블록에 items 가 없다")
                for e_i, it in enumerate(b.get("items") or [], 1):
                    w2 = f"{where}.e{e_i}"
                    q = norm(it.get("quote", ""))
                    if it.get("claims"):
                        cs = _refs(iss, w2, it.get("claims"), ix)
                        used_claims.update(c["id"] for c in cs)
                        if q and q not in all_src:
                            iss.error("G3", w2, "example 인용문이 원문에 그대로 있지 않다 — 예시는 원문에서 복사한다")
                        lab_new = numbers(it.get("label", "") + " " + b.get("label", "")) - numbers(_evidence_text(cs)) - source_numbers(ir)
                        if lab_new:
                            iss.error("G3", w2, f"example 라벨에 근거 없는 숫자: {sorted(lab_new)}")
                    elif it.get("context"):
                        for k in it["context"]:
                            if k not in ctx:
                                iss.error("G2", w2, f"없는 context 참조: {k}")
                            elif q and q not in norm(ctx[k].get("text", "")):
                                iss.error("G3", w2, f"example 인용문이 context {k} 문장에 그대로 있지 않다")
                        used_ctx.update(it["context"])
                    else:
                        iss.error("G2", w2, "example 인용에 claims 또는 context 가 없다")
            elif kind == "visual":
                vv = next((v for v in ir.get("visuals") or [] if v.get("id") == b.get("ref")), None)
                if not vv:
                    iss.error("G2", where, f"없는 visual 참조: {b.get('ref')}")
                elif b.get("caption"):
                    vbasis = _evidence_text([ix["claims"][r] for r in _visual_claims(vv) if r in ix["claims"]])
                    if numbers(b["caption"]) - numbers(vbasis) - source_numbers(ir) or ko_counts(b["caption"]) - numbers(vbasis) - ko_counts(vbasis):
                        iss.warn("G3", f"{where}.caption", "캡션에 근거 없는 숫자·개수 표현이 있다")
            else:
                iss.error("G2", where, f"알 수 없는 block kind: {kind}")
    if not nar.get("sections"):
        iss.error("G2", "narrative.sections", "설명 섹션이 없다")
    for cid, c in ix["claims"].items():
        if c.get("importance") == "core" and cid not in used_claims:
            iss.warn("G1", cid, "핵심 Claim 이 읽기 페이지 설명에 나오지 않는다")
    for kid in ctx:
        if kid not in used_ctx:
            iss.warn("G4", kid, "어느 문장에서도 쓰지 않는 context")
    # 읽기 페이지가 원문 주장의 대부분을 다루는가 — 부실한 요약을 막는다
    body = [c for c in ix["claims"].values() if c.get("importance") != "detail"]
    if body:
        ratio = len([c for c in body if c["id"] in used_claims]) / len(body)
        if ratio < 0.8 and (ir.get("explanation_plan") or {}).get("depth") != "quick":
            missing = [c["id"] for c in body if c["id"] not in used_claims]
            iss.warn("G1", "narrative", f"읽기 페이지가 detail 이 아닌 Claim 의 {ratio:.0%}만 다룬다 (80% 권장). 빠진 것: {', '.join(missing[:12])}")


def _visual_claims(v: dict) -> set[str]:
    out: set[str] = set(v.get("claims") or [])
    for key in ("nodes", "edges", "steps", "rows", "scenes"):
        for it in v.get(key) or []:
            out.update(it.get("claims") or [])
    return out


def _check_backing(iss: Issues, where: str, kind: str | None, cs: list[dict]) -> None:
    need = EDGE_BACKING.get(kind or "")
    if not need or not cs:
        return
    have = set()
    for c in cs:
        have.update(c.get("type") or [])
    if not (need & have):
        iss.error("G3", where, f"'{kind}' 연결을 뒷받침하는 Claim 유형({'/'.join(sorted(need))})이 근거에 없다 — 원문에 없는 관계 생성 의심")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ir")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    ir = load_ir(args.ir)
    iss = check(ir)
    iss.print_human("validate-traceability")
    if args.json:
        emit({"ok": not iss.errors, "gates": iss.gates(), "issues": iss.items})
    else:
        emit({"ok": not iss.errors, "visuals": len(ir.get("visuals") or []),
              "errors": len(iss.errors), "warnings": len(iss.warnings), "gates": iss.gates()})
    sys.exit(1 if iss.errors else 0)


if __name__ == "__main__":
    main()
