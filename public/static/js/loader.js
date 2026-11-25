/* Loading screen: appears when the next page takes more than a moment (e.g. the server waking up),
   and while photos upload in the admin. Quick pages never show it. */
(function () {
  const el = document.getElementById("page-loader");
  if (!el) return;
  const text = el.querySelector(".pl-text");
  const mark = el.querySelector("svg");
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches && mark && mark.pauseAnimations) { mark.pauseAnimations(); mark.setCurrentTime(0); }

  let timer = null, failsafe = null;
  function show(label, delay) {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (text) text.textContent = label || "Loading…";
      el.hidden = false;
      requestAnimationFrame(() => el.classList.add("show"));
      clearTimeout(failsafe);
      failsafe = setTimeout(hide, 15000);   // never leave it up for good
    }, delay);
  }
  function hide() {
    clearTimeout(timer); clearTimeout(window.__plTimer); clearTimeout(failsafe);
    el.classList.remove("show");
    setTimeout(() => { if (!el.classList.contains("show")) el.hidden = true; }, 260);
  }
  window.pageLoader = { show, hide };

  // first visit
  if (document.readyState === "complete") hide(); else window.addEventListener("load", hide);
  // coming back with the Back button, or returning from WhatsApp
  window.addEventListener("pageshow", hide);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") hide(); });

  // links to other pages of this site
  document.addEventListener("click", e => {
    const a = e.target.closest("a[href]");
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target && a.target !== "_self") return;
    if (a.hasAttribute("download") || a.dataset.modal !== undefined) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return;                                  // WhatsApp, Instagram, mail …
    if (url.pathname === location.pathname && url.search === location.search) return;   // same page / #section
    if (url.pathname.startsWith("/media/")) return;                              // a photo opening
    setTimeout(() => { if (!e.defaultPrevented) show("Loading…", 300); }, 0);
  });

  // forms that really send (after every other check has run)
  document.addEventListener("submit", e => {
    const form = e.target;
    setTimeout(() => {
      if (e.defaultPrevented || form.target === "_blank" || form.method.toLowerCase() === "dialog") return;
      const photos = [...form.querySelectorAll("input[type=file]")].some(i => i.files && i.files.length);
      show(photos ? "Uploading photos…" : "Saving…", photos ? 0 : 400);
    }, 0);
  });
})();
