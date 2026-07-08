/**
 * ctfd_cybercollab_theme - hero network signature
 * ---------------------------------------------
 * Ambient node-network animation for the homepage hero only. Represents
 * the platform's core idea (universities as connected nodes) without being
 * a generic particle effect - nodes are sparse, connections fade with
 * distance, motion is slow and quiet. Plain canvas 2D, no 3D libs.
 *
 * Only runs on the homepage hero (#cc-network-canvas) and respects
 * prefers-reduced-motion (CSS already hides the canvas; this also bails
 * out of the animation loop as a defense-in-depth measure).
 */
(function () {
  function isHomepage() {
    var p = window.location.pathname.replace(/\/+$/, "");
    return p === "" || p === "/index";
  }

  function initNetworkCanvas(attemptsLeft) {
    if (attemptsLeft === undefined) attemptsLeft = 20; // ~1s total at 50ms/try
    if (!isHomepage()) return;

    var canvas = document.getElementById("cc-network-canvas");
    if (!canvas) {
      if (attemptsLeft <= 0) return; // landing.js likely failed to inject; give up quietly
      setTimeout(function () { initNetworkCanvas(attemptsLeft - 1); }, 50);
      return;
    }

    var prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReducedMotion) return;

    var ctx = canvas.getContext("2d");
    var width, height, nodes;
    var NODE_COUNT = 22;
    var LINK_DIST = 150;

    function resize() {
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    }

    function makeNodes() {
      nodes = [];
      for (var i = 0; i < NODE_COUNT; i++) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.15,
          vy: (Math.random() - 0.5) * 0.15,
        });
      }
    }

    function step() {
      ctx.clearRect(0, 0, width, height);

      nodes.forEach(function (n) {
        n.x += n.vx;
        n.y += n.vy;
        if (n.x < 0 || n.x > width) n.vx *= -1;
        if (n.y < 0 || n.y > height) n.vy *= -1;
      });

      for (var i = 0; i < nodes.length; i++) {
        for (var j = i + 1; j < nodes.length; j++) {
          var dx = nodes[i].x - nodes[j].x;
          var dy = nodes[i].y - nodes[j].y;
          var dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < LINK_DIST) {
            ctx.strokeStyle = "rgba(0, 217, 192, " + (1 - dist / LINK_DIST) * 0.35 + ")";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
          }
        }
      }

      nodes.forEach(function (n) {
        ctx.fillStyle = "rgba(0, 217, 192, 0.8)";
        ctx.beginPath();
        ctx.arc(n.x, n.y, 2, 0, Math.PI * 2);
        ctx.fill();
      });

      requestAnimationFrame(step);
    }

    resize();
    makeNodes();
    window.addEventListener("resize", function () {
      resize();
      makeNodes();
    });
    requestAnimationFrame(step);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initNetworkCanvas);
  } else {
    initNetworkCanvas();
  }
})();
