// Campus launcher: disclosure navigation, not an operating-system menu.
(function () {
  "use strict";
  // Example tabs indicate the current text without changing the request payload.
  const text = document.getElementById("request-text");
  const examples = document.querySelectorAll("[data-example]");
  function syncExamples() {
    examples.forEach((button) => button.setAttribute("aria-pressed", String(!!text && text.value === button.dataset.example)));
  }
  examples.forEach((button) => button.addEventListener("click", () => { if (text) { text.value = button.dataset.example; syncExamples(); } }));
  if (text) text.addEventListener("input", syncExamples);
  syncExamples();
  // Keep keyboard-focused content controls above the fixed taskbar.
  document.addEventListener("focusin", (event) => {
    if (!event.target.closest || !event.target.closest("#main")) return;
    const bar = document.querySelector(".taskbar");
    const rect = event.target.getBoundingClientRect();
    const lowerEdge = bar ? bar.getBoundingClientRect().top - 12 : window.innerHeight - 12;
    if (rect.bottom > lowerEdge) window.scrollBy({ top: rect.bottom - lowerEdge, behavior: "instant" });
    else if (rect.top < 12) window.scrollBy({ top: rect.top - 12, behavior: "instant" });
  });
  const toggle = document.getElementById("start-toggle");
  const menu = document.getElementById("start-menu");
  if (!toggle || !menu) return;
  function close(restoreFocus) {
    menu.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open Campus menu");
    if (restoreFocus) toggle.focus();
  }
  toggle.addEventListener("click", () => {
    if (!menu.hidden) { close(true); return; }
    menu.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close Campus menu");
    menu.querySelector("a").focus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !menu.hidden) { event.preventDefault(); close(true); }
  });
  document.addEventListener("pointerdown", (event) => {
    if (!menu.hidden && !menu.contains(event.target) && !toggle.contains(event.target)) {
      close(menu.contains(document.activeElement));
    }
  });
  document.addEventListener("focusin", (event) => {
    if (!menu.hidden && !menu.contains(event.target) && !toggle.contains(event.target)) close(false);
  });
  menu.addEventListener("click", (event) => { if (event.target.closest("a")) close(false); });
})();
