#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
하이브리드 인포그래픽 합성기.

gpt-image 가 생성한 비주얼(hero)을 가운데 배치하고, 그 위/아래에 맑은 고딕 폰트로
또렷한 한글 텍스트(제목·핵심 포인트·소속·토픽)를 합성하여 세로형 인포그래픽 PNG를 만든다.
gpt-image 의 한글 렌더링 한계를 피하면서도 AI 비주얼의 장점을 살리기 위한 구조.

사용:
  python compose_infographic.py --spec spec.json --hero hero.png --out paper-01.png
  # 또는 hero 생략 시 그라데이션 플레이스홀더 사용

spec.json 예:
{
  "headline": "한 줄 핵심 제목(한글)",
  "title_en": "Original English Title",
  "points": ["핵심 포인트 1", "주요 결과 2", "결론/시사점 3"],
  "organizations": ["Google DeepMind", "MIT"],
  "topics": ["Agentic AI", "MCP"],
  "rank": 1,
  "upvotes": 123,
  "date": "2026-06-15"
}
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

# --- 캔버스 / 레이아웃 상수 -------------------------------------------------
W, H = 1080, 1620
MARGIN = 64
FONT_REG = "C:/Windows/Fonts/malgun.ttf"
FONT_BOLD = "C:/Windows/Fonts/malgunbd.ttf"

# 토픽별 액센트 색
TOPIC_COLORS = {
    "MCP": (99, 102, 241),
    "Orchestration": (14, 165, 233),
    "Agentic AI": (139, 92, 246),
    "Ontology": (16, 185, 129),
}
DEFAULT_ACCENT = (37, 99, 235)

INK = (15, 23, 42)        # 본문 진한 남색
SUBINK = (100, 116, 139)  # 보조 회색
PANEL = (255, 255, 255)
PANEL_BORDER = (226, 232, 240)
BG_TOP = (244, 246, 251)
BG_BOTTOM = (255, 255, 255)

# 세로 영역 분할 (고정 zone + 오버플로는 말줄임)
HEADER_H = 150
TITLE_Y0, TITLE_Y1 = 150, 470
HERO_Y0, HERO_Y1 = 470, 980
POINTS_Y0, POINTS_Y1 = 1000, 1500
FOOTER_Y0 = 1500


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype(FONT_REG, size)


def accent_for(topics) -> tuple:
    for t in (topics or []):
        if t in TOPIC_COLORS:
            return TOPIC_COLORS[t]
    return DEFAULT_ACCENT


def lighten(rgb, f=0.85):
    return tuple(int(c + (255 - c) * f) for c in rgb)


def wrap(draw, text, fnt, max_w):
    """공백/문자 단위로 줄바꿈."""
    if not text:
        return []
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            # 단어 하나가 너무 길면 문자 단위로 강제 분할
            if draw.textlength(trial, font=fnt) > max_w and not cur:
                buf = ""
                for ch in w:
                    if draw.textlength(buf + ch, font=fnt) <= max_w:
                        buf += ch
                    else:
                        lines.append(buf)
                        buf = ch
                cur = buf
            else:
                cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(draw, text, fnt, x, y, max_w, fill, line_h, max_lines, anchor_left=True):
    lines = wrap(draw, text, fnt, max_w)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        # 마지막 줄 말줄임
        last = lines[-1]
        while last and draw.textlength(last + "…", font=fnt) > max_w:
            last = last[:-1]
        lines[-1] = last + "…"
    for i, ln in enumerate(lines):
        draw.text((x, y + i * line_h), ln, font=fnt, fill=fill)
    return y + len(lines) * line_h


def gradient_bg():
    img = Image.new("RGB", (W, H), BG_TOP)
    px = img.load()
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return img


