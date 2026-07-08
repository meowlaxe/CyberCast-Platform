/**
 * ctfd_cybercollab_theme - landing page content injector
 * ----------------------------------------------------------
 * Injects a hero section + feature card grid on the homepage only,
 * PREPENDED before whatever content the admin already wrote in CTFd's
 * Pages editor (nothing existing gets removed or hidden).
 *
 * Feature cards link to real, working pages built by the sibling plugins
 * (ctfd_organizations, ctfd_bounty, ctfd_team_finder, ctfd_learning_paths)
 * rather than promising features that don't exist yet.
 */
(function () {
  function isHomepage() {
    var p = window.location.pathname.replace(/\/+$/, "");
    return p === "" || p === "/index";
  }

  function buildLanding() {
    var wrapper = document.createElement("div");
    wrapper.className = "cc-landing";
    wrapper.innerHTML = `
      <div class="cc-hero">
        <canvas id="cc-network-canvas"></canvas>
        <div class="cc-hero-content">
          <div class="cc-hero-icon"><i class="fas fa-shield-alt"></i></div>
          <h1 class="cc-hero-title">Learn. Collaborate. <span class="cc-accent-text">Defend.</span></h1>
          <p class="cc-hero-subtitle">
            A cybersecurity platform built for the long run - structured learning paths,
            real enterprise bounty programs, and collaboration across universities,
            not just a single event.
          </p>
          <div class="cc-hero-ctas">
            <a href="/register" class="btn btn-primary btn-lg">Get Started</a>
            <a href="/challenges" class="btn btn-outline-primary btn-lg">View Challenges</a>
          </div>
        </div>
      </div>

      <div class="cc-features">
        <h2 class="cc-features-title">Platform <span class="cc-accent-text">Features</span></h2>
        <div class="cc-features-grid">

          <a class="cc-feature-card" href="/plugins/platform-plus/learning-paths">
            <div class="cc-feature-icon"><i class="fas fa-graduation-cap"></i></div>
            <h3>Learning Paths</h3>
            <p>Structured curriculum across web, pwn, crypto and more - progress
               tracked automatically as you solve real challenges.</p>
          </a>

          <a class="cc-feature-card" href="/plugins/platform-plus/organizations">
            <div class="cc-feature-icon"><i class="fas fa-university"></i></div>
            <h3>University Collaboration</h3>
            <p>Connect with teams across universities and companies - not
               limited to a single campus or a single event.</p>
          </a>

          <a class="cc-feature-card cc-feature-card--bounty" href="/plugins/platform-plus/bounty">
            <div class="cc-feature-icon"><i class="fas fa-dollar-sign"></i></div>
            <h3>Enterprise Bounty</h3>
            <p>Real bug bounty programs from partner companies - report
               findings, earn rewards.</p>
          </a>

          <a class="cc-feature-card" href="/plugins/platform-plus/team-finder">
            <div class="cc-feature-icon"><i class="fas fa-user-friends"></i></div>
            <h3>Find a Team</h3>
            <p>Match with teammates across universities for your next
               competition or research project.</p>
          </a>

        </div>
      </div>
    `;
    return wrapper;
  }

  function inject() {
    if (!isHomepage()) return;
    if (document.querySelector(".cc-landing")) return; // already injected

    var main = document.querySelector("main[role='main']");
    if (!main) return;

    main.insertBefore(buildLanding(), main.firstChild);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  } else {
    inject();
  }
})();
