/* =========================================================================
   AI Daily Papers — 테마 토글 + 메인 동적 렌더링 + 상세 네비/스마트 점프
   ========================================================================= */
(function () {
  "use strict";

  /* ---------- 테마 ---------- */
  const root = document.documentElement;
  function currentTheme() {
    return root.getAttribute("data-theme") || "light";
  }
  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch (e) {}
    const btn = document.getElementById("themeToggle");
    if (btn) btn.textContent = theme === "dark" ? "☀️" : "🌙";
  }
  window.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("themeToggle");
    if (btn) {
      btn.textContent = currentTheme() === "dark" ? "☀️" : "🌙";
      btn.addEventListener("click", function () {
        applyTheme(currentTheme() === "dark" ? "light" : "dark");
      });
    }
    if (document.getElementById("app")) initIndex();
    else if (document.querySelector(".day-hero")) initDetail();
  });

  /* ---------- 유틸 ---------- */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function orgText(p) {
    const o = p.organizations || [];
    return o.length ? o.join(", ") : "소속 정보 미상";
  }
  function fmtDate(d) {
    const days = ["일", "월", "화", "수", "목", "금", "토"];
    const dt = new Date(d + "T00:00:00");
    if (isNaN(dt)) return d;
    return `${d} (${days[dt.getDay()]})`;
  }

  /* ---------- 인덱스 페이지 ---------- */
  const state = { query: "", date: "all", sort: "date", days: [], open: {} };

  function initIndex() {
    fetch("data/manifest.json", { cache: "no-store" })
      .then((r) => r.json())
      .then((m) => {
        state.days = (m.days || []).slice();
        // URL 파라미터(?d=DATE)로 특정 날짜로 진입(상세→아카이브 복귀 시)
        const params = new URLSearchParams(location.search);
        const want = params.get("d");
        const dates = state.days.map((d) => d.date);
        if (want && dates.indexOf(want) >= 0) state.date = want;
        else if (dates.length) state.date = dates[0]; // 기본: 최신 날짜만
        if (dates.length) state.open[dates[0]] = true; // 전체보기 시 최신만 펼침
        buildControls();
        renderStats();
        render();
        scrollToDateHash();
      })
      .catch(() => {
        document.getElementById("app").innerHTML =
          '<div class="empty">아직 게시된 논문이 없습니다. <code>/daily-papers</code> 를 실행해 첫 데이터를 생성하세요.</div>';
      });
    setupBackToTop();
  }

  function allPapers() {
    const out = [];
    state.days.forEach((d) =>
      (d.papers || []).forEach((p) => out.push(Object.assign({ date: d.date, page: d.page }, p)))
    );
    return out;
  }

  function buildControls() {
    const dateChips = document.getElementById("dateChips");
    if (dateChips) {
      const dates = state.days.map((d) => d.date);
      dateChips.innerHTML = ["all", ...dates]
        .map(
          (dt) =>
            `<button class="chip${dt === state.date ? " active" : ""}" data-date="${esc(dt)}">${
              dt === "all" ? "전체" : esc(dt)
            }</button>`
        )
        .join("");
      dateChips.querySelectorAll(".chip").forEach((c) =>
        c.addEventListener("click", function () {
          dateChips.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
          c.classList.add("active");
          state.date = c.getAttribute("data-date");
          render();
          const main = document.querySelector("main");
          if (main) window.scrollTo({ top: 0, behavior: "smooth" });
        })
      );
    }

    const search = document.getElementById("search");
    if (search)
      search.addEventListener("input", function () {
        state.query = this.value.trim().toLowerCase();
        render();
      });
    const sort = document.getElementById("sort");
    if (sort)
      sort.addEventListener("change", function () {
        state.sort = this.value;
        render();
      });
  }

  function renderStats() {
    const totalDays = state.days.length;
    const totalPapers = state.days.reduce((s, d) => s + (d.count || (d.papers || []).length), 0);
    const el = document.getElementById("stats");
    if (!el) return;
    const latest = totalDays ? state.days[0].date : "-";
    el.innerHTML = `
      <div class="stat"><div class="num">${totalDays}</div><div class="lbl">아카이브 일수</div></div>
      <div class="stat"><div class="num">${totalPapers}</div><div class="lbl">누적 논문</div></div>
      <div class="stat"><div class="num">${esc(latest)}</div><div class="lbl">최신 업데이트</div></div>`;
  }

  function matches(p) {
    if (!state.query) return true;
    const hay = [p.title, (p.organizations || []).join(" "), p.summary_line || "", p.date]
      .join(" ")
      .toLowerCase();
    return hay.includes(state.query);
  }

  function cardHtml(p) {
    const href = `${p.page}#paper-${esc(p.id)}`;
    return `<a class="card" href="${href}">
      <div class="body">
        <div class="card-title">${esc(p.title)}</div>
        ${p.summary_line ? `<div class="card-summary">${esc(p.summary_line)}</div>` : ""}
        <div class="org">${esc(orgText(p))}</div>
      </div>
    </a>`;
  }

  function daySectionHtml(d, papers, collapsible) {
    const open = !collapsible || !!state.open[d.date];
    return `<section class="day-section${collapsible ? " collapsible" : ""}${open ? "" : " collapsed"}" data-date="${esc(d.date)}">
      <div class="day-head" ${collapsible ? 'role="button" tabindex="0"' : ""}>
        ${collapsible ? '<span class="toggle" aria-hidden="true">▾</span>' : ""}
        <h2>${esc(fmtDate(d.date))}</h2>
        <span class="count">${papers.length}편</span>
        <a class="seeall" href="${esc(d.page)}">그날 전체 페이지 →</a>
      </div>
      <div class="day-body">
        <div class="grid">${papers.map((p) => cardHtml(Object.assign({ page: d.page }, p))).join("")}</div>
      </div>
    </section>`;
  }

  function render() {
    const app = document.getElementById("app");
    const dateOk = (dt) => state.date === "all" || dt === state.date;
    const filtered = allPapers().filter((p) => matches(p) && dateOk(p.date));
    if (!filtered.length) {
      app.innerHTML = '<div class="empty">조건에 맞는 논문이 없습니다.</div>';
      return;
    }
    const flatMode = state.query || state.sort === "upvotes";
    if (flatMode) {
      const arr = filtered.slice();
      if (state.sort === "upvotes") arr.sort((a, b) => (b.upvotes || 0) - (a.upvotes || 0));
      else arr.sort((a, b) => (b.date < a.date ? -1 : b.date > a.date ? 1 : (b.upvotes || 0) - (a.upvotes || 0)));
      app.innerHTML = `<div class="grid">${arr.map(cardHtml).join("")}</div>`;
      return;
    }
    // 날짜별 섹션. '전체'일 때만 접이식(최신만 펼침), 단일 날짜는 펼침 고정.
    const collapsible = state.date === "all";
    app.innerHTML = state.days
      .filter((d) => dateOk(d.date))
      .map((d) => {
        const papers = (d.papers || []).filter(matches);
        if (!papers.length) return "";
        return daySectionHtml(d, papers, collapsible);
      })
      .join("");
    if (collapsible) wireDayToggles(app);
  }

  function wireDayToggles(app) {
    app.querySelectorAll(".day-section.collapsible .day-head").forEach((head) => {
      const toggle = (e) => {
        // '그날 전체 페이지' 링크 클릭은 접기 토글에서 제외
        if (e.target.closest(".seeall")) return;
        const sec = head.closest(".day-section");
        const dt = sec.getAttribute("data-date");
        const nowOpen = sec.classList.toggle("collapsed");
        state.open[dt] = !nowOpen ? true : false;
      };
      head.addEventListener("click", toggle);
      head.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(e); }
      });
    });
  }

  // 메인에서 #date-DATE 해시로 진입하면 해당 날짜로 부드럽게 이동
  function scrollToDateHash() {
    const m = (location.hash || "").match(/^#date-(.+)$/);
    if (!m) return;
    const sec = document.querySelector(`.day-section[data-date="${CSS.escape(m[1])}"]`);
    if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* =======================================================================
     상세(일자별) 페이지 — 스마트 앵커 점프 + 플로팅 네비
     ======================================================================= */
  function initDetail() {
    smartScrollToHash();
    buildDetailNav();
    setupBackToTop();
  }

  // lazy 이미지가 뒤늦게 로드되며 콘텐츠가 밀려도 타깃을 정확히 유지
  function smartScrollToHash() {
    const id = (location.hash || "").slice(1);
    if (!id) return;
    const el = document.getElementById(id);
    if (!el) return;
    let userMoved = false;
    const stop = () => {
      userMoved = true;
      window.removeEventListener("wheel", stop);
      window.removeEventListener("touchmove", stop);
      window.removeEventListener("keydown", onKey);
    };
    const onKey = (e) => {
      if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].indexOf(e.key) >= 0) stop();
    };
    window.addEventListener("wheel", stop, { passive: true });
    window.addEventListener("touchmove", stop, { passive: true });
    window.addEventListener("keydown", onKey);
    const jump = () => { if (!userMoved) el.scrollIntoView({ block: "start" }); };
    jump();
    // 아직 로드 안 된 모든 이미지가 로드/실패할 때마다 보정
    const imgs = document.images;
    for (let i = 0; i < imgs.length; i++) {
      if (!imgs[i].complete) {
        imgs[i].addEventListener("load", jump, { once: true });
        imgs[i].addEventListener("error", jump, { once: true });
      }
    }
    window.addEventListener("load", function () {
      jump();
      setTimeout(jump, 80);
      setTimeout(stop, 400); // 이후엔 사용자 스크롤에 양보
    });
  }

  // 현재 상세 페이지의 날짜를 경로에서 추출 (days/DATE/index.html)
  function detailDate() {
    const m = location.pathname.match(/days\/([^\/]+)\//);
    return m ? m[1] : null;
  }

  // 우하단 플로팅 네비: 맨 위로 / 전체 아카이브(해당 날짜로)
  function buildDetailNav() {
    const dt = detailDate();
    const wrap = document.createElement("div");
    wrap.className = "fabnav";
    wrap.innerHTML = `
      <button class="fab" data-act="top" title="이 날짜 목록 맨 위로" aria-label="맨 위로">↑</button>
      <a class="fab fab-home" href="../../${dt ? "?d=" + encodeURIComponent(dt) + "#date-" + encodeURIComponent(dt) : ""}" title="전체 아카이브로" aria-label="전체 아카이브">⌂</a>`;
    document.body.appendChild(wrap);
    wrap.querySelector('[data-act="top"]').addEventListener("click", () =>
      window.scrollTo({ top: 0, behavior: "smooth" })
    );
    const onScroll = () => wrap.classList.toggle("show", window.scrollY > 320);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // 메인 전용 '맨 위로' (긴 전체 목록 대비)
  function setupBackToTop() {
    if (document.querySelector(".fabnav")) return; // 상세는 buildDetailNav가 담당
    const wrap = document.createElement("div");
    wrap.className = "fabnav";
    wrap.innerHTML = `<button class="fab" data-act="top" title="맨 위로" aria-label="맨 위로">↑</button>`;
    document.body.appendChild(wrap);
    wrap.querySelector('[data-act="top"]').addEventListener("click", () =>
      window.scrollTo({ top: 0, behavior: "smooth" })
    );
    const onScroll = () => wrap.classList.toggle("show", window.scrollY > 600);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }
})();
