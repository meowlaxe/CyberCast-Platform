/**
 * ctfd_cybercollab_theme - landing page content injector
 * ----------------------------------------------------------
 * Modified: 2026-07-15  — Show logged-in hero variant with correct CTAs;
 *                          show "Welcome back!" toast when arriving from /login.
 * Original: injects hero + feature card grid on the homepage only,
 * PREPENDED before whatever content the admin already wrote in CTFd's
 * Pages editor (nothing existing gets removed or hidden).
 */
(function () {
  /* ── Helpers ── */

  function isHomepage() {
    var p = window.location.pathname.replace(/\/+$/, "");
    return p === "" || p === "/index";
  }

  function isLoggedIn() {
    return window.init && window.init.userId && window.init.userId > 0;
  }

  function getUserName() {
    return (window.init && window.init.userName) ? window.init.userName : "there";
  }

  /**
   * Show a brief toast at the bottom of the screen.
   * Auto-dismisses after 4 s.
   */
  function showToast(message, type) {
    type = type || "success";
    var toast = document.createElement("div");
    toast.className = "cc-toast cc-toast--" + type;
    toast.innerHTML =
      '<span class="cc-toast-icon"><i class="fas ' +
      (type === "success" ? "fa-check-circle" : "fa-info-circle") +
      '"></i></span>' +
      '<span class="cc-toast-msg">' + message + "</span>";

    toast.style.cssText = [
      "position:fixed",
      "bottom:24px",
      "left:50%",
      "transform:translateX(-50%) translateY(80px)",
      "z-index:9999",
      "display:flex",
      "align-items:center",
      "gap:10px",
      "padding:12px 24px",
      "border-radius:8px",
      "font-size:0.95rem",
      "font-weight:500",
      "box-shadow:0 4px 20px rgba(0,0,0,0.4)",
      "transition:transform 0.35s cubic-bezier(.175,.885,.32,1.275), opacity 0.3s",
      "opacity:0",
      "background:" + (type === "success" ? "#00c896" : "#4f7cff"),
      "color:#fff",
    ].join(";");

    document.body.appendChild(toast);

    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        toast.style.opacity = "1";
        toast.style.transform = "translateX(-50%) translateY(0)";
      });
    });

    setTimeout(function () {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(-50%) translateY(80px)";
      setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 350);
    }, 4000);
  }

  /**
   * Show "Welcome back!" toast once per login.
   * cc_login_pending is set by the submit handler in login.html.
   */
  function maybeShowLoginToast() {
    if (!isLoggedIn()) return;

    var fromLogin =
      sessionStorage.getItem("cc_login_pending") === "1" ||
      document.referrer.indexOf("/login") !== -1;

    if (fromLogin) {
      sessionStorage.removeItem("cc_login_pending");
      showToast("Welcome back, " + getUserName() + "! ✔", "success");
    }
  }

  /* ── Hero HTML builders ── */

  function buildLoggedOutHero() {
    return (
      '<div class="cc-hero">' +
      '<canvas id="cc-network-canvas"></canvas>' +
      '<div class="cc-hero-content">' +
      '<div class="cc-hero-icon"><i class="fas fa-shield-alt"></i></div>' +
      '<h1 class="cc-hero-title">Learn. Collaborate. <span class="cc-accent-text">Defend.</span></h1>' +
      '<p class="cc-hero-subtitle">' +
      "A cybersecurity platform built for the long run — structured learning paths, " +
      "real enterprise bounty programs, and collaboration across universities, not just a single event." +
      "</p>" +
      '<div class="cc-hero-ctas">' +
      '<a href="/register" class="btn btn-primary btn-lg">Get Started</a>' +
      '<a href="/challenges" class="btn btn-outline-primary btn-lg">View Challenges</a>' +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function buildLoggedInHero() {
    var name = getUserName();
    return (
      '<div class="cc-hero cc-hero--authed">' +
      '<canvas id="cc-network-canvas"></canvas>' +
      '<div class="cc-hero-content">' +
      '<div class="cc-hero-icon"><i class="fas fa-user-shield"></i></div>' +
      '<h1 class="cc-hero-title">Welcome back, <span class="cc-accent-text">' +
      name +
      "</span></h1>" +
      '<p class="cc-hero-subtitle">' +
      "Pick up where you left off — your learning path, team projects, and bounty programs are waiting." +
      "</p>" +
      '<div class="cc-hero-ctas">' +
      '<a href="/users/me" class="btn btn-primary btn-lg"><i class="fas fa-tachometer-alt me-2"></i>My Dashboard</a>' +
      '<a href="/challenges" class="btn btn-outline-primary btn-lg">Challenges</a>' +
      '<a href="/plugins/platform-plus/bounty" class="btn btn-outline-secondary btn-lg">Bounty Programs</a>' +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  /* ── Feature cards ── */

  var FEATURES_HTML =
    '<div class="cc-features">' +
    '<h2 class="cc-features-title">Platform <span class="cc-accent-text">Features</span></h2>' +
    '<div class="cc-features-grid">' +
    '<a class="cc-feature-card" href="/plugins/platform-plus/learning-paths">' +
    '<div class="cc-feature-icon"><i class="fas fa-graduation-cap"></i></div>' +
    "<h3>Learning Paths</h3>" +
    "<p>Structured curriculum across web, pwn, crypto and more — progress tracked automatically as you solve challenges.</p>" +
    "</a>" +
    '<a class="cc-feature-card" href="/plugins/platform-plus/organizations">' +
    '<div class="cc-feature-icon"><i class="fas fa-university"></i></div>' +
    "<h3>University Collaboration</h3>" +
    "<p>Connect with teams across universities and companies — not limited to a single campus or a single event.</p>" +
    "</a>" +
    '<a class="cc-feature-card cc-feature-card--bounty" href="/plugins/platform-plus/bounty">' +
    '<div class="cc-feature-icon"><i class="fas fa-dollar-sign"></i></div>' +
    "<h3>Enterprise Bounty</h3>" +
    "<p>Real bug bounty programs from partner companies — report findings, earn rewards.</p>" +
    "</a>" +
    '<a class="cc-feature-card" href="/plugins/platform-plus/team-finder">' +
    '<div class="cc-feature-icon"><i class="fas fa-user-friends"></i></div>' +
    "<h3>Find a Team</h3>" +
    "<p>Match with teammates across universities for your next competition or research project.</p>" +
    "</a>" +
    "</div>" +
    "</div>";

  /* ── Main inject ── */

  function buildLanding() {
    var wrapper = document.createElement("div");
    wrapper.className = "cc-landing";
    wrapper.innerHTML =
      (isLoggedIn() ? buildLoggedInHero() : buildLoggedOutHero()) +
      FEATURES_HTML;
    return wrapper;
  }

  function inject() {
    if (!isHomepage()) return;
    if (document.querySelector(".cc-landing")) return;
    // Role-setup redirect is now handled server-side in __init__.py before_request hook.

    var main = document.querySelector("main[role='main']");
    if (!main) return;

    main.insertBefore(buildLanding(), main.firstChild);
    maybeShowLoginToast();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  } else {
    inject();
  }
})();
