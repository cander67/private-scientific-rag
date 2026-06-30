/* Shared mockup behavior — vanilla, no dependencies.
   Progressive: pages render fine if this never runs. */

(function () {
  "use strict";

  // ---- Theme ----
  var root = document.documentElement;
  var stored = null;
  try {
    stored = localStorage.getItem("mml-theme");
  } catch (e) {
    stored = null;
  }
  var prefersDark =
    window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  var theme = stored || (prefersDark ? "dark" : "light");
  applyTheme(theme);

  function applyTheme(t) {
    root.setAttribute("data-theme", t);
    document.querySelectorAll("[data-theme-label]").forEach(function (el) {
      el.textContent = t === "dark" ? "Light" : "Dark";
    });
  }

  function toggleTheme() {
    theme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("mml-theme", theme);
    } catch (e) {
      /* ignore */
    }
    applyTheme(theme);
  }

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-action]");
    if (!t) return;
    var action = t.getAttribute("data-action");

    if (action === "toggle-theme") {
      toggleTheme();
    } else if (action === "toggle-nav") {
      document.body.classList.toggle("nav-open");
    } else if (action === "close-nav") {
      document.body.classList.remove("nav-open");
    } else if (action === "open-modal") {
      var m = document.getElementById(t.getAttribute("data-target"));
      if (m) m.classList.add("open");
    } else if (action === "close-modal") {
      var ov = t.closest(".overlay");
      if (ov) ov.classList.remove("open");
    } else if (action === "tab") {
      selectTab(t);
    } else if (action === "accordion") {
      toggleAccordion(t);
    }
  });

  // close overlay on backdrop click
  document.addEventListener("click", function (e) {
    if (e.target.classList && e.target.classList.contains("overlay")) {
      e.target.classList.remove("open");
    }
  });

  // Esc closes overlays + mobile nav
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      document.querySelectorAll(".overlay.open").forEach(function (o) {
        o.classList.remove("open");
      });
      document.body.classList.remove("nav-open");
    }
  });

  // ---- Tabs ----
  function selectTab(btn) {
    var group = btn.closest(".tabbed");
    if (!group) return;
    group.querySelectorAll("[data-action='tab']").forEach(function (b) {
      b.setAttribute("aria-selected", b === btn ? "true" : "false");
    });
    var target = btn.getAttribute("data-target");
    group.querySelectorAll(".tab-panel").forEach(function (p) {
      p.classList.toggle("active", p.id === target);
    });
  }

  // ---- Accordion ----
  function toggleAccordion(head) {
    var expanded = head.getAttribute("aria-expanded") === "true";
    head.setAttribute("aria-expanded", expanded ? "false" : "true");
    var body = head.nextElementSibling;
    if (body) body.classList.toggle("open", !expanded);
  }

  // ---- Active nav by filename ----
  var here = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav a").forEach(function (a) {
    var href = a.getAttribute("href");
    if (href === here) a.classList.add("active");
  });

  // ---- Segmented controls (visual only) ----
  document.querySelectorAll(".segmented").forEach(function (seg) {
    seg.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      seg.querySelectorAll("button").forEach(function (x) {
        x.setAttribute("aria-pressed", x === b ? "true" : "false");
      });
    });
  });
})();
