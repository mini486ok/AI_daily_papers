---
description: 국내 언론 기준 AI·철도/대중교통 뉴스를 한글 요약·칠판 인포그래픽으로 만들어 daily_news 사이트에 배포
argument-hint: "[YYYY-MM-DD] (생략 시 어제 날짜)"
---

이 커맨드는 **어느 폴더에서 실행하든** 아래 저장소를 대상으로 Daily News 파이프라인을 수행합니다.

- **저장소 루트(절대경로)**: `C:/업무자료/claude_project/202606_daily_news` (이하 `REPO`)
- 스크립트는 **절대경로**로 실행하면 현재 작업 폴더와 무관하게 동작합니다(스크립트가 자기 위치 기준으로 REPO를 찾음). 내가 직접 만드는 파일(`articles.json` 등)도 REPO 하위 **절대경로**로 Write 합니다.

선택 인자(특정 날짜): `$ARGUMENTS` — 비어 있으면 **어제(오늘 KST−1일)** 를 사용합니다(아침 실행 시 당일 기사가 적으므로 하루 전 날짜의 뉴스를 검색·게시).

두 주제를 각각 다룹니다: **① AI(인공지능)**, **② 철도·대중교통**. 주제별로 기준일 **당일 게재가 확인된 중요 기사 10건**을 선별·요약합니다.

### 1단계 · 날짜 확정
- 실행: `python "C:/업무자료/claude_project/202606_daily_news/scripts/build_news.py" date $ARGUMENTS`
- 출력값을 `DATE` 로 사용합니다(인자 있으면 그 날짜, 없으면 어제). 검색·게시 모두 `DATE` 기준.
- `REPO/days/DATE/` 가 이미 완성돼 있으면(재실행) 덮어쓸지 사용자에게 먼저 확인합니다.

### 2단계 · 기사 수집·요약 (Claude, 주제별)
주제별로 **병렬 서브에이전트(general-purpose)** 1개씩 띄웁니다. 각 에이전트에게:
"**오직 DATE 당일(YYYY-MM-DD)에 국내 언론사가 보도(게재)한** '<주제>' 관련 중요 기사 **10건**을 찾아라.
한국어로 WebSearch 하고(예: '<주제> YYYY년 M월 D일', '<주제> 뉴스 YYYY.MM.DD'), **각 후보 기사는 반드시 WebFetch로 본문을 열어 게재일이 DATE와 정확히 일치하는지 확인**하라. 게재일이 DATE가 아닌 기사(전날·다음날·미상)는 **제외**하라. DATE 당일 중요 기사가 10건 미만이면 억지로 채우지 말고 확인된 것만 포함하고 개수를 보고하라.
각 기사에 대해 한글로 채워라(title, outlet, url, published=DATE, summary_line=핵심 1문장 서술식, summary.core/implication/questions/rnd).
**Write 도구**로 `C:/tmp/news_<DATE>_<key>.json`(key: `ai`, `transit`)에 **기사 배열 JSON만** 저장하라(코드펜스·설명 금지)." 라고 지시합니다.
- 두 파일을 합쳐 `C:/업무자료/claude_project/202606_daily_news/days/DATE/articles.json` 을 **Write** 로 생성(절대경로). 구조:
```json
{
 "date": "DATE",
 "topics": [
   {"key": "ai", "label": "AI(인공지능)", "articles": [ {rank,title,outlet,url,published,summary_line,summary{core,implication,questions,rnd}}, ... ]},
   {"key": "transit", "label": "철도·대중교통", "articles": [ ... ]}
 ]
}
```
- 각 주제 안에서 rank 1~N(중요도순) 부여. 모든 `published` 는 DATE 와 같아야 합니다.

### 3단계 · 칠판 인포그래픽 합성
- (재실행이면) 먼저 기존 이미지를 비웁니다: `python -c "import glob,os; [os.remove(f) for f in glob.glob(r'C:/업무자료/claude_project/202606_daily_news/days/DATE/img/*.png')]"` (DATE 치환).
- 실행: `python "C:/업무자료/claude_project/202606_daily_news/scripts/compose_news.py" --articles "C:/업무자료/claude_project/202606_daily_news/days/DATE/articles.json" --all`

### 4단계 · 품질 검증(QA)
- 생성된 `REPO/days/DATE/img/*.png` 중 2~3장을 Read 도구로 열어 한글 텍스트·레이아웃을 확인합니다.

### 5단계 · 페이지 생성
- 실행: `python "C:/업무자료/claude_project/202606_daily_news/scripts/build_news.py" build DATE`
- → 일자별 페이지 + `manifest.json` 에 해당 날짜 **추가**. (게재일≠DATE 기사가 섞이면 경고가 출력되니 확인)

### 6단계 · 배포
- 실행: `python "C:/업무자료/claude_project/202606_daily_news/scripts/build_news.py" deploy DATE` (스크립트가 REPO에서 git add/commit/push 수행)
- 완료 후 처리 건수·배포 URL(`https://mini486ok.github.io/daily_news/`)을 보고합니다(반영까지 약 1분).

---

**유의사항**
- 메인 카드: 기사 제목 · 핵심 내용 1문장(서술식) · 언론사.
- 상세: 기사제목 → 칠판 인포그래픽 → 언론사 → 핵심 내용 → 시사점 → 더 생각해볼 문제 → 추진 필요한 연구개발 주제 → 원문 링크.
- `REPO`의 `index.html`·`assets/`·`templates/` 는 최초 1회 생성 자산이므로 수정하지 않습니다(매일 `manifest.json` 추가 + `days/DATE/` 신규 생성만).
- 반드시 **기준일 당일 게재가 확인된 기사만** 싣습니다(전날·다음날 금지).
