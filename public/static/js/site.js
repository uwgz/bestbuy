// Best Buy 250 — small progressive enhancements (the site works without JS)
document.addEventListener("DOMContentLoaded", () => {
  // ---------- Phone menu ----------
  const toggle = document.querySelector(".nav-toggle");
  const links = document.getElementById("nav-links");
  if (toggle && links) {
    const setOpen = open => {
      links.classList.toggle("open", open);
      toggle.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open);
      document.body.classList.toggle("menu-open", open);
    };
    toggle.addEventListener("click", () => setOpen(!links.classList.contains("open")));
    links.querySelectorAll("a").forEach(a => a.addEventListener("click", () => setOpen(false)));
    document.addEventListener("keydown", e => { if (e.key === "Escape") setOpen(false); });
  }

  // ---------- Flash messages ----------
  document.querySelectorAll(".flash").forEach(f => {
    const close = () => { f.style.transition = "opacity .3s"; f.style.opacity = 0; setTimeout(() => f.remove(), 300); };
    f.querySelector(".flash-close")?.addEventListener("click", close);
    setTimeout(close, 5000);
  });

  // ---------- Portfolio filter ----------
  const filter = document.getElementById("portfolio-filter");
  if (filter) {
    filter.addEventListener("click", e => {
      const btn = e.target.closest(".chip");
      if (!btn) return;
      filter.querySelectorAll(".chip").forEach(c => c.classList.toggle("active", c === btn));
      const cat = btn.dataset.filter;
      document.querySelectorAll(".gallery-item").forEach(item =>
        item.classList.toggle("hidden", cat !== "all" && item.dataset.category !== cat));
    });
  }

  // ---------- Fade content in as it scrolls into view ----------
  if ("IntersectionObserver" in window) {
    const els = document.querySelectorAll(".tile-copy, .tile-media, .shelf-card, .product-card, .service-card, .gear-card, .gallery-item, .steps li");
    const io = new IntersectionObserver(entries => {
      entries.forEach(en => { if (en.isIntersecting) { en.target.classList.add("visible"); io.unobserve(en.target); } });
    }, { threshold: 0.08 });
    els.forEach(el => { el.classList.add("reveal"); io.observe(el); });
  }

  // ---------- Booking: no past dates ----------
  const date = document.querySelector('input[type="date"][name="date"]');
  if (date) date.min = new Date().toISOString().split("T")[0];

  // ---------- Admin: show chosen file ----------
  document.querySelectorAll(".file-btn input").forEach(inp => {
    inp.addEventListener("change", () => {
      if (!inp.files[0]) return;
      inp.parentElement.classList.add("chosen");
      inp.parentElement.firstChild.textContent = "✓ " + inp.files[0].name.slice(0, 18);
    });
  });

  // ---------- Product page gallery ----------
  const main = document.getElementById("main-photo");
  const thumbs = [...document.querySelectorAll("#thumbs .thumb")];
  const dotsPd = [...document.querySelectorAll(".pd-dot")];
  if (main && thumbs.length > 1) {
    let t = 0;
    const showPhoto = n => {
      t = (n + thumbs.length) % thumbs.length;
      main.style.opacity = 0;
      setTimeout(() => { main.src = thumbs[t].dataset.src; main.style.opacity = 1; }, 150);
      thumbs.forEach((el, k) => el.classList.toggle("active", k === t));
      dotsPd.forEach((el, k) => el.classList.toggle("active", k === t));
    };
    thumbs.forEach((el, k) => el.addEventListener("click", () => showPhoto(k)));
    let x0 = null;
    const wrap = document.getElementById("main-photo-wrap");
    wrap.addEventListener("touchstart", e => { x0 = e.touches[0].clientX; }, { passive: true });
    wrap.addEventListener("touchend", e => {
      if (x0 === null) return;
      const dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 40) showPhoto(t + (dx < 0 ? 1 : -1));
      x0 = null;
    });
  }

  // ---------- Product page: share and like ----------
  const toastEl = document.getElementById("pd-toast");
  const toast = msg => {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastEl._t);
    toastEl._t = setTimeout(() => toastEl.classList.remove("show"), 1800);
  };
  const shareBtn = document.getElementById("pd-share");
  if (shareBtn) {
    shareBtn.addEventListener("click", async () => {
      const data = { title: shareBtn.dataset.title, url: location.href.split("#")[0] };
      if (navigator.share) {
        try { await navigator.share(data); } catch (e) { /* closed the share sheet */ }
        return;
      }
      try { await navigator.clipboard.writeText(data.url); toast("Link copied"); }
      catch (e) { toast("Copy the link from the address bar"); }
    });
  }
  const likeBtn = document.getElementById("pd-like");
  if (likeBtn) {
    // liked products are remembered on this phone or computer only
    const read = () => { try { return JSON.parse(localStorage.getItem("liked") || "[]"); } catch (e) { return []; } };
    const id = Number(likeBtn.dataset.id);
    const paint = on => likeBtn.setAttribute("aria-pressed", on ? "true" : "false");
    paint(read().includes(id));
    likeBtn.addEventListener("click", () => {
      let list = read();
      const on = !list.includes(id);
      list = on ? [...list, id] : list.filter(x => x !== id);
      try { localStorage.setItem("liked", JSON.stringify(list)); } catch (e) { /* private mode */ }
      paint(on);
      toast(on ? "Added to your likes" : "Removed from your likes");
    });
  }

  // ---------- Home gallery carousel: centred slide, neighbours peeking, dots + pause ----------
  const root = document.getElementById("gallery");
  if (root) {
    const track = root.querySelector(".gallery-track");
    const slides = [...root.querySelectorAll(".gallery-slide")];
    const dots = [...root.querySelectorAll(".dot")];
    const pauseBtn = root.querySelector(".slider-pause");
    let i = 0;

    const position = () => {
      const s = slides[i];
      const offset = s.offsetLeft - (root.clientWidth - s.offsetWidth) / 2;
      track.style.transform = `translateX(${-offset}px)`;
    };
    const show = n => {
      i = (n + slides.length) % slides.length;
      slides.forEach((s, k) => { s.classList.toggle("active", k === i); s.inert = k !== i; });
      dots.forEach((d, k) => {
        d.classList.toggle("active", k === i);
        d.setAttribute("aria-current", k === i ? "true" : "false");
        const f = d.querySelector(".fill");
        f.style.animation = "none"; f.offsetWidth; f.style.animation = "";   // restart progress
      });
      position();
    };
    const setPaused = p => {
      root.classList.toggle("paused", p);
      pauseBtn.setAttribute("aria-label", p ? "Play slideshow" : "Pause slideshow");
    };

    dots.forEach((d, k) => {
      d.querySelector(".fill").addEventListener("animationend", () => { if (k === i) show(i + 1); });
      d.addEventListener("click", () => show(k));
    });
    slides.forEach((s, k) => s.addEventListener("click", e => { if (k !== i) { e.preventDefault(); show(k); } }));
    pauseBtn.addEventListener("click", () => setPaused(!root.classList.contains("paused")));
    window.addEventListener("resize", position);

    let x0 = null;
    root.addEventListener("touchstart", e => { x0 = e.touches[0].clientX; }, { passive: true });
    root.addEventListener("touchend", e => {
      if (x0 === null) return;
      const dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 50) show(i + (dx < 0 ? 1 : -1));
      x0 = null;
    });

    // only play while visible on screen
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(([en]) => root.classList.toggle("offscreen", !en.isIntersecting), { threshold: 0.3 }).observe(root);
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) setPaused(true);
    show(0);
  }
});