def cover_fit(im: Image.Image, tw: int, th: int) -> Image.Image:
    """대상 영역을 꽉 채우도록 비율 유지 크롭(cover)."""
    sw, sh = im.size
    scale = max(tw / sw, th / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return im.crop((left, top, left + tw, top + th))


def placeholder_hero(accent) -> Image.Image:
    im = Image.new("RGB", (W, HERO_Y1 - HERO_Y0), lighten(accent, 0.6))
    d = ImageDraw.Draw(im)
    d.text((W // 2, (HERO_Y1 - HERO_Y0) // 2), "AI", font=font(120, True),
           fill=(255, 255, 255), anchor="mm")
    return im


def rounded_panel(draw, box, radius, fill, border=None, bw=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=border, width=bw)


def build(spec: dict, hero_path: str | None, out_path: str) -> None:
    accent = accent_for(spec.get("topics"))
    img = gradient_bg()
    draw = ImageDraw.Draw(img)

    # ---- 헤더 밴드 ----
    draw.rectangle([0, 0, W, HEADER_H], fill=accent)
    draw.text((MARGIN, 44), "AI DAILY PAPERS", font=font(30, True), fill=(255, 255, 255))
    draw.text((MARGIN, 90), spec.get("date", ""), font=font(26), fill=lighten(accent, 0.75))
    # rank 배지
    rank = spec.get("rank")
    if rank:
        r = 40
        cx, cy = W - MARGIN - r, HEADER_H // 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255))
        draw.text((cx, cy), f"{rank}", font=font(40, True), fill=accent, anchor="mm")
    # upvotes
    up = spec.get("upvotes")
    if up:
        draw.text((W - MARGIN - 100, 44), f"▲ {up}", font=font(28, True),
                  fill=(255, 255, 255), anchor="ra")

    # ---- 제목 영역 ----
    y = TITLE_Y0 + 24
    y = draw_wrapped(draw, spec.get("headline", ""), font(50, True),
                     MARGIN, y, W - 2 * MARGIN, INK, 64, max_lines=3)
    y += 14
    if spec.get("title_en"):
        draw_wrapped(draw, spec["title_en"], font(26), MARGIN, y,
                     W - 2 * MARGIN, SUBINK, 34, max_lines=2)

    # ---- hero 비주얼 ----
    hero_h = HERO_Y1 - HERO_Y0
    try:
        hero = Image.open(hero_path).convert("RGB") if hero_path and Path(hero_path).exists() else placeholder_hero(accent)
    except Exception:  # noqa: BLE001
        hero = placeholder_hero(accent)
    hero = cover_fit(hero, W, hero_h)
    img.paste(hero, (0, HERO_Y0))
    # hero 상/하단에 얇은 액센트 라인
    draw.rectangle([0, HERO_Y0, W, HERO_Y0 + 6], fill=accent)
    draw.rectangle([0, HERO_Y1 - 6, W, HERO_Y1], fill=accent)

    # ---- 핵심 포인트 ----
    points = (spec.get("points") or [])[:4]
    if points:
        zone_h = POINTS_Y1 - POINTS_Y0
        gap = 16
        ph = (zone_h - gap * (len(points) - 1)) // len(points)
        py = POINTS_Y0
        for pt in points:
            rounded_panel(draw, [MARGIN, py, W - MARGIN, py + ph], 20,
                          PANEL, border=PANEL_BORDER, bw=2)
            # 액센트 점
            dot_r = 9
            draw.ellipse([MARGIN + 28 - dot_r, py + ph // 2 - dot_r,
                          MARGIN + 28 + dot_r, py + ph // 2 + dot_r], fill=accent)
            # 텍스트(세로 중앙 정렬 근사)
            tx = MARGIN + 60
            tw = (W - MARGIN) - tx - 28
            lines = wrap(draw, pt, font(30), tw)
            lines = lines[:2]
            text_h = len(lines) * 40
            ty = py + (ph - text_h) // 2
            draw_wrapped(draw, pt, font(30), tx, ty, tw, INK, 40, max_lines=2)
            py += ph + gap

    # ---- 푸터: 소속 / 토픽 ----
    draw.rectangle([0, FOOTER_Y0, W, H], fill=lighten(accent, 0.9))
    orgs = ", ".join(spec.get("organizations") or [])
    if orgs:
        draw.text((MARGIN, FOOTER_Y0 + 26), "소속", font=font(18, True), fill=accent)
        draw_wrapped(draw, orgs, font(24, True), MARGIN + 52, FOOTER_Y0 + 24,
                     W - 2 * MARGIN - 52, INK, 30, max_lines=1)
    # 토픽 칩
    chip_x = MARGIN
    chip_y = FOOTER_Y0 + 66
    for t in (spec.get("topics") or []):
        cw = draw.textlength(t, font=font(22, True)) + 36
        rounded_panel(draw, [chip_x, chip_y, chip_x + cw, chip_y + 40], 20, accent)
        draw.text((chip_x + 18, chip_y + 8), t, font=font(22, True), fill=(255, 255, 255))
        chip_x += cw + 12
    # 출처
    draw.text((W - MARGIN, H - 30), "출처: arXiv · Hugging Face Daily Papers",
              font=font(20), fill=SUBINK, anchor="rs")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    print(f"[compose] 인포그래픽 저장 → {out_path}")


def spec_from_papers(papers_json: str, rank: int) -> dict:
    """papers.json + rank → 합성기 spec. Claude가 채운 필드를 그대로 활용."""
    data = json.loads(Path(papers_json).read_text(encoding="utf-8"))
    p = next((x for x in data["papers"] if x.get("rank") == rank), None)
    if p is None:
        raise SystemExit(f"rank {rank} 논문을 papers.json에서 찾을 수 없습니다.")
    ig = p.get("infographic", {})
    orgs = p.get("organizations") or ([p["org_hint"]] if p.get("org_hint") else [])
    return {
        "headline": ig.get("headline") or p.get("title_ko") or p.get("title", ""),
        "title_en": p.get("title", ""),
        "points": ig.get("points") or [],
        "organizations": orgs,
        "topics": p.get("topics", []),
        "rank": p.get("rank"),
        "upvotes": p.get("upvotes", 0),
        "date": data.get("date", ""),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="spec JSON 파일 경로")
    ap.add_argument("--papers", help="papers.json 경로 (--rank 와 함께 사용)")
    ap.add_argument("--rank", type=int, help="papers.json 내 대상 논문 rank")
    ap.add_argument("--hero", help="gpt-image 비주얼 PNG 경로(생략 시 플레이스홀더)")
    ap.add_argument("--out", required=True, help="출력 PNG 경로")
    args = ap.parse_args()
    if args.papers and args.rank is not None:
        spec = spec_from_papers(args.papers, args.rank)
    elif args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    else:
        raise SystemExit("--spec 또는 (--papers 와 --rank) 중 하나가 필요합니다.")
    build(spec, args.hero, args.out)


if __name__ == "__main__":
    main()
