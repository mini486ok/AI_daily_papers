---
description: 허깅페이스 Daily Papers 핵심 논문을 한글 요약·칠판 인포그래픽으로 만들어 GitHub Pages에 배포
argument-hint: "[YYYY-MM-DD] (생략 시 최신 날짜 자동)"
---

당신은 이 저장소(AI Daily Papers)의 **일일 논문 파이프라인**을 실행합니다. 모든 명령은 저장소 루트에서 수행하세요.
선택 인자(특정 날짜): `$ARGUMENTS` — 비어 있으면 가장 최신 날짜를 자동 사용합니다.

아래 순서를 **그대로** 따르세요. 각 단계 결과를 간단히 보고하며 진행합니다.

---

### 1단계 · 수집 (스크립트)
- 실행: `python scripts/pipeline.py fetch` — 인자가 주어졌다면 `--date $ARGUMENTS` 를 덧붙입니다.
- 출력의 **대상 날짜**를 `DATE` 로 기억하고, `days/DATE/papers.json` 경로를 확인합니다.
- "처리할 논문이 없습니다"로 종료되면, 사용자에게 알리고 **중단**합니다.
- `days/DATE/` 가 이미 완성돼 있으면(재실행) 덮어쓸지 사용자에게 먼저 확인합니다.

### 2단계 · 요약 (Claude, 논문별)
`days/DATE/papers.json` 을 읽고, `papers` 의 각 논문에 대해:
- `pdf_ok=true` 면 `pdf_path` 의 PDF를 **Read 도구로 직접 읽습니다**(초록·서론·방법·결과·결론 중심, 긴 논문은 pages 인자 활용). `pdf_ok=false` 면 `hf_summary`·`ai_summary` 로 대체합니다.
- 여러 논문은 **병렬 서브에이전트**(general-purpose)로 나눠 읽으면 빠릅니다. 각 논문에 대해 다음을 **한글로** 채웁니다(간결·핵심 위주):
  - `organizations`: 저자 소속 기관 배열(PDF 표지/각주에서 확인, 없으면 `org_hint` 사용)
  - `summary.core_idea`: 핵심 아이디어 2~3문장
  - `summary.key_results`: 주요 결과 불릿 2~4개(수치/벤치마크 위주, **문자열 배열**)
  - `summary.conclusion`: 결론 및 시사점 2~3문장
  - `infographic.image_path`: `"img/paper-NN.png"` (NN = rank 2자리, 예: `img/paper-01.png`)
  - `status.summarized`: `true`
- 모든 논문 처리 후, **papers.json 전체를 Write 도구로 다시 저장**합니다(다른 필드·구조 보존).
- 참고: 제목은 **영문 원제만** 사용합니다(한글 번역 제목은 사이트·인포그래픽 어디에도 쓰지 않으므로 만들 필요 없음).

### 3단계 · 칠판 인포그래픽 합성 (스크립트, 한 번에)
모든 논문을 한 번에 렌더링합니다(Playwright로 칠판 도식 HTML 템플릿을 PNG로 — 영문제목·소속·핵심아이디어·주요결과·결론을 한 장에 또렷한 한글로, 통일 스타일):
```
python scripts/compose_infographic.py --papers days/DATE/papers.json --all
```
- 요약(2단계)을 papers.json 기준으로 읽어 `days/DATE/img/paper-NN.png` 를 생성합니다.
- **gpt-image는 사용하지 않습니다**(한글 텍스트를 또렷하게 넣고 11편을 동일 양식으로 만들기 위해 HTML 렌더링 사용).

### 4단계 · 품질 검증(QA)
- 생성된 인포그래픽 중 **2~3장을 Read 도구로 열어** 확인: ① 한글 텍스트가 또렷/정확한지 ② 박스·화살표 도식 레이아웃이 깨지지 않았는지 ③ 내용이 잘리지 않았는지.
- 문제가 있으면 요약 텍스트를 다듬거나 템플릿을 조정한 뒤 3단계를 재실행합니다.

### 5단계 · 페이지 생성 (스크립트)
- 실행: `python scripts/pipeline.py build DATE`
- → `days/DATE/index.html` 생성 + `data/manifest.json` 에 해당 날짜 **추가**(메인 `index.html` 은 건드리지 않음).

### 6단계 · 검수 & 배포 (스크립트)
- `days/DATE/index.html` 과 `data/manifest.json` 이 정상인지 가볍게 확인합니다.
- 실행: `python scripts/pipeline.py deploy DATE`
- 완료 후 사용자에게 처리 편수·배포 URL(`https://mini486ok.github.io/AI_daily_papers/`)을 보고합니다(반영까지 약 1분).

---

**유의사항**
- `index.html`·`assets/`·`templates/` 는 최초 1회 생성된 자산이므로 **수정하지 않습니다**(매일 바뀌는 것은 `data/manifest.json` 추가와 `days/DATE/` 신규 생성뿐).
- 우선 토픽(MCP·Orchestration·Agentic AI·Ontology) 강제 포함은 1단계 `fetch` 에서 자동 처리됩니다(선정용이며 화면에는 표시하지 않음).
- 배포(push) 시 인증이 필요하면 사용자에게 알리고 대기합니다.
