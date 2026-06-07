/* CISD Hub — renders docs/data/summary.json into the launchpad. Vanilla JS. */
(function () {
  "use strict";

  // ── Site-nav toggle (mobile "All Sites" button) ──────────────────────────
  document.querySelectorAll(".sitenav__tog").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var nav  = btn.closest(".sitenav");
      var open = nav.hasAttribute("data-open");
      if (open) {
        nav.removeAttribute("data-open");
        btn.setAttribute("aria-expanded", "false");
        btn.innerHTML = "All Sites &#9660;";
      } else {
        nav.setAttribute("data-open", "");
        btn.setAttribute("aria-expanded", "true");
        btn.innerHTML = "All Sites &#9650;";
      }
    });
  });

  function fmtUsdCompact(n) {
    if (n == null || isNaN(n)) return "—";
    var abs = Math.abs(n);
    if (abs >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
    if (abs >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
    if (abs >= 1e3) return "$" + Math.round(n / 1e3) + "K";
    return "$" + n;
  }
  function fmtInt(n) {
    if (n == null || isNaN(n)) return "—";
    return Number(n).toLocaleString("en-US");
  }
  function fmtMetric(m) {
    if (m.fmt === "usd_compact") return fmtUsdCompact(m.value);
    if (m.fmt === "int") return fmtInt(m.value);
    return m.value == null ? "—" : String(m.value);
  }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  // Minimal inline markdown: *italics* and [text](url) → safe HTML.
  function mdInline(s) {
    var out = esc(s);
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    out = out.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    return out;
  }

  function renderMetrics(node, metrics, siteUrl) {
    node.innerHTML = "";
    if (!metrics || !metrics.length) { node.appendChild(el("p", "err", "No data available.")); return; }
    metrics.forEach(function (m) {
      var cell;
      if (siteUrl) {
        cell = document.createElement("a");
        cell.className = "metric metric--link";
        cell.href = siteUrl;
        cell.target = "_blank";
        cell.rel = "noopener";
      } else {
        cell = el("div", "metric");
      }
      cell.appendChild(el("div", "metric__val", esc(fmtMetric(m))));
      cell.appendChild(el("div", "metric__label", esc(m.label)));
      if (m.sub) cell.appendChild(el("div", "metric__sub", esc(m.sub)));
      node.appendChild(cell);
    });
  }

  function buildHighlightBox(kicker, mtg, expanded) {
    var box = el("div", "hl");
    var bodyId = "hlb-" + kicker.toLowerCase().replace(/\W+/g, "");
    if (!mtg) {
      box.appendChild(el("div", "hl__hint", "No " + kicker.toLowerCase() + " available."));
      return box;
    }
    var btn = el("button", "hl__btn");
    btn.type = "button";
    btn.setAttribute("aria-expanded", expanded ? "true" : "false");
    btn.setAttribute("aria-controls", bodyId);

    var meta = el("div", "hl__meta");
    meta.appendChild(el("div", "hl__kicker", esc(kicker)));
    meta.appendChild(el("div", "hl__title", esc(mtg.type_display || "Meeting")));

    // Pull the calendar date out of date_display (e.g. "June 16, 2026 - 5:00 p.m., Jett Center")
    // and render it as a standout badge so the date itself catches the eye, separate from
    // the time/location/agenda details.
    var dateDisplay = mtg.date_display || "";
    var dateMatch = dateDisplay.match(/^([A-Za-z]+ \d{1,2}, \d{4})\s*(?:[-–—]\s*(.*))?$/);
    if (dateMatch) {
      var badge = el("div", "hl__date");
      badge.appendChild(el("span", "hl__date-icon", "📅"));
      badge.appendChild(document.createTextNode(dateMatch[1]));
      meta.appendChild(badge);
      var rest = dateMatch[2] || "";
      if (mtg.item_count) rest += (rest ? " · " : "") + mtg.item_count + " agenda items";
      if (rest) meta.appendChild(el("div", "hl__when", esc(rest)));
    } else {
      var when = dateDisplay;
      if (mtg.item_count) when += " · " + mtg.item_count + " agenda items";
      meta.appendChild(el("div", "hl__when", esc(when)));
    }
    btn.appendChild(meta);
    btn.appendChild(el("span", "hl__chev", "▾"));
    box.appendChild(btn);

    var body = el("div", "hl__body");
    body.id = bodyId;
    var ul = el("ul");
    (mtg.highlights || []).forEach(function (h) { ul.appendChild(el("li", null, mdInline(h))); });
    if (!(mtg.highlights || []).length) ul.appendChild(el("li", null, mtg.scheduled_only ? "Agenda not yet published — check back closer to the meeting date." : "Highlights not yet available."));
    body.appendChild(ul);
    if (mtg.url) {
      var link = el("a", null, "View full breakdown ↗");
      link.href = mtg.url; link.target = "_blank"; link.rel = "noopener";
      link.style.fontSize = "13px"; link.style.fontWeight = "600";
      body.appendChild(link);
    }
    box.appendChild(body);

    btn.addEventListener("click", function () {
      btn.setAttribute("aria-expanded", btn.getAttribute("aria-expanded") === "true" ? "false" : "true");
    });
    return box;
  }

  function buildAlertSignup() {
    var wrap = el("div", "alert-signup");
    var label = el("label", "alert-signup__label");
    label.htmlFor = "hub-alert-email";
    label.textContent = "Get meeting alerts";
    var row = el("div", "alert-signup__row");
    var input = document.createElement("input");
    input.type = "email"; input.id = "hub-alert-email";
    input.className = "alert-signup__input";
    input.placeholder = "your@email.com";
    input.autocomplete = "email"; input.maxLength = 254;
    var btn = el("button", "alert-signup__btn", "Notify me");
    btn.type = "button";
    var msg = el("span", "alert-signup__msg"); msg.setAttribute("aria-live", "polite");
    row.appendChild(input); row.appendChild(btn);
    wrap.appendChild(label); wrap.appendChild(row); wrap.appendChild(msg);

    function submit() {
      var email = input.value.trim();
      msg.textContent = ""; msg.className = "alert-signup__msg";
      if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        msg.textContent = "Enter a valid email.";
        msg.classList.add("alert-signup__msg--err"); return;
      }
      btn.disabled = true; btn.textContent = "Sending…";
      fetch("https://api.boardmonitor.app", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email })
      }).then(function(r){ return r.json().then(function(d){ return {ok:r.ok,d:d}; }); })
        .then(function(res){
          if (res.ok || (res.d && res.d.error && res.d.error.code === "MEMBER_EXISTS_WITH_EMAIL_ADDRESS")) {
            input.value = ""; msg.textContent = "You're subscribed!";
            msg.classList.add("alert-signup__msg--ok");
          } else { throw new Error((res.d && res.d.error && res.d.error.message) || "Signup failed"); }
        })
        .catch(function(e){
          msg.textContent = e.message || "Something went wrong.";
          msg.classList.add("alert-signup__msg--err");
        })
        .finally(function(){ btn.disabled = false; btn.textContent = "Notify me"; });
    }
    btn.addEventListener("click", submit);
    input.addEventListener("keydown", function(e){ if (e.key === "Enter") submit(); });
    return wrap;
  }

  function renderMeetings(node, m) {
    node.innerHTML = "";
    if (!m) { node.appendChild(el("p", "err", "Meeting data unavailable.")); return; }
    var hasNext = !!m.next;
    if (hasNext) {
      node.appendChild(buildHighlightBox("Next meeting", m.next, false));
      node.appendChild(buildHighlightBox("Last meeting", m.last, false));
    } else {
      // No upcoming meeting — show last meeting full-width with a no-upcoming note
      var single = buildHighlightBox("Last meeting", m.last, false);
      single.style.gridColumn = "1 / -1";
      node.appendChild(single);
      var noNext = el("p", "meetings__hint meetings__hint--nonext", "No upcoming meeting currently scheduled. Check back closer to the next board meeting date.");
      node.appendChild(noNext);
    }
    var hint = el("p", "meetings__hint", "Select a meeting to expand its highlights.");
    node.appendChild(hint);
    node.appendChild(buildAlertSignup());
  }

  function renderPerformance(node, p) {
    node.innerHTML = "";
    if (!p || !p.grade) { node.appendChild(el("p", "err", "Performance data unavailable.")); return; }

    var grid = el("div", "perf-grid");

    // Grade tile — spans as first cell, styled distinctly
    var gradeTile = el("div", "perf-tile perf-tile--grade");
    gradeTile.appendChild(el("div", "perf-grade grade-ltr--" + esc(p.grade), esc(p.grade)));
    gradeTile.appendChild(el("div", "perf-tile__label", "TEA Grade"));
    gradeTile.appendChild(el("div", "perf-tile__sub", esc(p.school_year) + " · Overall Accountability Rating"));
    grid.appendChild(gradeTile);

    // Metric tiles
    (p.metrics || []).forEach(function (m) {
      var tile = el("div", "perf-tile");
      var val = m.value != null ? (Math.round(m.value * 10) / 10) + "%" : "—";
      tile.appendChild(el("div", "perf-tile__val", esc(val)));
      tile.appendChild(el("div", "perf-tile__label", esc(m.label)));
      if (m.sub) tile.appendChild(el("div", "perf-tile__sub", esc(m.sub)));

      if (m.trend != null) {
        var lib     = !!m.lower_is_better;
        var better  = lib ? m.trend < 0 : m.trend > 0;
        var worse   = lib ? m.trend > 0 : m.trend < 0;
        var arrow   = m.trend > 0 ? "↑" : m.trend < 0 ? "↓" : "→";
        var cls     = "perf-tile__trend " + (better ? "perf-tile__trend--up" : worse ? "perf-tile__trend--down" : "perf-tile__trend--neutral");
        var trendTxt = (m.trend > 0 ? "+" : "") + m.trend.toFixed(1) + " pp " + arrow;
        tile.appendChild(el("span", cls, esc(trendTxt)));
      }
      grid.appendChild(tile);
    });

    node.appendChild(grid);
    var hint = el("p", "meetings__hint", "Source: TEA TAPR · " + esc(p.school_year) + " school year");
    hint.style.marginTop = "var(--sp-3)";
    node.appendChild(hint);
  }

  function setLink(name, url) {
    if (!url) return;
    var a = document.querySelector('[data-link="' + name + '"]');
    if (a) a.href = url;
  }

  function fmtStamp(iso) {
    if (!iso) return null;
    var d = new Date(iso);
    if (isNaN(d)) return null;
    return d.toLocaleString("en-US", {
      month: "short", day: "numeric", year: "numeric",
      hour: "numeric", minute: "2-digit", timeZoneName: "short"
    });
  }

  fetch("data/summary.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (data) {
      var s = data.sites || {};
      if (s.meetings)    { renderMeetings(document.getElementById("meetings-body"), s.meetings); setLink("meetings", s.meetings.url); }
      if (s.performance) { renderPerformance(document.getElementById("performance-body"), s.performance); setLink("performance", s.performance.url); }
      if (s.finance)     { renderMetrics(document.getElementById("finance-metrics"), s.finance.metrics, s.finance.url); setLink("finance", s.finance.url); }
      if (s.policy)      { renderMetrics(document.getElementById("policy-metrics"), s.policy.metrics, s.policy.url); setLink("policy", s.policy.url); }
      if (s.books)       { renderMetrics(document.getElementById("books-metrics"), s.books.metrics, s.books.url); setLink("books", s.books.url); }

      var stamp = fmtStamp(data.generated_at);
      if (stamp) {
        var note = el("p", "foot__note", "Data refreshed " + esc(stamp) + ".");
        document.getElementById("foot-note").after(note);
      }
    })
    .catch(function (e) {
      ["meetings-body", "performance-body", "finance-metrics", "policy-metrics", "books-metrics"].forEach(function (id) {
        var n = document.getElementById(id);
        if (n) n.innerHTML = '<p class="err">Could not load data (' + esc(e.message) + ').</p>';
      });
    });
})();
