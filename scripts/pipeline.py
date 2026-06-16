#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
허깅페이스 Daily Papers 요약·인포그래픽 파이프라인 오케스트레이터.

서브커맨드
  fetch  [--date YYYY-MM-DD] [--top N]   최신 날짜 논문 수집·선정·PDF 다운로드 → days/<date>/papers.json
  build  <date>                          papers.json + 템플릿 → 일자별 페이지 + manifest.json 갱신(추가만)
  deploy [date]                          git add/commit/push → GitHub Pages 배포

요약(summary)과 인포그래픽 이미지는 Claude + gpt-image 단계에서 papers.json에 채워지며,
이 스크립트는 그 사이의 결정론적 작업(수집/선정/다운로드/렌더/배포)만 담당한다.
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import requests

# Windows 콘솔(cp949)에서도 한글/특수문자 출력이 깨지거나 크래시하지 않도록 UTF-8 고정
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

# ---------------------------------------------------------------------------
# 경로 / 상수
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent          # 저장소 루트
DATA_DIR = ROOT / "data"
DAYS_DIR = ROOT / "days"
TEMPLATES_DIR = ROOT / "templates"
MANIFEST_PATH = DATA_DIR / "manifest.json"

HF_API = "https://huggingface.co/api/daily_papers"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 AI-daily-papers/1.0"
)
HEADERS = {"User-Agent": USER_AGENT}

DEFAULT_TOP_N = 10
HARD_CAP = 15  # 우선 토픽 논문이 많아도 하루 처리량 상한

# 토픽 자동 태깅 (제목 + 초록 + ai_keywords 를 소문자로 매칭)
TOPIC_PATTERNS = {
    "MCP": [r"\bmcp\b", r"model context protocol"],
    "Orchestration": [r"multi[- ]?agent", r"orchestrat", r"agent\s+orchestration"],
    "Agentic AI": [r"agentic", r"autonomous agent", r"\bllm[- ]?agents?\b",
                   r"\bai[- ]?agents?\b", r"\bagents?\b"],
    "Ontology": [r"ontolog", r"knowledge graph"],
}


def log(msg: str) -> None:
    print(f"[pipeline] {msg}", flush=True)


