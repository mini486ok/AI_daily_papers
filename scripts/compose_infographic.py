#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
인포그래픽 합성기 (HTML → PNG, Playwright).

논문 전체 내용(제목·소속·핵심 아이디어·주요 결과·결론·키워드)을 한 장의 한글 인포그래픽
이미지로 렌더링한다. 통일된 HTML/CSS 템플릿(templates/infographic.html.j2)을 사용하므로
모든 논문이 동일한 스타일을 가진다. gpt-image가 만든 텍스트 없는 hero 이미지는 상단 배너로
data URI로 임베드해 재사용한다(추가 gpt-image 호출 불필요).

사용:
  # 단일
  python compose_infographic.py --papers days/DATE/papers.json --rank 1 \
      --hero days/DATE/img/_hero_01.png --out days/DATE/img/paper-01.png
  # 전체(papers.json의 모든 논문, hero/out 경로 자동, 브라우저 1회 기동)
  python compose_infographic.py --papers days/DATE/papers.json --all
"""
import argparse
import base64
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
MAX_KEYWORDS = 8


def hero_data_uri(hero: str | None) -> str:
    if hero and Path(hero).exists():
        b = base64.b64encode(Path(hero).read_bytes()).decode()
        return f"data:image/png;base64,{b}"
    return ""


def spec_from_paper(p: dict, date: str, hero: str | None) -> dict:
    orgs = p.get("organizations") or ([p["org_hint"]] if p.get("org_hint") else [])
    s = p.get("summary", {})
    return {
        "date": date,
        "rank": p.get("rank"),
        "upvotes": p.get("upvotes", 0),
        "title_ko": p.get("title_ko") or p.get("title", ""),
        "title_en": p.get("title", ""),
        "organizations": orgs,
        "topics": p.get("topics", []),
        "keywords": (p.get("ai_keywords") or [])[:MAX_KEYWORDS],
        "core_idea": s.get("core_idea", ""),
        "key_results": s.get("key_results", []),
        "conclusion": s.get("conclusion", ""),
        "hero_uri": hero_data_uri(hero),
    }


def make_env():
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_one(page, env, spec: dict, out: str) -> None:
    html = env.get_template("infographic.html.j2").render(**spec)
    page.set_content(html, wait_until="networkidle")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    page.locator(".ig").screenshot(path=out)
    print(f"[compose] 인포그래픽 저장 → {out}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", required=True, help="papers.json 경로")
    ap.add_argument("--rank", type=int, help="단일 렌더링 대상 rank")
    ap.add_argument("--all", action="store_true", help="papers.json의 모든 논문 렌더링")
    ap.add_argument("--hero", help="(단일) hero PNG 경로")
    ap.add_argument("--out", help="(단일) 출력 PNG 경로")
    args = ap.parse_args()

    data = json.loads(Path(args.papers).read_text(encoding="utf-8"))
    date = data.get("date", "")
    img_dir = Path(args.papers).resolve().parent / "img"

    env = make_env()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1120, "height": 1200}, device_scale_factor=2)

        if args.all:
            for paper in data["papers"]:
                rank = paper["rank"]
                hero = img_dir / f"_hero_{rank:02d}.png"
                out = img_dir / f"paper-{rank:02d}.png"
                spec = spec_from_paper(paper, date, str(hero))
                render_one(page, env, spec, str(out))
        else:
            if args.rank is None or not args.out:
                raise SystemExit("--all 이 아니면 --rank 와 --out 이 필요합니다.")
            paper = next((x for x in data["papers"] if x.get("rank") == args.rank), None)
            if paper is None:
                raise SystemExit(f"rank {args.rank} 논문을 찾을 수 없습니다.")
            spec = spec_from_paper(paper, date, args.hero)
            render_one(page, env, spec, args.out)

        browser.close()


if __name__ == "__main__":
    main()
