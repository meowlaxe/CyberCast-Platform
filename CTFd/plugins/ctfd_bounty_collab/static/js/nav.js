// =============================================================================
// File: CTFd/plugins/ctfd_bounty_collab/static/js/nav.js
// Plugin: ctfd_bounty_collab
// Created: 2026-07-15  Author: Claude / CyberCast implementation
// Modified: 2026-07-15  — Role-aware nav injection.
//   student  → no Bounty link (bounty not available for students)
//   expert   → "Bounty" link to project list
//   partner  → "Bounty" link to project list (their own projects)
//   no role  → "Set Up Profile" link to /setup-role
//   admin    → "Bounty" link always shown
// =============================================================================

(function () {
  "use strict";

  function appendNavItem(nav, href, text, color) {
    var li = document.createElement("li");
    li.className = "nav-item";
    li.setAttribute("data-bntc-nav", "true");
    var a = document.createElement("a");
    a.className = "nav-link";
    a.href = href;
    a.textContent = text;
    if (color) a.style.color = color;
    li.appendChild(a);
    nav.appendChild(li);
  }

  function injectNavLink(role, needsSetup) {
    var nav = document.querySelector("ul.navbar-nav");
    if (!nav) return;
    if (document.querySelector("[data-bntc-nav]")) return;

    if (needsSetup) {
      appendNavItem(nav, "/plugins/bounty-collab/setup-role", "Set Up Profile", "#ffc107");
      return;
    }

    // Bounty link for everyone with a role (not students)
    appendNavItem(nav, "/plugins/bounty-collab/", "Bounty", null);
  }

  var CACHE_KEY = "bntc_role";
  var CACHE_TTL = 5 * 60 * 1000; // 5 minutes

  function getCached(userId) {
    try {
      var raw = sessionStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      var obj = JSON.parse(raw);
      if (obj.uid !== userId) return null;
      if (Date.now() - obj.ts > CACHE_TTL) return null;
      return obj.data;
    } catch (e) { return null; }
  }

  function setCached(userId, data) {
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ uid: userId, ts: Date.now(), data: data }));
    } catch (e) {}
  }

  function applyRole(d) {
    if (!d) return;
    if (d.role === "student") return;
    injectNavLink(d.role, d.needs_setup);
  }

  function init() {
    var userId = window.init && window.init.userId;
    if (!userId) return;

    // Use cache so we don't hit the DB on every page navigation
    var cached = getCached(userId);
    if (cached) {
      applyRole(cached);
      return;
    }

    fetch("/plugins/bounty-collab/me/role", { credentials: "same-origin" })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(d) {
      if (!d) return;
      setCached(userId, d);
      applyRole(d);
    })
    .catch(function() {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
