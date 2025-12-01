(function () {
  const STORAGE_KEY = "media_server_theme";
  const root = document.documentElement;

  function getPreferredTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  }

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    const toggles = document.querySelectorAll("#theme-toggle");
    toggles.forEach((toggle) => {
      const iconEl = toggle.querySelector("[data-theme-icon]");
      const labelEl = toggle.querySelector("[data-theme-label]");
      if (iconEl && labelEl) {
        if (theme === "dark") {
          iconEl.textContent = "🌙";
          labelEl.textContent = "Dark";
        } else {
          iconEl.textContent = "☀️";
          labelEl.textContent = "Light";
        }
      }
    });
  }

  function toggleTheme() {
    const current = root.getAttribute("data-theme") || getPreferredTheme();
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(getPreferredTheme());
    document.querySelectorAll("#theme-toggle").forEach((toggle) => {
      toggle.addEventListener("click", toggleTheme);
    });
  });
})();
