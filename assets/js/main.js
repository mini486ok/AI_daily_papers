/* =========================================================================
   AI Daily Papers — 테마 토글 + 메인 페이지 동적 렌더링
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
  });

  /* ---------- 유틸 ---------- */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function tagHtml(topics) {
    return (topics || []).map((t) => `<span class="tag" data-t="${esc(t)}">${esc(t)}</span>`).join("");
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
  const state = { query: "", date: "all", sort: "date", days: [] };

  function initIndex() {
    fetch("data/manifest.json", { cache: "no-store" })
      .then((r) => r.json())
      .then((m) => {
        state.days = (m.days || []).slice();
        buildControls();
        renderStats();
        render();
      })
      .catch(() => {
        document.getElementById("app").innerHTML =
          '<div class="empty">아직 게시된 논문이 없습니다. <code>/daily-papers</code> 를 실행해 첫 데이터를 생성하세요.</div>';
      });
  }

  function allPapers() {
    const out = [];
    state.days.forEach((d) =>
      (d.papers || []).forEach((p) => out.push(Object.assign({ date: d.date, page: d.page }, p)))
    );
    return out;
  }

  function buildControls() {
    // 날짜 칩
    const dateChips = document.getElementById("dateChips");
    if (dateChips) {
      const dates = state.days.map((d) => d.date);
      dateChips.innerHTML = ["all", ...dates]
        .map(
          (dt) =>
            `<button class="chip${dt === "all" ? " active" : ""}" data-date="${esc(dt)}">${
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
    // 날짜별 섹션 (기본)
    app.innerHTML = state.days
      .filter((d) => dateOk(d.date))
      .map((d) => {
        const papers = (d.papers || []).filter(matches);
        if (!papers.length) return "";
        return `<section class="day-section">
          <div class="day-head">
            <h2>${esc(fmtDate(d.date))}</h2>
            <span class="count">${papers.length}편</span>
            <a class="seeall" href="${esc(d.page)}">그날 전체 페이지 →</a>
          </div>
          <div class="grid">${papers.map((p) => cardHtml(Object.assign({ page: d.page }, p))).join("")}</div>
        </section>`;
      })
      .join("");
  }
})();