// Photography page: swipeable service galleries with dots
document.querySelectorAll(".svc-gallery").forEach(g => {
  const track = g.querySelector(".svc-track");
  const dots = [...g.querySelectorAll(".svc-dot")];
  if (!dots.length) return;
  const sync = () => {
    const i = Math.round(track.scrollLeft / track.clientWidth);
    dots.forEach((d, k) => d.classList.toggle("active", k === i));
  };
  track.addEventListener("scroll", () => requestAnimationFrame(sync), { passive: true });
  dots.forEach((d, k) => d.addEventListener("click", () => track.scrollTo({ left: k * track.clientWidth, behavior: "smooth" })));
});

// Day / night tab (phones): choice lasts until the tab/browser is closed
(() => {
  const buttons = document.querySelectorAll(".theme-tab, .theme-btn");   // side tab (phones) + top bar (large screens)
  if (!buttons.length) return;
  const root = document.documentElement;
  const isDark = () => root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  const paintBar = () => document.querySelectorAll('meta[name="theme-color"]').forEach(m => {
    m.setAttribute("content", isDark() ? "#000000" : "#ffffff"); m.removeAttribute("media");
  });
  if (root.dataset.theme) paintBar();
  buttons.forEach(tab => tab.addEventListener("click", () => {
    const next = isDark() ? "light" : "dark";
    root.dataset.theme = next;
    try { sessionStorage.setItem("theme", next); } catch (e) {}
    paintBar();
    tab.classList.add("spin"); setTimeout(() => tab.classList.remove("spin"), 450);
  }));
})();


