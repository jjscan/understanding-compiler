"""Understanding Compiler 공용 유틸. 표준 라이브러리만 사용한다."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path

CLAIM_TYPES = {
    "fact", "definition", "procedure", "relationship", "comparison", "temporal",
    "causal", "conditional", "quantitative", "opinion", "prediction", "uncertain",
}
EVIDENCE = [
    "verified", "supported", "source-needed", "model-claim",
    "inference", "opinion", "uncertain", "conflicting",
]
CONFIDENCE = {"unknown", "low", "medium", "high"}
VISUALIZATION = {"text", "flow", "diagram", "table", "animation"}
IMPORTANCE = {"core", "supporting", "detail"}
RISK = {"low", "medium", "high"}
FLAGS = {
    "unsupported", "overgeneralization", "vague", "fact-inference-mix", "naming-drift",
    "missing-condition", "number-unclear", "hedge-dropped-in-source", "compound-split", "outdated-risk",
    "overclaim",
}
EDGE_KINDS = {
    "contains", "sequence", "causal", "dependency", "data-flow",
    "delegation", "association", "comparison", "conditional",
}
# 엣지 종류를 뒷받침하는 Claim 유형 (traceability-rules.md §2)
EDGE_BACKING = {
    "causal": {"causal"},
    "sequence": {"procedure", "temporal"},
    "contains": {"relationship", "definition"},
    "comparison": {"comparison"},
    "conditional": {"conditional"},
    "dependency": {"relationship", "procedure", "causal", "conditional", "definition"},
    "data-flow": {"relationship", "procedure", "causal", "conditional", "definition"},
    "delegation": {"relationship", "procedure", "causal", "conditional", "definition"},
    "association": {"relationship", "procedure", "causal", "conditional", "definition"},
}
# 약한 근거 → 강한 근거 (요약 배지는 가장 약한 것을 쓴다)
EVIDENCE_STRENGTH = [
    "conflicting", "source-needed", "uncertain", "inference",
    "model-claim", "opinion", "supported", "verified",
]
EVIDENCE_LABEL_KO = {
    "verified": "외부 확인됨",
    "supported": "출처·데이터 제시됨",
    "source-needed": "출처 확인 필요",
    "model-claim": "작성자 단언",
    "inference": "원문 속 추론",
    "opinion": "의견·평가",
    "uncertain": "불확실",
    "conflicting": "충돌",
}
CONTENT_UNIT_KINDS = {"paragraph", "list-item", "table-row", "quote"}

# 원문의 유보 표현. "~할 수 있다"(능력)는 오탐이 많아 넣지 않는다.
HEDGE_PATTERNS = [
    r"아마", r"추정", r"것\s?같", r"가능성", r"예상", r"보인다", r"보임", r"듯",
    r"일\s?수\s?있", r"을\s?수도", r"ㄹ\s?수도", r"수도\s?있", r"짐작", r"추측", r"대략", r"약\s?\d",
    r"\bmay\b", r"\bmight\b", r"\blikely\b", r"\bprobably\b", r"\bperhaps\b",
    r"\bpossibly\b", r"\bcould\b", r"\bseems?\b", r"\bappears?\b", r"\bestimated?\b", r"\bapprox",
]
PRONOUN_START = re.compile(r"^(이것|그것|저것|이는|이를|그는|그것은|이들|그들|it|this|that|they|these|those)(\s|은|는|이|가|을|를|$)", re.I)
COMPOUND_HINT = re.compile(r"(하고|하며|이며|이고|그리고|때문에|므로|으로써|\band\b|\bbecause\b|\bso\b)")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
# 요약·표 문장에서 인과를 새로 만드는 접속 표현
CAUSAL_CONNECTIVE = re.compile(r"(그 결과(?![를을이가의는와로])|결과적으로|때문에|덕분에|로 인해|으로 인해|따라서|그러므로|그래서|므로|탓에|\btherefore\b|\bthus\b|\bhence\b|\bbecause\b|\bso that\b|\bleads? to\b|\bresults? in\b)", re.I)


class Issues:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def error(self, gate: str, where: str, msg: str) -> None:
        self.items.append({"level": "error", "gate": gate, "where": where, "msg": msg})

    def warn(self, gate: str, where: str, msg: str) -> None:
        self.items.append({"level": "warning", "gate": gate, "where": where, "msg": msg})

    @property
    def errors(self) -> list[dict]:
        return [i for i in self.items if i["level"] == "error"]

    @property
    def warnings(self) -> list[dict]:
        return [i for i in self.items if i["level"] == "warning"]

    def extend(self, other: "Issues") -> None:
        self.items.extend(other.items)

    def gates(self) -> dict:
        out = {}
        for g in ["G1", "G2", "G3", "G4", "G5", "G6"]:
            errs = [i for i in self.errors if i["gate"] == g]
            out[g] = "FAIL" if errs else "PASS"
        return out

    def print_human(self, title: str) -> None:
        print(f"== {title} ==", file=sys.stderr)
        for i in self.items:
            mark = "ERROR" if i["level"] == "error" else "warn "
            print(f"  [{mark}] {i['gate']} {i['where']}: {i['msg']}", file=sys.stderr)
        print(f"  → error {len(self.errors)} / warning {len(self.warnings)}", file=sys.stderr)


def load_ir(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f"IR 파일이 없다: {p}")
    try:
        ir = json.loads(p.read_text(encoding="utf-8"))
        ir["_ir_path"] = str(p.resolve())
        return ir
    except json.JSONDecodeError as e:
        sys.exit(f"IR JSON 파싱 실패: {p}:{e.lineno}:{e.colno} {e.msg}")


def norm(s: str) -> str:
    """원문 대조용 정규화: NFC, 따옴표 통일, 마크다운 강조 기호 제거, 공백 압축."""
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[*_`]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# 한국어 조사가 바로 붙어도("C14과", "P08의") ID 로 인식하도록 \b 대신 영숫자 경계를 쓴다.
ID_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])[CPEIRVS]\d{2,}(?!\d)")


def numbers(s: str) -> set[str]:
    """숫자 집합. C01·P03 같은 IR ID 는 숫자로 세지 않는다."""
    t = ID_TOKEN_RE.sub(" ", norm(s))
    return {n.replace(",", "") for n in NUM_RE.findall(t)}


# 숫자가 섞인 고유 이름(ASD-STE100, 3b1b, GPT-4o). 대명사를 이름으로 바꿔 쓰면 원문 구간엔 없는 숫자가 생기므로,
# 원문 어딘가에 같은 이름이 그대로 있으면 숫자 검사에서 뺀다. (v0.4 → v0.5 처럼 원문에 없는 이름은 그대로 걸린다.)
IDENT_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)*\d[A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)*|\d+[A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)*")


def strip_known_identifiers(text: str, source_all: str) -> str:
    src = norm(source_all)
    return IDENT_RE.sub(lambda m: " " if m.group(0) in src else m.group(0), norm(text))


def claim_ids_in(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z0-9])C\d{2,}(?!\d)", text or "")


def unit_ids_in(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z0-9])P\d{2,}(?!\d)", text or "")


def source_numbers(ir: dict) -> set[str]:
    """원문 전체의 숫자 — 리뷰 메모·제목처럼 문서의 다른 부분을 가리키는 문장의 기준."""
    return numbers(" ".join(u.get("text", "") for u in (ir.get("source") or {}).get("units") or []))


def has_hedge(s: str, loose: bool = False) -> bool:
    """유보 표현이 있는가. loose=True 면 "~ㄹ 수 있다"(능력/가능성 모호)도 유보로 센다 —
    '원문엔 있었는데 사라졌는가'를 볼 때는 넓게 잡아야 놓치지 않는다."""
    t = norm(s)
    pats = HEDGE_PATTERNS + ([r"수\s?있"] if loose else [])
    return any(re.search(p, t, re.I) for p in pats)


def word_count(s: str) -> int:
    return len(norm(s).split(" "))


def sentence_count(s: str) -> int:
    t = re.sub(r"\d\.\d", "0", norm(s))
    parts = [p for p in re.split(r"(?<=[.?!。])\s+", t) if p.strip()]
    return len(parts)


def weakest(evidences: list[str]) -> str | None:
    ranked = [e for e in EVIDENCE_STRENGTH if e in evidences]
    return ranked[0] if ranked else None


def index(ir: dict) -> dict:
    """ID → 객체 맵 모음."""
    return {
        "units": {u.get("id"): u for u in ir.get("source", {}).get("units", [])},
        "claims": {c.get("id"): c for c in ir.get("claims", [])},
        "entities": {e.get("id"): e for e in ir.get("entities", []) or []},
        "inferences": {i.get("id"): i for i in ir.get("inferences", []) or []},
        "relations": {r.get("id"): r for r in ir.get("relations", []) or []},
    }


# 한국어 조사·어미 일부. 라벨 토큰 끝에서 떼어 내고 비교한다.
_PARTICLE_RE = re.compile(r"(으로|에서|에게|까지|부터|이다|이며|이고|은|는|이|가|을|를|의|와|과|로|에|도|만)$")


def _tokens(s: str) -> list[str]:
    out = []
    for t in re.split(r"[\s/·,()\[\]\-:]+", norm(s).lower()):
        t = _PARTICLE_RE.sub("", t) if len(t) > 2 else t
        if len(t) >= 2:
            out.append(t)
    return out


def label_mentioned(label: str, texts: list[str], aliases: list[str] | None = None) -> bool:
    """노드 라벨(또는 alias)이 근거 문장 중 하나에 등장하는가.
    라벨 전체가 들어 있거나, 같은 문장 안에 라벨 토큰(조사 제거)의 절반 이상이 나오면 인정한다."""
    hay = [norm(t).lower() for t in texts]
    for c in [label] + (aliases or []):
        key = norm(c).lower().replace(" ", "")
        if not key:
            continue
        if any(key in h.replace(" ", "") for h in hay):
            return True
        toks = _tokens(c)
        if not toks:
            continue
        need = max(1, -(-len(toks) // 2))  # ceil(n/2)
        if any(sum(1 for t in toks if t in h) >= need for h in hay):
            return True
    return False


def emit(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def entity_aliases(ix: dict, node: dict) -> list[str]:
    ent = ix["entities"].get(node.get("entity")) if node.get("entity") else None
    return ([ent.get("name", "")] + list(ent.get("aliases") or [])) if ent else []


SUMMARY_HEDGE_MARKERS = re.compile(r"(양립하지|모순|불확실|근거가? (없|제시되지)|확인되지 않|출처가? 없|미정|논쟁|uncertain|unclear)", re.I)

# 한국어 수 단어 + 단위("다섯 가지", "일곱 단계"). "한/하나"는 관형 표현과 구별이 안 돼 제외한다.
KO_NUM = {"두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
KO_COUNT_RE = re.compile(r"(?<![가-힣])(두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)\s?(가지|개|단계|명|곳|번|종류|축|층|부분|항목)")


def ko_counts(s: str) -> set[str]:
    return {str(KO_NUM[m.group(1)]) for m in KO_COUNT_RE.finditer(norm(s))}


# 비교 우열 표현 — 근거에 comparison Claim 이 있어야 쓸 수 있다
COMPARATIVE_RE = re.compile(r"(보다\s?(더|덜)?\s?\S*?(낫|좋|크|작|빠르|느리|중요|많|적|높|낮|쉽|어렵|강하|약하)|반면|더 낫|\bbetter than\b|\bworse than\b)")

# 의견·예측·추론을 누구의 것인지 밝히는 표현
ATTRIBUTION_RE = re.compile(r"(라고|다고|자고|냐고|에 따르면|에 의하면|의 (전망|평가|주장|예측|해석|견해|권고|결론)|작성자|저자|필자|답변은|보고서는|문서는|게시물[은에의]|원문[은에의]|그는|그녀는|그들은|본다|권한다|권고한다|느낀다|평가한다|예측한다|전망한다|주장한다|추정한다|해석한다|말한다|설명한다|밝힌다|적는다|보고한다|소개한다|제안한다|꼽는다|낙관|기대한다|추천한다|강조한다|결론짓는다|단언한다)")


REVIEW_STATES = {"not-reviewed", "needs-revision", "reviewed"}
NARRATIVE_DEPTHS = {"quick", "standard", "deep"}
VALIDATION_SCOPE = "구조·참조 검사 통과. 의미 정확성・주장 누락・외부 사실의 참 여부를 보장하지 않음."


def check_source(ir: dict) -> Issues:
    """실제 파일을 같은 분절기로 재분절해 IR 단위와 대조한다."""
    iss = Issues()
    base = Path(ir.get("_ir_path", "claim-ir.json")).parent
    source = Path((ir.get("meta") or {}).get("source_path") or "source.md")
    # source_path는 작업 폴더 내부 파일만 허용한다. 심링크로 나가는 것도 차단한다.
    source = (source if source.is_absolute() else base / source).resolve()
    base = base.resolve()
    if not source.is_relative_to(base):
        iss.error("G6", "source", "source_path가 IR 작업 폴더 밖을 가리킨다. 승인된 원문을 작업 폴더에 복사한다")
        return iss
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        iss.error("G6", "source", f"실제 원문 파일을 읽을 수 없다: {source}: {exc}")
        return iss
    spec = importlib.util.spec_from_file_location("uc_segment", Path(__file__).with_name("segment-source.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = module.segment(text.splitlines())
    actual = (ir.get("source") or {}).get("units") or []
    if expected != actual:
        iss.error("G6", "source.units", "실제 source 파일의 분절 결과와 IR이 다르다 (텍스트·행 번호·단위 순서·메타데이터). 원문에서 다시 분절한다")
    return iss


def review_status(ir: dict) -> dict:
    reviews = ir.get("reviews") or {}
    return {
        "scope": VALIDATION_SCOPE,
        "writing": {"profile": "ASD-STE100-inspired", "formal_compliance": "not-assessed",
                    "dictionary": "not-validated", "word_count": "heuristic",
                    "note": "카파시의 완화된 STE 제안 적용. 한국어는 명료성 원칙의 적용이며 공식 STE 영어 준수가 아님"},
        "semantic": {stage: (reviews.get(stage) or {}).get("status", "not-reviewed")
                     for stage in ("source_to_claim", "claim_to_narrative", "coverage", "reader_flow")},
        "review_origin": "작성자가 기록한 검토 상태이며 자동 의미 검증 결과가 아님",
        "external": {"status": "recorded-unverified" if any(c.get("verification") for c in ir.get("claims", [])) else "not-performed",
                     "note": "외부 확인 기록의 형식만 검사하며 실제 조회 수행·출처의 진위는 보장하지 않음"},
    }


STE_ADVISORY_WORDS = {"utilize": "use", "commence": "start", "prior to": "before", "in order to": "to"}


def check_ste_style(iss: Issues, where: str, text: str, procedural: bool = False,
                    entities: list[dict] | None = None) -> None:
    """STE 참고 편집 검사. 공식 사전·품사·단어 계수·의미 검증이 아닌 휴리스틱."""
    if not text:
        return
    korean = bool(re.search(r"[가-힣]", text))
    limit = 20 if procedural else 25
    for sentence in re.split(r"(?<=[.!?。])\s+", norm(text)):
        count = word_count(sentence)
        if count > limit:
            unit = "어절(한국어 적용 지침)" if korean else "공백 단위(공식 STE 단어 계수 아님)"
            iss.warn("G1", where, f"STE 참고: {'절차' if procedural else '설명'} 문장이 {count}{unit}이다 ({limit} 이하 권장)")
    if PRONOUN_START.match(norm(text)):
        iss.warn("G3", where, "STE 참고: 대명사의 대상이 명확한지 확인하고 필요한 경우 원문에 있는 대상 이름을 쓴다")
    if not korean:
        for phrase, alternative in STE_ADVISORY_WORDS.items():
            if re.search(r"\b" + re.escape(phrase) + r"\b", text, re.I):
                iss.warn("G1", where, f"STE 참고: '{phrase}'를 '{alternative}'로 바꿔도 원문의 의미가 유지되는지 검토한다 (공식 사전 판정 아님)")
        if procedural and re.search(r"\b(?:is|are|was|were|be|been)\s+(?:\w+ed|written|given|done|made|shown)\b", text, re.I):
            iss.warn("G1", where, "STE 참고: 절차의 수동태 후보다. 원문에 행위자가 있을 때만 능동 표현으로 바꾼다")
    for entity in entities or []:
        name = entity.get("name", "")
        for alias in entity.get("aliases") or []:
            if norm(alias).lower() == norm(name).lower():
                continue
            if re.search(r"(?<![A-Za-z0-9_])" + re.escape(alias) + r"(?![A-Za-z0-9_])", text, re.I) and name.lower() not in text.lower():
                iss.warn("G3", where, f"STE 참고: '{alias}'와 대표 이름 '{name}'의 용어 일관성을 검토한다")
