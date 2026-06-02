/* CISD Hub — renders docs/data/summary.json into the launchpad. Vanilla JS. */
(function () {
  "use strict";

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

  function renderMetrics(node, metrics) {
    node.innerHTML = "";
    if (!metrics || !metrics.length) { node.appendChild(el("p", "err", "No data available.")); return; }
    metrics.forEach(function (m) {
      var cell = el("div", "metric");
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
    var when = mtg.date_display || "";
    if (mtg.item_count) when += " · " + mtg.item_count + " agenda items";
    meta.appendChild(el("div", "hl__when", esc(when)));
    btn.appendChild(meta);
    btn.appendChild(el("span", "hl__chev", "▾"));
    box.appendChild(btn);

    var body = el("div", "hl__body");
    body.id = bodyId;
    var ul = el("ul");
    (mtg.highlights || []).forEach(function (h) { ul.appendChild(el("li", null, mdInline(h))); });
    if (!(mtg.highlights || []).length) ul.appendChild(el("li", null, "Highlights not yet available."));
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

  function renderMeetings(node, m) {
    node.innerHTML = "";
    if (!m) { node.appendChild(el("p", "err", "Meeting data unavailable.")); return; }
    node.appendChild(buildHighlightBox("Next meeting", m.next, true));
    node.appendChild(buildHighlightBox("Last meeting", m.last, false));
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
      if (s.meetings) { renderMeetings(document.getElementById("meetings-body"), s.meetings); setLink("meetings", s.meetings.url); }
      if (s.finance) { renderMetrics(document.getElementById("finance-metrics"), s.finance.metrics); setLink("finance", s.finance.url); }
      if (s.policy) { renderMetrics(document.getElementById("policy-metrics"), s.policy.metrics); setLink("policy", s.policy.url); }
      if (s.books) { renderMetrics(document.getElementById("books-metrics"), s.books.metrics); setLink("books", s.books.url); }

      var stamp = fmtStamp(data.generated_at);
      if (stamp) {
        var note = el("p", "foot__note", "Data refreshed " + esc(stamp) +
          ". Figures sourced from the linked watchdog sites; every record traces to a primary document.");
        document.getElementById("foot-note").after(note);
      }
    })
    .catch(function (e) {
      ["meetings-body", "finance-metrics", "policy-metrics", "books-metrics"].forEach(function (id) {
        var n = document.getElementById(id);
        if (n) n.innerHTML = '<p class="err">Could not load data (' + esc(e.message) + ').</p>';
      });
    });
})();
