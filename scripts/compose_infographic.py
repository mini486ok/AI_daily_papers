#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
인포그래픽 합성기 (HTML → PNG, Playwright) — 칠판 도식 스타일.

논문의 핵심 내용(영문 제목·저자 소속·핵심 아이디어·주요 결과·결론)을 "칠판에 도식화한"
느낌의 한 장짜리 한글 인포그래픽 이미지로 렌더링한다. 통일된 템플릿
(templates/infographic.html.j2)을 사용하므로 모든 논문이 동일한 양식/스타일을 가진다.
한글 텍스트를 또렷하게 넣고 스타일을 통일하기 위해 gpt-image가 아닌 HTML 렌더링을 사용한다.

사용:
  python compose_infographic.py --papers days/DATE/papers.json --all      # 전체
  python compose_infographic.py --papers days/DATE/papers.json --rank 1 --out days/DATE/img/paper-01.png
"""
import argparse
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


def spec_from_paper(p: dict, date: str) -> dict:
    orgs = p.get("organizations") or ([p["org_hint"]] if p.get("org_hint") else [])
    s = p.get("summary", {})
    return {
        "date": date,
        "rank": p.get("rank"),
        "title_en": p.get("title", ""),
        "organizations": orgs,
        "core_idea": s.get("core_idea", ""),
        "key_results": s.get("key_results", []),
        "conclusion": s.get("conclusion", ""),
    }


def make_env():
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_one(page, env, spec: dict, out: str) -> None:
    html = env.get_template("infographic.html.j2").render(**spec)
    page.set_content(html, wait_until="networkidle")
    page.wait_for_timeout(300)  # 폰트 적용 안정화
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    page.locator(".board").screenshot(path=out)
    print(f"[compose] 인포그래픽 저장 → {out}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", required=True, help="papers.json 경로")
    ap.add_argument("--rank", type=int, help="단일 렌더링 대상 rank")
    ap.add_argument("--all", action="store_true", help="papers.json의 모든 논문 렌더링")
    ap.add_argument("--out", help="(단일) 출력 PNG 경로")
    args = ap.parse_args()

    data = json.loads(Path(args.papers).read_text(encoding="utf-8"))
    date = data.get("date", "")
    img_dir = Path(args.papers).resolve().parent / "img"

    env = make_env()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1160, "height": 1200}, device_scale_factor=2)

        if args.all:
            for paper in data["papers"]:
                out = img_dir / f"paper-{paper['rank']:02d}.png"
                render_one(page, env, spec_from_paper(paper, date), str(out))
        else:
            if args.rank is None or not args.out:
                raise SystemExit("--all 이 아니면 --rank 와 --out 이 필요합니다.")
            paper = next((x for x in data["papers"] if x.get("rank") == args.rank), None)
            if paper is None:
                raise SystemExit(f"rank {args.rank} 논문을 찾을 수 없습니다.")
            render_one(page, env, spec_from_paper(paper, date), args.out)

        browser.close()


if __name__ == "__main__":
    main()
