#!/usr/bin/env python3
"""[8] 렌더링 — Claim IR → report.md + viewer.html + diagrams/*.mmd + gate-report.json.

두 검증기를 먼저 돌리고, error 가 있으면 아무것도 쓰지 않고 종료한다(Hard Gate).
Mermaid·HTML 은 IR 에서 기계적으로 생성한다 — 손으로 쓴 화살표가 끼어들 틈을 없애기 위해서다.

사용:
  python3 build-report.py understanding/<slug>/claim-ir.json [--mode understand|inspect|visualize] [--out DIR]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import datetime as dt
import importlib.util
import json
import math
import textwrap
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from uc_common import (  # noqa: E402
    review_status, CONTENT_UNIT_KINDS, EVIDENCE, EVIDENCE_LABEL_KO, Issues, emit, index, load_ir, weakest,
)

TEMPLATES = HERE.parent / "templates"
EV_SCORE = {"conflicting": 100, "source-needed": 70, "inference": 55, "uncertain": 55,
            "model-claim": 35, "opinion": 30, "supported": 10, "verified": 0}
REVIEW_THRESHOLD = 50
REVIEW_MAX = 12
FLAG_KO = {
    "unsupported": "근거 없는 강한 단정", "overgeneralization": "지나친 일반화", "vague": "모호한 표현",
    "fact-inference-mix": "사실·추론 혼합", "naming-drift": "이름 불일치", "missing-condition": "조건 누락",
    "number-unclear": "숫자 기준 불명확", "hedge-dropped-in-source": "원문 안에서 유보→단정",
    "compound-split": "복합 문장 분해", "outdated-risk": "시점 민감", "overclaim": "근거보다 강한 결론",
}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------- 계산

def score(c: dict) -> int:
    """REVIEW FIRST 우선순위 (claim-types.md §4). 설계 결정 같은 평범한 작성자 단언은 50 미만에 머물고,
    플래그·위험·근거 없는 인과가 붙어야 올라온다."""
    ev = c.get("evidence")
    types = set(c.get("type") or [])
    grounded = ev in ("verified", "supported")
    s = EV_SCORE.get(ev, 0)
    s += {"high": 30, "medium": 10}.get(c.get("risk"), 0)
    s += 10 if c.get("importance") == "core" else 0
    s += 10 if ({"causal", "prediction"} & types) and not grounded else 0
    s += 10 if "quantitative" in types and ev == "source-needed" else 0
    s += 15 if c.get("confidence") == "low" else 0
    s += 20 * len([f for f in c.get("flags") or [] if f != "compound-split"])
    return s


def review_reason(c: dict) -> str:
    parts = [EVIDENCE_LABEL_KO.get(c.get("evidence"), c.get("evidence", ""))]
    types = set(c.get("type") or [])
    if "causal" in types and c.get("evidence") not in ("verified", "supported"):
        parts.append("근거 없는 인과")
    for f in c.get("flags") or []:
        if f != "compound-split":
            parts.append(FLAG_KO.get(f, f))
    if c.get("risk") == "high":
        parts.append("위험 높음")
    if c.get("conflicts_with"):
        parts.append("충돌: " + ", ".join(c["conflicts_with"]))
    return " · ".join(dict.fromkeys(parts))


def counts(ir: dict) -> dict:
    cs = ir.get("claims") or []
    by_ev = {e: 0 for e in EVIDENCE}
    by_type: dict[str, int] = {}
    for c in cs:
        by_ev[c.get("evidence")] = by_ev.get(c.get("evidence"), 0) + 1
        for t in c.get("type") or []:
            by_type[t] = by_type.get(t, 0) + 1
    return {
        "total": len(cs),
        "grounded": by_ev["verified"] + by_ev["supported"],
        "source_needed": by_ev["source-needed"],
        "inference": by_ev["inference"] + len(ir.get("inferences") or []),
        "low_confidence": sum(1 for c in cs if c.get("confidence") == "low"),
        "inference_in_source": by_ev["inference"],
        "inference_added": len(ir.get("inferences") or []),
        "uncertain": by_ev["uncertain"],
        "conflicting": by_ev["conflicting"],
        "model_claim": by_ev["model-claim"],
        "opinion": by_ev["opinion"],
        "by_evidence": by_ev,
        "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        "fact": by_type.get("fact", 0),
    }


# ---------------------------------------------------------------- Mermaid

def _mq(s: str) -> str:
    return (s or "").replace('"', "#quot;").replace("\n", " ")


def mermaid_for(v: dict, ix: dict) -> str:
    lines = [f"flowchart {v.get('direction') or 'TD'}"]
    classes: dict[str, list[str]] = {}
    for nd in v.get("nodes") or []:
        nid = "n_" + nd["id"]
        refs = nd.get("claims") or []
        lines.append(f'  {nid}["{_mq(nd.get("label", ""))}<br/><small>{" ".join(refs)}</small>"]')
        evs = [ix["claims"][r].get("evidence") for r in refs if r in ix["claims"]]
        w = weakest(evs) or "model-claim"
        classes.setdefault(w, []).append(nid)
    for e in v.get("edges") or []:
        a, b = "n_" + e["from"], "n_" + e["to"]
        if e.get("inferred"):
            iid = e.get("inference", "")
            tag = (ix["inferences"].get(iid) or {}).get("label", "INFERENCE")
            lab = " · ".join(x for x in [tag, e.get("label", ""), iid] if x)
            lines.append(f'  {a} -.->|"{_mq(lab)}"| {b}')
            continue
        refs = list(e.get("claims") or [])
        if e.get("relation") and e["relation"] in ix["relations"]:
            refs += [r for r in ix["relations"][e["relation"]].get("claims") or [] if r not in refs]
        # 종류(kind)는 연결 근거 표에 있으므로 그림 라벨은 짧게 — 라벨이 없을 때만 종류를 쓴다
        lab = " · ".join(x for x in [e.get("label") or e.get("kind", ""), " ".join(refs)] if x)
        arrow = "==>" if e.get("kind") == "causal" else "-->"
        lines.append(f'  {a} {arrow}|"{_mq(lab)}"| {b}')
    styles = {
        "verified": "fill:#e7f5ec,stroke:#2f855a",
        "supported": "fill:#e7f5ec,stroke:#2f855a",
        "model-claim": "fill:#f1f3f5,stroke:#868e96",
        "opinion": "fill:#f3f0ff,stroke:#7048e8",
        "inference": "fill:#fff4e6,stroke:#d9480f,stroke-dasharray:4 3",
        "uncertain": "fill:#fff9db,stroke:#e67700,stroke-dasharray:4 3",
        "source-needed": "fill:#fff0f0,stroke:#c92a2a",
        "conflicting": "fill:#ffe3e3,stroke:#c92a2a,stroke-width:3px",
    }
    for ev, ids in classes.items():
        cls = "ev_" + ev.replace("-", "_")
        lines.append(f"  classDef {cls} {styles.get(ev, '')}")
        lines.append(f"  class {','.join(ids)} {cls}")
    return "\n".join(lines)


def svg_for(v: dict, ix: dict) -> str:
    """설치·외부 요청 없는 기본 그래프. 배치는 의미 순서를 나타내지 않는다."""
    nodes = v.get("nodes") or []
    size = max(700, len(nodes) * 100)
    radius = size / 2 - 140
    centers = {n["id"]: (size/2 + radius * math.cos(2*math.pi*i/max(1,len(nodes))),
                           size/2 + radius * math.sin(2*math.pi*i/max(1,len(nodes))))
               for i,n in enumerate(nodes)}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" role="img" aria-label="{_html_escape(v.get("title", "관계 그림"))}">',
           '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#555"/></marker></defs>']
    for edge in v.get("edges") or []:
        x1,y1=centers[edge["from"]]; x2,y2=centers[edge["to"]]
        distance=math.hypot(x2-x1,y2-y1) or 1
        dx,dy=(x2-x1)/distance,(y2-y1)/distance
        dash=' stroke-dasharray="6 4"' if edge.get("inferred") else ''
        width=3 if edge.get("kind")=="causal" else 1.5
        refs=list(edge.get("claims") or [])
        if edge.get("relation") in ix["relations"]:
            refs += ix["relations"][edge["relation"]].get("claims") or []
        label=" · ".join([edge.get("label") or edge.get("kind", ""),
                           "INFERENCE " + edge.get("inference", "") if edge.get("inferred") else " ".join(dict.fromkeys(refs))])
        out.append(f'<line x1="{x1+dx*100}" y1="{y1+dy*45}" x2="{x2-dx*100}" y2="{y2-dy*45}" stroke="#555" stroke-width="{width}"{dash} marker-end="url(#arrow)"><title>{_html_escape(label)}</title></line>')
        out.append(f'<text x="{(x1+x2)/2}" y="{(y1+y2)/2}" font-size="11" fill="#333" stroke="white" stroke-width="3" paint-order="stroke" text-anchor="middle">{_html_escape(label)}</text>')
    for node in nodes:
        x,y=centers[node["id"]]
        state=weakest([ix["claims"][c].get("evidence") for c in node.get("claims", [])])
        color={"verified":"#e7f5ec","supported":"#e7f5ec","uncertain":"#fff9db","conflicting":"#ffe3e3","source-needed":"#fff0f0","opinion":"#f3f0ff","inference":"#fff4e6"}.get(state,"#f1f3f5")
        out.append(f'<g class="node" data-node-id="{_html_escape(node["id"])}" style="cursor:pointer"><rect x="{x-110}" y="{y-45}" width="220" height="90" rx="8" fill="{color}" stroke="#777"/>')
        for i,line in enumerate(textwrap.wrap(node.get("label", ""), width=20)[:2]):
            out.append(f'<text x="{x}" y="{y-18+i*19}" text-anchor="middle" font-size="14" fill="#222">{_html_escape(line)}</text>')
        out.append(f'<text x="{x}" y="{y+27}" text-anchor="middle" font-size="12" fill="#333">{_html_escape(" ".join(node.get("claims", [])))}</text></g>')
    return "".join(out) + '</svg>'


# ---------------------------------------------------------------- Markdown 조각

def loc_str(c: dict, units: dict) -> str:
    u = units.get(c.get("source_location"))
    if not u:
        return c.get("source_location", "?")
    ln = f"{u['line_start']}행" if u["line_start"] == u["line_end"] else f"{u['line_start']}–{u['line_end']}행"
    sec = f", §{u['section']}" if u.get("section") else ""
    img = f", 이미지 {u['origin'].split(':')[1]}에서 옮김" if u.get("origin") else ""
    return f"{u['id']} ({ln}{sec}{img})"


def claim_line(c: dict, units: dict, with_loc: bool = True) -> str:
    badge = EVIDENCE_LABEL_KO.get(c.get("evidence"), c.get("evidence"))
    types = "/".join(c.get("type") or [])
    s = f"- **{c['id']}** {c.get('text', '')}  \n  `{types}` · **[{badge}]** · confidence `{c.get('confidence')}`"
    if with_loc:
        s += f" · {loc_str(c, units)}"
    if c.get("conditions"):
        s += f"  \n  조건: {'; '.join(c['conditions'])}"
    if c.get("exceptions"):
        s += f"  \n  예외: {'; '.join(c['exceptions'])}"
    return s


def md_table(cols: list[str], rows: list[list[str]]) -> str:
    esc = lambda x: str(x).replace("|", "\\|").replace("\n", " ")  # noqa: E731
    out = ["| " + " | ".join(esc(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def build_sections(ir: dict, ix: dict, cnt: dict, review: list[dict], gates: dict, issues: Issues,
                   mermaids: dict) -> dict:
    units = ix["units"]
    claims = ir.get("claims") or []
    sec: dict[str, str] = {}

    sec["overview"] = md_table(
        ["항목", "개수", "뜻"],
        [
            ["총 Claim", cnt["total"], "원문에서 뽑은 주장 단위"],
            ["근거 제시됨", cnt["grounded"], "verified(외부 확인) + supported(원문이 출처·데이터를 제시 — 출처 내용 자체는 미확인)"],
            ["출처 확인 필요", cnt["source_needed"], "확인 가능한 사실·통계인데 출처 없음"],
            ["작성자 단언", cnt["model_claim"], "원문이 그렇게 말할 뿐 근거는 없음 (설계 결정·일반론 포함)"],
            ["Inference", cnt["inference"], f"원문 속 추론 {cnt['inference_in_source']} + 이 리포트가 덧붙인 해석 {cnt['inference_added']}"],
            ["의견·평가", cnt["opinion"], "가치 판단·권고"],
            ["불확실", cnt["uncertain"], "원문 스스로 유보"],
            ["충돌 가능성", cnt["conflicting"], "다른 Claim 또는 외부 확인과 양립 불가"],
        ],
    ) + "\n\n유형 분포: " + ", ".join(f"`{k}` {v}" for k, v in cnt["by_type"].items())

    # 요약
    if ir.get("summary"):
        lines = []
        for s in ir["summary"]:
            evs = [ix["claims"][r].get("evidence") for r in s.get("claims") or [] if r in ix["claims"]]
            w = weakest(evs)
            low = any(ix["claims"][r].get("confidence") == "low" for r in s.get("claims") or [] if r in ix["claims"])
            lines.append(f"- {s['text']} — {', '.join(s.get('claims') or [])} **[{EVIDENCE_LABEL_KO.get(w, w)}"
                         f"{' · 근거 약함' if low else ''}]**")
        sec["summary"] = "\n".join(lines)
    else:
        sec["summary"] = "_요약 없음_"

    # REVIEW FIRST
    if review:
        sec["review_first"] = "```text\nREVIEW FIRST\n\n" + "\n".join(
            f"{c['id']} — {review_reason(c)}" for c in review) + "\n```\n\n" + "\n".join(
            claim_line(c, units) + (f"  \n  ⚑ {c['review_note']}" if c.get("review_note") else "") for c in review)
    else:
        sec["review_first"] = "_우선 검토 기준(점수 50)을 넘는 Claim 이 없다._"

    core = [c for c in claims if c.get("importance") == "core"] or claims[: min(7, len(claims))]
    sec["core_claims"] = "\n".join(claim_line(c, units) for c in core)
    sec["all_claims"] = "\n".join(claim_line(c, units, with_loc=False) for c in claims)

    # 관계 구조 · 흐름
    struct, tables, anim = [], [], []
    vis_md: dict[str, str] = {}
    for v in ir.get("visuals") or []:
        k = v.get("kind")
        n_before = len(struct) + len(tables) + len(anim)
        if k == "diagram":
            edge_rows = []
            nodes = {n["id"]: n for n in v.get("nodes") or []}
            for e in v.get("edges") or []:
                refs = list(e.get("claims") or [])
                if e.get("relation") in ix["relations"]:
                    refs += ix["relations"][e["relation"]].get("claims") or []
                tag = (ix["inferences"].get(e.get("inference")) or {}).get("label", "INFERENCE")
                basis = (f"**{tag}** {e.get('inference')}" if e.get("inferred") else ", ".join(dict.fromkeys(refs)))
                edge_rows.append([nodes.get(e["from"], {}).get("label", e["from"]), e.get("kind", ""),
                                  e.get("label", ""), nodes.get(e["to"], {}).get("label", e["to"]), basis])
            struct.append(f"### {v['id']} · {v.get('title', '')}\n\n```mermaid\n{mermaids[v['id']]}\n```\n\n"
                          + "연결 근거 (그림을 못 읽어도 이 표로 검토할 수 있다):\n\n"
                          + md_table(["출발", "종류", "라벨", "도착", "근거"], edge_rows))
        elif k == "flow":
            steps = "\n".join(f"{i}. {s['text']} — {', '.join(s['claims'])}" for i, s in enumerate(v.get("steps") or [], 1))
            struct.append(f"### {v['id']} · {v.get('title', '')}\n\n{steps}")
        elif k == "table":
            rows = []
            for r in v.get("rows") or []:
                evs = [ix["claims"][x].get("evidence") for x in r.get("claims") or [] if x in ix["claims"]]
                rows.append(list(r.get("cells") or []) + [", ".join(r.get("claims") or []),
                                                          EVIDENCE_LABEL_KO.get(weakest(evs), "")])
            tables.append(f"### {v['id']} · {v.get('title', '')}\n\n"
                          + md_table(list(v.get("columns") or []) + ["Claim", "근거 상태"], rows))
        elif k == "animation":
            rows = [[i, s.get("caption", ""), s.get("motion", ""), s.get("seconds", ""), ", ".join(s.get("claims") or [])]
                    for i, s in enumerate(v.get("scenes") or [], 1)]
            anim.append(f"### {v['id']} · {v.get('title', '')} (애니메이션 후보 — 스토리보드)\n\n"
                        + md_table(["#", "자막(=내레이션)", "움직임", "초", "Claim"], rows))
        if len(struct) + len(tables) + len(anim) > n_before:
            vis_md[v["id"]] = {"diagram": struct, "flow": struct, "table": tables, "animation": anim}[k][-1]
    sec["structure"] = "\n\n".join(struct) or "_다이어그램·흐름 없음 — 관계·순서를 그림으로 보여야 할 Claim 이 없다 (routing-rules §2)._"
    sec["tables"] = "\n\n".join(tables) or "_비교·예외 표 없음._"
    sec["animation"] = "\n\n".join(anim) or "_애니메이션 후보 없음 — 정적 표현으로 충분하다._"

    sec["narrative"] = narrative_md(ir, ix, vis_md)

    # 추론
    inf_lines = []
    for c in claims:
        if c.get("evidence") == "inference":
            inf_lines.append(claim_line(c, units) + (f"  \n  전제: {', '.join(c['dependencies'])}" if c.get("dependencies") else ""))
    added = [f"- **{i['id']} · {i['label']}** {i['text']}  \n  근거: {', '.join(i['based_on'])} · 이유: {i['reason']}"
             for i in ir.get("inferences") or []]
    sec["inferences"] = ("**원문 작성자가 스스로 끌어낸 추론**\n\n" + ("\n".join(inf_lines) or "_없음_")
                         + "\n\n**이 리포트가 덧붙인 해석 (원문에 없음 — 점선으로 표시)**\n\n" + ("\n".join(added) or "_없음_"))

    # 원문 추적
    by_unit: dict[str, list[str]] = {}
    for c in claims:
        by_unit.setdefault(c.get("source_location"), []).append(c["id"])
    skipped = {s["unit"]: s["reason"] for s in (ir.get("coverage") or {}).get("skipped") or []}
    rows = []
    for u in ix["units"].values():
        if u["id"] in by_unit:
            rows.append([u["id"], f"{u['line_start']}–{u['line_end']}", u.get("section", ""), ", ".join(by_unit[u["id"]])])
        elif u["id"] in skipped:
            rows.append([u["id"], f"{u['line_start']}–{u['line_end']}", u.get("section", ""), f"_skip: {skipped[u['id']]}_"])
        elif u.get("kind") in CONTENT_UNIT_KINDS:
            rows.append([u["id"], f"{u['line_start']}–{u['line_end']}", u.get("section", ""), "—"])
    sec["trace"] = md_table(["원문 단위", "행", "섹션", "Claim"], rows)

    # inspect 전용
    by_flag: dict[str, list[dict]] = {}
    for c in claims:
        for f in c.get("flags") or []:
            if f != "compound-split":
                by_flag.setdefault(f, []).append(c)
    sec["issues_by_flag"] = "\n\n".join(
        f"### {FLAG_KO.get(f, f)} (`{f}`) — {len(cs)}개\n\n" + "\n".join(
            claim_line(c, units) + (f"  \n  ⚑ {c['review_note']}" if c.get("review_note") else "") for c in cs)
        for f, cs in sorted(by_flag.items(), key=lambda x: -len(x[1]))) or "_플래그가 붙은 Claim 이 없다._"
    conf = [c for c in claims if c.get("evidence") == "conflicting"]
    sec["conflicts"] = "\n".join(
        claim_line(c, units) + f"  \n  ↔ {', '.join(c.get('conflicts_with') or [])}"
        + (f" · 외부 확인: {c['verification'].get('reference')}" if c.get("verification") else "")
        for c in conf) or "_충돌 없음._"
    weak = [c for c in claims if c.get("evidence") in ("source-needed", "model-claim")
            and ({"fact", "quantitative", "causal"} & set(c.get("type") or []))]
    sec["unsupported"] = "\n".join(claim_line(c, units) for c in weak) or "_없음._"

    # 검증
    sec["gates"] = md_table(["Gate", "판정", "내용"], [
        ["G1", gates["G1"], "모든 핵심 주장에 Claim ID"],
        ["G2", gates["G2"], "시각 요소 ↔ Claim 연결"],
        ["G3", gates["G3"], "원문에 없는 사실 생성 없음"],
        ["G4", gates["G4"], "Fact / Inference 구분"],
        ["G5", gates["G5"], "불확실성 표시"],
        ["G6", gates["G6"], "원문으로 돌아갈 수 있음"],
    ])
    w = issues.warnings
    sec["warnings"] = ("\n".join(f"- `{i['gate']}` {i['where']}: {i['msg']}" for i in w)
                       if w else "_경고 없음._")
    return sec


SENT_MARK = {"source-needed": "⚠출처 필요", "conflicting": "⚠충돌", "uncertain": "~불확실",
             "inference": "~추론", "opinion": "의견"}


def _sent_md(s: dict, ix: dict) -> str:
    refs = s.get("claims") or []
    evs = [ix["claims"][r].get("evidence") for r in refs if r in ix["claims"]]
    w = weakest(evs)
    tags = []
    if refs:
        tags.append(", ".join(refs))
    if s.get("context"):
        tags.append("배경 " + ", ".join(s["context"]))
    if s.get("inferences"):
        tags.append("해석 " + ", ".join(s["inferences"]))
    mark = SENT_MARK.get(w or "", "")
    return f"{s.get('text', '')}<sup>[{' · '.join(tags)}{' · ' + mark if mark else ''}]</sup>"


def narrative_md(ir: dict, ix: dict, vis_md: dict) -> str:
    nar = ir.get("narrative")
    if not nar:
        return "_읽기 페이지(narrative)가 없다 — inspect 모드는 생략할 수 있다._"
    out = []
    if nar.get("headline"):
        out.append("> **" + _sent_md(nar["headline"], ix) + "**")
    for sec in nar.get("sections") or []:
        out.append(f"### {sec.get('title', '')}")
        for b in sec.get("blocks") or []:
            if b.get("kind") == "text":
                out.append(" ".join(_sent_md(s, ix) for s in b.get("sentences") or []))
            elif b.get("kind") == "points":
                out.append("\n".join("- " + _sent_md(s, ix) for s in b.get("sentences") or []))
            elif b.get("kind") == "callout":
                out.append("> **핵심** — " + " ".join(_sent_md(s, ix) for s in b.get("sentences") or []))
            elif b.get("kind") == "example":
                lines = [f"**{b.get('label', '예시')}**", ""]
                for it in b.get("items") or []:
                    tag = ", ".join(it.get("claims") or []) or ("배경 " + ", ".join(it.get("context") or []))
                    lines.append(f"- {('*' + it['label'] + '* ') if it.get('label') else ''}`{it.get('quote', '')}` <sup>[{tag}]</sup>")
                out.append("\n".join(lines))
            elif b.get("kind") == "visual":
                body = vis_md.get(b.get("ref"), f"_({b.get('ref')})_")
                body = re.sub(r"^### .*\n\n", "", body)
                out.append((f"*{b['caption']}*\n\n" if b.get("caption") else "") + body)
    ctx = ir.get("context") or []
    if ctx:
        out.append("#### 배경 설명 — 원문 밖 (CONTEXT · AI가 덧붙임" + (")" if any(k.get("reference") for k in ctx) else " · 외부 확인 안 함)"))
        out.append("\n".join(f"- **{k['id']} {k['term']}** — {k['text']}" + (f" ({k['reference']})" if k.get("reference") else "")
                             for k in ctx))
    out.append("<sub>문장 끝 [C..]는 근거 Claim, [배경 K..]는 원문 밖 설명. ⚠출처 필요·~불확실·~추론·의견 표시는 근거 중 가장 약한 상태.</sub>")
    return "\n\n".join(out)


def fill(template: str, values: dict) -> str:
    def rep(m: re.Match) -> str:
        return str(values.get(m.group(1), m.group(0)))
    return re.sub(r"\{\{(\w+)\}\}", rep, template)


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ir")
    ap.add_argument("--mode", choices=["understand", "inspect", "visualize"], default=None)
    ap.add_argument("--out", default=None, help="기본: IR 과 같은 폴더")
    args = ap.parse_args()

    ir_path = Path(args.ir)
    ir = load_ir(ir_path)
    mode = args.mode or (ir.get("meta") or {}).get("mode") or "understand"

    ir.setdefault("meta", {})["mode"] = mode
    issues = Issues()
    issues.extend(_load("validate-claims").check(ir))
    issues.extend(_load("validate-traceability").check(ir))
    gates = issues.gates()
    issues.print_human("build-report: Hard Gate")
    if issues.errors:
        emit({"ok": False, "gates": gates, "errors": issues.errors,
              "msg": "Hard Gate FAIL — 산출물을 쓰지 않았다. IR 을 고친 뒤 다시 실행한다."})
        sys.exit(1)

    out = (Path(args.out) if args.out else ir_path.parent).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # 기존 산출물의 심링크를 따라 작업 폴더 밖에 쓰지 않는다.
    targets = [out / name for name in ("report.md", "viewer.html", "gate-report.json", "diagrams")]
    targets += [out / "diagrams" / (v["id"] + suffix)
                for v in ir.get("visuals") or [] if v.get("kind") == "diagram"
                for suffix in (".mmd", ".svg")]
    if any(target.is_symlink() or not target.resolve().is_relative_to(out) for target in targets):
        sys.exit("산출 경로에 심링크 또는 작업 폴더 밖으로 향하는 경로가 있다. 안전한 출력 폴더를 사용한다.")
    ix = index(ir)
    cnt = counts(ir)

    scored = sorted(((score(c), c) for c in ir["claims"]), key=lambda x: (-x[0], x[1]["id"]))
    review = [c for s, c in scored if s >= REVIEW_THRESHOLD][:REVIEW_MAX]

    mermaids = {v["id"]: mermaid_for(v, ix) for v in ir.get("visuals") or [] if v.get("kind") == "diagram"}
    if mermaids:
        (out / "diagrams").mkdir(exist_ok=True)
        for vid, code in mermaids.items():
            (out / "diagrams" / f"{vid}.mmd").write_text(code + "\n", encoding="utf-8")
            visual = next(v for v in ir["visuals"] if v["id"] == vid)
            (out / "diagrams" / f"{vid}.svg").write_text(svg_for(visual, ix), encoding="utf-8")

    sec = build_sections(ir, ix, cnt, review, gates, issues, mermaids)
    meta = ir.get("meta") or {}
    values = {
        **sec,
        "title": meta.get("title", ""),
        "mode": mode,
        "source_path": meta.get("source_path", ""),
        "created": meta.get("created") or dt.date.today().isoformat(),
        "external_verification": "기록 있음 (실제 수행 여부는 자동 검증하지 않음)" if meta.get("external_verification") else "수행하지 않음 — verified Claim 없음, confidence 기본값 unknown",
        "total": cnt["total"],
    }
    tpl_name = "inspect-report.md" if mode == "inspect" else "understanding-report.md"
    validation = review_status(ir)
    report = fill((TEMPLATES / tpl_name).read_text(encoding="utf-8"), values)
    report = "> ASD-STE100 참고 작성 · 공식 준수 미검증\n> " + validation["scope"] + "\n\n" + "검토 상태: " + json.dumps(validation["semantic"], ensure_ascii=False) + "\n\n" + validation["review_origin"] + " · " + validation["external"]["note"] + "\n\n" + report
    (out / "report.md").write_text(report, encoding="utf-8")

    # viewer.html
    payload = {
        "meta": {**meta, "mode": mode},
        "counts": cnt,
        "units": list(ix["units"].values()),
        "claims": [{**c, "_score": score(c), "_loc": loc_str(c, ix["units"])} for c in ir["claims"]],
        "entities": ir.get("entities") or [],
        "inferences": ir.get("inferences") or [],
        "visuals": [{**v, "_mermaid": mermaids.get(v["id"]), "_svg": svg_for(v, ix) if v.get("kind") == "diagram" else None} for v in ir.get("visuals") or []],
        "summary": [{**s, "_weakest": weakest([ix["claims"][r].get("evidence") for r in s.get("claims") or [] if r in ix["claims"]]),
                     "_low": any(ix["claims"][r].get("confidence") == "low" for r in s.get("claims") or [] if r in ix["claims"])}
                    for s in ir.get("summary") or []],
        "review": [{"id": c["id"], "reason": review_reason(c)} for c in review],
        "narrative": _annotate_narrative(ir.get("narrative"), ix),
        "context": ir.get("context") or [],
        "skipped": (ir.get("coverage") or {}).get("skipped") or [],
        "validation": validation,
        "explanation_plan": ir.get("explanation_plan"),
        "gates": gates,
        "warnings": issues.warnings,
        "labels": {"evidence": EVIDENCE_LABEL_KO, "flags": FLAG_KO},
    }
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    viewer = (TEMPLATES / "viewer.html").read_text(encoding="utf-8")
    # 제목을 먼저 넣는다 — IR 데이터 안에 우연히 "{{title}}" 문자열이 있어도 건드리지 않도록.
    viewer = viewer.replace("{{title}}", _html_escape(meta.get("title", ""))).replace("/*__IR_JSON__*/null", data)
    # 사용자 데이터가 들어간 스크립트를 포함해 정확한 바이트의 해시만 실행 허용한다.
    hashes = ["'sha256-" + base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii") + "'"
              for script in re.findall(r"<script>(.*?)</script>", viewer, re.S)]
    policy = "default-src 'none'; script-src " + " ".join(hashes) + "; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-src 'none'; worker-src 'none'; media-src 'none'; manifest-src 'none'"
    viewer = viewer.replace("{{csp}}", _html_escape(policy))
    (out / "viewer.html").write_text(viewer, encoding="utf-8")

    gate_report = {"validation": validation, "ok": True, "mode": mode, "gates": gates, "counts": cnt,
                   "review_first": payload["review"], "warnings": issues.warnings,
                   "built": dt.datetime.now().isoformat(timespec="seconds")}
    (out / "gate-report.json").write_text(json.dumps(gate_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    emit({"ok": True, "mode": mode, "gates": gates,
          "files": [str(out / "report.md"), str(out / "viewer.html"), str(out / "gate-report.json")]
          + [str(out / "diagrams" / f"{v}.mmd") for v in mermaids],
          "first_screen": {"총 Claim": cnt["total"], "근거 제시됨": cnt["grounded"], "출처 확인 필요": cnt["source_needed"],
                           "작성자 단언": cnt["model_claim"],
                           "Inference": f'{cnt["inference"]} (원문 속 {cnt["inference_in_source"]} + 덧붙인 해석 {cnt["inference_added"]})',
                           "의견·평가": cnt["opinion"],
                           "불확실": cnt["uncertain"], "충돌 가능성": cnt["conflicting"]},
          "review_first": payload["review"][:7], "warnings": len(issues.warnings)})


def _annotate_narrative(nar: dict | None, ix: dict) -> dict | None:
    if not nar:
        return None

    def ann(s: dict) -> dict:
        refs = [r for r in s.get("claims") or [] if r in ix["claims"]]
        return {**s, "_weakest": weakest([ix["claims"][r].get("evidence") for r in refs]),
                "_low": any(ix["claims"][r].get("confidence") == "low" for r in refs)}

    return {
        "headline": ann(nar["headline"]) if nar.get("headline") else None,
        "sections": [{**sec, "blocks": [{**b, "sentences": [ann(s) for s in b.get("sentences") or []]}
                                        if b.get("kind") in ("text", "points", "callout") else b for b in sec.get("blocks") or []]}
                     for sec in nar.get("sections") or []],
    }


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


if __name__ == "__main__":
    main()
