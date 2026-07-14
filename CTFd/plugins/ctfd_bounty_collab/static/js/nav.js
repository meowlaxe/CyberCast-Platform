// =============================================================================
// File: CTFd/plugins/ctfd_bounty_collab/static/js/nav.js
// Plugin: ctfd_bounty_collab
// Created: 2026-07-15  Author: Claude / CyberCast implementation
// Purpose: Inject "Bounty Collab" link into CTFd's main navigation bar.
//          Mirrors the pattern used by ctfd_bounty/static/js/nav.js.
// =============================================================================

(function () {
  "use strict";

  function injectNavLink() {
    var nav = document.querySelector("ul.navbar-nav");
    if (!nav) return;

    // Guard against double-injection on SPA navigations
    if (document.querySelector("[data-bntc-nav]")) return;

    var li = document.createElement("li");
    li.className = "nav-item";
    li.setAttribute("data-bntc-nav", "true");

    var a = document.createElement("a");
    a.className = "nav-link";
    a.href = "/plugins/bounty-collab/";
    a.textContent = "Bounty Collab";

    li.appendChild(a);
    nav.appendChild(li);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectNavLink);
  } else {
    injectNavLink();
  }
})();
