/**
 * ctfd_organizations - navbar link injector
 * -------------------------------------------
 * Adds its link into a shared "Platform" dropdown (created lazily by
 * whichever sibling plugin's script runs first) instead of a flat
 * top-level nav item - keeps the navbar from overflowing when several
 * of these plugins are installed together. Each plugin still works
 * completely fine on its own if installed alone.
 */
(function () {
  function ensurePlatformDropdown(navList) {
    var toggle = navList.querySelector("#cc-platform-dropdown");
    if (toggle) return toggle.parentElement.querySelector(".dropdown-menu");

    var li = document.createElement("li");
    li.className = "nav-item dropdown";
    li.innerHTML =
      '<a class="nav-link dropdown-toggle" href="#" id="cc-platform-dropdown" ' +
      'role="button" data-bs-toggle="dropdown" aria-expanded="false">Platform</a>' +
      '<ul class="dropdown-menu" aria-labelledby="cc-platform-dropdown"></ul>';
    navList.appendChild(li);
    return li.querySelector(".dropdown-menu");
  }

  function addLink(menu, href, label) {
    if (menu.querySelector('a[href="' + href + '"]')) return;
    var item = document.createElement("li");
    var a = document.createElement("a");
    a.className = "dropdown-item";
    a.href = href;
    a.textContent = label;
    item.appendChild(a);
    menu.appendChild(item);
  }

  function inject() {
    var navList = document.querySelector(".navbar-nav.me-auto");
    if (!navList) return;
    var menu = ensurePlatformDropdown(navList);
    addLink(menu, "/plugins/platform-plus/organizations", "Organizations");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  } else {
    inject();
  }
})();