def kst_today() -> dt.date:
    """머신 타임존과 무관하게 KST(UTC+9) 기준 오늘 날짜."""
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).date()


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------
def fetch_daily(date_str: str):
    """해당 날짜의 daily papers 목록(list)을 반환. 없으면 []."""
    try:
        r = requests.get(HF_API, params={"date": date_str}, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:  # noqa: BLE001
        log(f"  API 오류({date_str}): {e}")
        return []


def resolve_latest_date(explicit: str | None):
    """명시 날짜가 있으면 그대로, 없으면 오늘부터 거슬러 논문이 있는 최신 날짜를 찾는다."""
    if explicit:
        items = fetch_daily(explicit)
        return explicit, items
    today = kst_today()
    for back in range(0, 8):
        d = (today - dt.timedelta(days=back)).strftime("%Y-%m-%d")
        items = fetch_daily(d)
        log(f"날짜 확인 {d}: {len(items)}편")
        if items:
            return d, items
    return today.strftime("%Y-%m-%d"), []


def normalize(item: dict) -> dict:
    """HF API 항목 → 내부 표준 dict."""
    paper = item.get("paper") or {}
    arxiv_id = paper.get("id") or item.get("id") or ""
    title = (item.get("title") or paper.get("title") or "").strip()
    summary = (paper.get("summary") or item.get("summary") or "").strip()
    upvotes = paper.get("upvotes") or item.get("upvotes") or 0
    ai_keywords = paper.get("ai_keywords") or []
    ai_summary = paper.get("ai_summary") or ""
    authors = [a.get("name", "") for a in (paper.get("authors") or []) if a.get("name")]
    org = item.get("organization") or {}
    org_hint = org.get("fullname") or org.get("name") or ""
    return {
        "id": arxiv_id,
        "title": title,
        "title_ko": "",
        "authors": authors,
        "organizations": [],
        "org_hint": org_hint,
        "upvotes": int(upvotes),
        "topics": [],
        "is_priority": False,
        "hf_url": f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else "",
        "arxiv_abs_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
        "arxiv_pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
        "pdf_path": "",
        "pdf_ok": False,
        "hf_summary": summary,
        "ai_keywords": ai_keywords,
        "ai_summary": ai_summary,
        "summary": {"core_idea": "", "key_results": [], "conclusion": "", "affiliations": ""},
        "infographic": {"hero_path": "", "image_path": "", "headline": "", "points": []},
        "status": {"summarized": False, "hero": False, "composed": False},
    }


def tag_topics(p: dict) -> None:
    text = " ".join([p["title"], p["hf_summary"], " ".join(p["ai_keywords"])]).lower()
    found = []
    for topic, patterns in TOPIC_PATTERNS.items():
        if any(re.search(pat, text) for pat in patterns):
            found.append(topic)
    p["topics"] = found
    p["is_priority"] = bool(found)


def select_papers(papers: list, top_n: int) -> list:
    for p in papers:
        tag_topics(p)
    priority = sorted([p for p in papers if p["is_priority"]], key=lambda x: -x["upvotes"])
    others = sorted([p for p in papers if not p["is_priority"]], key=lambda x: -x["upvotes"])

    selected = list(priority)                       # 우선 토픽은 모두 포함
    for p in others:
        if len(selected) >= top_n:
            break
        selected.append(p)
    if len(selected) > HARD_CAP:
        log(f"  선정 {len(selected)}편 → 상한 {HARD_CAP}편으로 제한(upvote 기준)")
        selected = sorted(selected, key=lambda x: -x["upvotes"])[:HARD_CAP]

    selected.sort(key=lambda x: -x["upvotes"])      # 표시 순서: upvote 내림차순
    for rank, p in enumerate(selected, start=1):
        p["rank"] = rank
    return selected


def download_pdf(p: dict, day_dir: Path) -> None:
    if not p["id"]:
        return
    pdf_dir = day_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    dest = pdf_dir / f"{p['id']}.pdf"
    rel = dest.relative_to(ROOT).as_posix()
    if dest.exists() and dest.stat().st_size > 1000:
        p["pdf_path"], p["pdf_ok"] = rel, True
        return
    try:
        r = requests.get(p["arxiv_pdf_url"], headers=HEADERS, timeout=60, allow_redirects=True)
        r.raise_for_status()
        if not (r.content[:5] == b"%PDF-" or "pdf" in r.headers.get("Content-Type", "")):
            raise ValueError("PDF가 아님")
        dest.write_bytes(r.content)
        p["pdf_path"], p["pdf_ok"] = rel, True
        log(f"  PDF 저장: {p['id']} ({len(r.content)//1024} KB)")
    except Exception as e:  # noqa: BLE001
        p["pdf_ok"] = False
        log(f"  PDF 실패: {p['id']} ({e}) → 초록으로 대체 예정")


def cmd_fetch(args) -> None:
    date_str, raw = resolve_latest_date(args.date)
    if not raw:
        log(f"{date_str}: 처리할 논문이 없습니다. 종료합니다.")
        sys.exit(2)
    log(f"대상 날짜: {date_str} (총 {len(raw)}편)")

    papers = [normalize(it) for it in raw if (it.get("paper") or {}).get("id") or it.get("id")]
    selected = select_papers(papers, args.top)

    day_dir = DAYS_DIR / date_str
    (day_dir / "img").mkdir(parents=True, exist_ok=True)

    log(f"선정 {len(selected)}편 (우선토픽 {sum(p['is_priority'] for p in selected)}편) — PDF 다운로드 시작")
    for p in selected:
        download_pdf(p, day_dir)
        time.sleep(1.0)  # arxiv 예의상 지연

    out = {
        "date": date_str,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": "huggingface daily papers",
        "top_n": args.top,
        "total_available": len(raw),
        "papers": selected,
    }
    (day_dir / "papers.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"papers.json 작성 완료 → {day_dir / 'papers.json'}")

    # Claude가 이어서 채울 항목 안내
    print("\nNEXT_STEPS:")
    print(json.dumps({
        "date": date_str,
        "papers_json": str((day_dir / "papers.json").relative_to(ROOT).as_posix()),
        "to_fill_per_paper": ["title_ko", "organizations", "summary.*",
                              "infographic.headline", "infographic.points(3-4)"],
        "pdf_ok_count": sum(p["pdf_ok"] for p in selected),
    }, ensure_ascii=False))


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def load_template(name: str):
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return env.get_template(name)


def cmd_build(args) -> None:
    date_str = args.date
    day_dir = DAYS_DIR / date_str
    pj = day_dir / "papers.json"
    if not pj.exists():
        log(f"{pj} 가 없습니다. 먼저 fetch 를 실행하세요.")
        sys.exit(1)
    data = json.loads(pj.read_text(encoding="utf-8"))
    papers = data["papers"]

    # 일자별 페이지 렌더
    tpl = load_template("day.html.j2")
    html = tpl.render(date=date_str, papers=papers, data=data)
    (day_dir / "index.html").write_text(html, encoding="utf-8")
    log(f"일자별 페이지 생성 → {day_dir / 'index.html'}")

    # manifest 갱신 (추가만)
    manifest = {"site": "AI Daily Papers", "days": []}
    if MANIFEST_PATH.exists():
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    manifest.setdefault("days", [])
    manifest["days"] = [d for d in manifest["days"] if d.get("date") != date_str]

    topics_union = sorted({t for p in papers for t in p.get("topics", [])})
    day_entry = {
        "date": date_str,
        "count": len(papers),
        "topics": topics_union,
        "page": f"days/{date_str}/index.html",
        "papers": [
            {
                "id": p["id"],
                "title": p["title"],
                "title_ko": p.get("title_ko", ""),
                "organizations": p.get("organizations", []) or ([p["org_hint"]] if p.get("org_hint") else []),
                "upvotes": p.get("upvotes", 0),
                "topics": p.get("topics", []),
                "image": (f"days/{date_str}/" + p["infographic"]["image_path"]) if p["infographic"].get("image_path") else "",
                "hf_url": p.get("hf_url", ""),
            }
            for p in papers
        ],
    }
    manifest["days"].append(day_entry)
    manifest["days"].sort(key=lambda d: d["date"], reverse=True)
    manifest["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"manifest.json 갱신 완료 ({len(manifest['days'])}일치 누적)")


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------
def run(cmd: list[str]) -> int:
    import subprocess
    log("$ " + " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def cmd_deploy(args) -> None:
    date_str = args.date or kst_today().strftime("%Y-%m-%d")
    run(["git", "add", "-A"])
    msg = f"papers {date_str}"
    rc = run(["git", "commit", "-m", msg])
    if rc != 0:
        log("커밋할 변경사항이 없거나 커밋 실패. push는 계속 시도합니다.")
    # 첫 푸시면 -u, 이후엔 일반 push
    if run(["git", "push", "origin", "main"]) != 0:
        run(["git", "push", "-u", "origin", "main"])
    log(f"배포 시도 완료 → https://mini486ok.github.io/AI_daily_papers/")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="HF Daily Papers 파이프라인")
    sub = ap.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="논문 수집·선정·PDF 다운로드")
    f.add_argument("--date", help="YYYY-MM-DD (생략 시 최신 자동)")
    f.add_argument("--top", type=int, default=DEFAULT_TOP_N, help=f"처리 편수(기본 {DEFAULT_TOP_N})")
    f.set_defaults(func=cmd_fetch)

    b = sub.add_parser("build", help="일자별 페이지 생성 + manifest 갱신")
    b.add_argument("date", help="YYYY-MM-DD")
    b.set_defaults(func=cmd_build)

    d = sub.add_parser("deploy", help="git commit & push")
    d.add_argument("date", nargs="?", help="YYYY-MM-DD (커밋 메시지용)")
    d.set_defaults(func=cmd_deploy)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
