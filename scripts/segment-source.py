#!/usr/bin/env python3
"""[0] 원문 고정·분절.

source.md 를 문단·목록 항목·표 행·인용·제목·코드 단위로 나누고 P01, P02… ID를 붙여
같은 폴더에 claim-ir.json 골격을 만든다. 원문은 수정하지 않는다.

사용:
  python3 segment-source.py understanding/<slug>/source.md [--mode understand|inspect|visualize]
                            [--kind design-doc|research-report|ai-answer|other] [--title "..."] [--force]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from uc_common import emit  # noqa: E402

LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def segment(lines: list[str]) -> list[dict]:
    units: list[dict] = []
    section = ""
    origin = "text"          # "[이미지 N] …" 제목 아래 단위는 이미지에서 옮겨 적은 것
    origin_level = 0
    i = 0
    n = len(lines)

    def add(kind: str, start: int, end: int, text: str, **extra) -> None:
        text = text.strip()
        if not text:
            return
        units.append({
            "id": "",
            "kind": kind,
            "text": text,
            "line_start": start + 1,
            "line_end": end + 1,
            "section": section,
            **({"origin": origin} if origin != "text" else {}),
            **extra,
        })

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # 코드 블록
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = stripped[:3]
            j = i + 1
            while j < n and not lines[j].strip().startswith(fence):
                j += 1
            add("code", i, min(j, n - 1), "\n".join(lines[i:j + 1]))
            i = j + 1
            continue

        # 제목
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            section = m.group(2).strip()
            level = len(m.group(1))
            im = re.match(r"^\[(이미지|image)\s*(\d+)", section, re.I)
            if im:
                origin, origin_level = f"image:{im.group(2)}", level
            elif origin != "text" and level <= origin_level:
                origin = "text"
            add("heading", i, i, section)
            i += 1
            continue

        # 수평선
        if re.match(r"^([-*_])\s*(\1\s*){2,}$", stripped):
            i += 1
            continue

        # 표: 행마다 단위, 구분선 행은 건너뜀
        if stripped.startswith("|"):
            while i < n and lines[i].strip().startswith("|"):
                if not TABLE_SEP_RE.match(lines[i]):
                    add("table-row", i, i, lines[i].strip())
                i += 1
            continue

        # 인용
        if stripped.startswith(">"):
            j = i
            buf = []
            while j < n and lines[j].strip().startswith(">"):
                buf.append(lines[j].strip().lstrip(">").strip())
                j += 1
            add("quote", i, j - 1, " ".join(buf))
            i = j
            continue

        # 목록 항목(들여쓴 이어지는 줄 포함)
        m = LIST_RE.match(line)
        if m:
            indent = len(m.group(1))
            buf = [m.group(3)]
            j = i + 1
            while j < n:
                nxt = lines[j]
                if not nxt.strip():
                    break
                if LIST_RE.match(nxt) or nxt.strip().startswith(("#", "|", ">", "```")):
                    break
                if len(nxt) - len(nxt.lstrip()) > indent:
                    buf.append(nxt.strip())
                    j += 1
                    continue
                break
            marker = m.group(2)
            if marker[0].isdigit():
                add("list-item", i, j - 1, " ".join(buf), ordered=True, index=int(marker[:-1]))
            else:
                add("list-item", i, j - 1, " ".join(buf), ordered=False)
            i = j
            continue

        # 문단
        j = i
        buf = []
        while j < n:
            nxt = lines[j]
            s = nxt.strip()
            if not s or s.startswith(("#", "|", ">", "```", "~~~")) or LIST_RE.match(nxt):
                break
            buf.append(s)
            j += 1
        add("paragraph", i, j - 1, " ".join(buf))
        i = j

    width = max(2, len(str(len(units))))
    for k, u in enumerate(units, 1):
        u["id"] = f"P{k:0{width}d}"
    return units


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--mode", default="understand", choices=["understand", "inspect", "visualize"])
    ap.add_argument("--kind", default="other", choices=["design-doc", "research-report", "ai-answer", "other"])
    ap.add_argument("--title", default=None)
    ap.add_argument("--out", default=None, help="기본: source 와 같은 폴더의 claim-ir.json")
    ap.add_argument("--force", action="store_true", help="기존 claim-ir.json 을 덮어쓴다(작업 내용이 사라진다)")
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        sys.exit(f"원문 파일이 없다: {src}")
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()
    units = segment(lines)

    out = Path(args.out) if args.out else src.parent / "claim-ir.json"
    if not src.resolve().is_relative_to(out.resolve().parent):
        sys.exit("원문은 IR 작업 폴더 내부에 있어야 한다. 원문을 출력 폴더에 먼저 복사한다.")
    if out.exists() and not args.force:
        sys.exit(f"{out} 가 이미 있다. 작업한 Claim이 사라지지 않도록 멈춘다. 다시 만들려면 --force.")

    title = args.title
    if not title:
        first_heading = next((u["text"] for u in units if u["kind"] == "heading"), None)
        title = first_heading or src.stem

    ir = {
        "version": "1.0",
        "meta": {
            "title": title,
            "mode": args.mode,
            "source_path": str(src.resolve().relative_to(out.resolve().parent)),
            "source_kind": args.kind,
            "created": dt.date.today().isoformat(),
            "external_verification": False,
        },
        "source": {"units": units},
        "coverage": {"skipped": []},
        "entities": [],
        "claims": [],
        "relations": [],
        "inferences": [],
        "visuals": [],
        "summary": [],
    }
    out.write_text(json.dumps(ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    kinds: dict[str, int] = {}
    for u in units:
        kinds[u["kind"]] = kinds.get(u["kind"], 0) + 1
    emit({"ok": True, "out": str(out), "units": len(units), "by_kind": kinds,
          "next": "claims[] 를 채운 뒤 validate-claims.py 실행"})


if __name__ == "__main__":
    main()
