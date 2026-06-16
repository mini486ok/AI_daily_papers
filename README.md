# AI Daily Papers — 허깅페이스 논문 요약·인포그래픽 자동 아카이브

[허깅페이스 Daily Papers](https://huggingface.co/papers)에 매일 올라오는 논문 중 핵심 논문을
선별·요약하고, 한 장짜리 한글 인포그래픽을 생성해 웹페이지로 아카이빙하는 프로젝트입니다.

🌐 **배포 사이트**: https://mini486ok.github.io/AI_daily_papers/

## 동작 방식

원하는 시간에 이 폴더에서 Claude Code를 실행하고 슬래시 커맨드를 입력하면, 가장 최신 날짜의
논문에 대해 아래 파이프라인이 실행됩니다.

```
/daily-papers
   │
   ├─ ① fetch   : HF API로 최신 날짜 논문 수집 → 토픽 태깅 → 상위 10편 선정 → PDF 다운로드
   ├─ ② 요약    : 각 PDF 원문을 읽고 한글로 구조화 요약(제목/소속/핵심/결과/결론)
   ├─ ③ 인포그래픽: 논문별 비주얼(gpt-image) + 한글 텍스트 합성 → 세로형 인포그래픽 PNG
   ├─ ④ build   : 일자별 페이지(days/<date>/index.html) 생성 + manifest.json 갱신(추가만)
   └─ ⑤ deploy  : git push → GitHub Pages 자동 배포
```

## 선정 규칙

- 기본: 그날 upvote 상위 10편
- **우선 포함(반드시)**: MCP(Model Context Protocol), Multi/Multi-agent Orchestration,
  Agentic AI, Ontology 관련 논문 — 제목·요약·키워드에서 자동 감지

## 디렉터리 구조

| 경로 | 설명 |
|---|---|
| `index.html` | 메인 페이지(최초 1회 생성, 이후 불변). `data/manifest.json`을 읽어 동적 렌더 |
| `assets/css`, `assets/js` | 디자인·다크모드·검색/필터/정렬 |
| `data/manifest.json` | 누적 메타데이터(매일 항목 1건 append) |
| `days/<YYYY-MM-DD>/` | 날짜별 요약 페이지·이미지·데이터 |
| `scripts/pipeline.py` | fetch / build / deploy 오케스트레이션 |
| `scripts/compose_infographic.py` | 인포그래픽 합성기(하이브리드) |
| `templates/` | HTML 템플릿(Jinja2) |
| `.claude/commands/daily-papers.md` | 전용 슬래시 커맨드 정의 |

## 수동 사용 (스크립트 직접 실행)

```bash
python scripts/pipeline.py fetch              # 최신 날짜 자동 / 또는 --date 2026-06-15
python scripts/pipeline.py build  2026-06-15  # 요약·이미지 완료 후 페이지 생성
python scripts/pipeline.py deploy 2026-06-15  # commit & push
```