/* Logo animations (top bar, error pages): the two small lines light up red in turn, like a signal.
   People who turn off motion on their device see the still emblem. */
if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.querySelectorAll(".logo-mark, .error-mark").forEach(svg => {
    if (svg.pauseAnimations) { svg.pauseAnimations(); svg.setCurrentTime(0); }
  });
}

/* ---------- Giveaway ----------
   While a giveaway runs, the page asks the server (now, then every 45 s while open) whether this
   visitor has won. The server decides; a win comes back with a unique code. The win is kept on the
   device so the "Your prize" button can show it again until the claim deadline. */
(function () {
  const KEY = "ve-prize";
  const body = document.body;
  const fmt = iso => new Date(iso).toLocaleString(undefined, { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
  const esc = t => String(t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function saved() {
    try {
      const w = JSON.parse(localStorage.getItem(KEY) || "null");
      if (w && new Date(w.claim_by) > new Date()) return w;
      localStorage.removeItem(KEY);
    } catch (e) { /* storage unavailable */ }
    return null;
  }
  function keep(w) { try { localStorage.setItem(KEY, JSON.stringify(w)); } catch (e) { /* ignore */ } }

  function popup(w) {
    document.querySelector(".prize-dialog")?.remove();
    const d = document.createElement("dialog");
    d.className = "prize-dialog";
    d.setAttribute("aria-labelledby", "prize-title");
    d.innerHTML = `
      <div class="prize-burst" aria-hidden="true">${"<i></i>".repeat(14)}</div>
      ${w.test ? '<p class="prize-test">TEST — not a real prize</p>' : ""}
      <p class="prize-eyebrow">Congratulations!</p>
      <h2 id="prize-title" tabindex="-1" autofocus>You've won<br>${w.link
        ? `<a class="prize-name" href="${esc(w.link)}" title="See it in the shop">${esc(w.prize)}</a>`
        : `<span class="prize-name">${esc(w.prize)}</span>`}</h2>
      <p class="prize-code-label">Your winning code</p>
      <button type="button" class="prize-code" title="Copy">${esc(w.code)}</button>
      <p class="prize-how">To collect, show this code at our store or send it to us on WhatsApp
        <b>before ${esc(fmt(w.claim_by))}</b>. Take a screenshot to keep it safe.</p>
      <div class="prize-actions">
        <button type="button" class="btn btn-light prize-close">Close</button>
        ${w.whatsapp ? `<a class="btn prize-wa" href="${esc(w.whatsapp)}" target="_blank" rel="noopener">Claim on WhatsApp</a>` : ""}
      </div>
      <p class="prize-small">Each code works once and is checked in our system. <a href="${esc(w.rules)}">Giveaway rules</a></p>`;
    body.appendChild(d);
    d.querySelector(".prize-close").addEventListener("click", () => d.close());
    d.addEventListener("close", () => { d.remove(); pill(w); });
    d.addEventListener("click", e => { if (e.target === d) d.close(); });
    const codeBtn = d.querySelector(".prize-code");
    codeBtn.addEventListener("click", () => {
      navigator.clipboard?.writeText(w.code).then(() => { codeBtn.classList.add("copied"); setTimeout(() => codeBtn.classList.remove("copied"), 1500); });
    });
    d.showModal();
  }

  function pill(w) {
    if (document.querySelector(".prize-pill")) return;
    const b = document.createElement("button");
    b.type = "button";
    b.className = "prize-pill";
    b.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7M7.5 8a2.5 2.5 0 0 1 0-5C10 3 12 8 12 8s2-5 4.5-5a2.5 2.5 0 0 1 0 5"/></svg>Your prize`;
    b.addEventListener("click", () => { b.remove(); popup(w); });
    body.appendChild(b);
  }

  const already = saved();
  if (already) pill(already);

  const url = body.dataset.giveaway;
  if (!url || already) return;
  let timer = null;
  async function check() {
    if (document.visibilityState !== "visible") return;
    try {
      const r = await fetch(url, { method: "POST", headers: { "X-CSRF-Token": body.dataset.csrf || "" }, credentials: "same-origin" });
      const w = await r.json();
      if (w.won) { clearInterval(timer); if (!w.test) keep(w); popup(w); }
      else if (w.live === false) clearInterval(timer);
    } catch (e) { /* offline: try again later */ }
  }
  setTimeout(check, 1200);
  timer = setInterval(check, 45000);
})();
