/* Best Buy 250: everything interactive. The cart and likes are kept in this browser (localStorage). */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const body = document.body;
  const store = { name: body.dataset.store, currency: body.dataset.currency, decimals: Number(body.dataset.decimals || 0),
                  whatsapp: (body.dataset.whatsapp || "").replace(/\D/g, "") };
  const money = v => `${store.currency} ${Number(v).toLocaleString("en-US", { minimumFractionDigits: store.decimals, maximumFractionDigits: store.decimals })}`;
  const waLink = text => `https://wa.me/${store.whatsapp}?text=${encodeURIComponent(text)}`;
  const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch (e) { return fallback; } };
  const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ } };

  $$("[data-year]").forEach(el => (el.textContent = new Date().getFullYear()));

  // ---------- toast ----------
  const toastEl = $("[data-toast]");
  const toast = msg => {
    toastEl.textContent = msg;
    toastEl.classList.remove("opacity-0", "translate-y-4");
    clearTimeout(toastEl._t);
    toastEl._t = setTimeout(() => toastEl.classList.add("opacity-0", "translate-y-4"), 1900);
  };

  // ---------- day / night ----------
  $$("[data-theme-toggle]").forEach(btn => btn.addEventListener("click", () => {
    const dark = document.documentElement.classList.toggle("dark");
    try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch (e) {}
  }));

  // ---------- cart (slug -> quantity) ----------
  const getCart = () => read("cart", {});
  const setCart = cart => { write("cart", cart); paintCount(); };
  const paintCount = () => {
    const n = Object.values(getCart()).reduce((a, b) => a + b, 0);
    $$("[data-cart-count]").forEach(el => { el.textContent = n > 99 ? "99+" : n; el.hidden = !n; });
  };
  paintCount();
  window.addEventListener("storage", e => e.key === "cart" && paintCount());   // another tab changed it

  // product page: quantity stepper and "Add to cart"
  const qtyInput = $("[data-qty]");
  $$("[data-step]").forEach(b => b.addEventListener("click", () => {
    const max = Number(qtyInput.max || 99);
    qtyInput.value = Math.min(max, Math.max(1, Number(qtyInput.value || 1) + Number(b.dataset.step)));
  }));
  $$("[data-add]").forEach(btn => btn.addEventListener("click", () => {
    const slug = btn.dataset.add, stock = Number(btn.dataset.stock || 99);
    const cart = getCart();
    const want = (cart[slug] || 0) + Math.max(1, Number(qtyInput?.value || 1));
    cart[slug] = Math.min(want, stock);
    setCart(cart);
    toast(want > stock ? `Only ${stock} in stock: ${stock} in your cart` : "Added to your cart");
  }));

  // cart page
  const cartBox = $("[data-cart]");
  if (cartBox && window.CATALOG) {
    const lines = $("[data-cart-lines]"), tpl = $("template[data-line]");
    const render = () => {
      const cart = getCart();
      Object.keys(cart).forEach(slug => { if (!CATALOG[slug]) delete cart[slug]; });   // products no longer sold
      const slugs = Object.keys(cart);
      lines.innerHTML = "";
      let total = 0;
      const orderLines = [];
      slugs.forEach(slug => {
        const p = CATALOG[slug], qty = cart[slug], line = tpl.content.firstElementChild.cloneNode(true);
        total += p.price * qty;
        orderLines.push(`• ${qty} × ${p.short} (${p.sku}): ${money(p.price * qty)}`);
        $$("[data-link]", line).forEach(a => (a.href = p.url));
        $("[data-img]", line).src = p.image;
        $("[data-name]", line).textContent = p.short;
        $("[data-sku]", line).textContent = `${p.sku} · ${money(p.price)} each`;
        $("[data-qty]", line).textContent = qty;
        $("[data-total]", line).textContent = money(p.price * qty);
        const change = d => { const c = getCart(); c[slug] = Math.min(p.stock, Math.max(1, (c[slug] || 1) + d)); setCart(c); render(); };
        $("[data-minus]", line).onclick = () => change(-1);
        $("[data-plus]", line).onclick = () => { if (qty >= p.stock) toast(`Only ${p.stock} in stock`); change(1); };
        $("[data-remove]", line).onclick = () => { const c = getCart(); delete c[slug]; setCart(c); render(); toast("Removed"); };
        lines.appendChild(line);
      });
      const empty = !slugs.length;
      lines.hidden = empty;
      $("[data-cart-summary]").hidden = empty;
      $("[data-cart-empty]").hidden = !empty;
      $("[data-cart-total]").textContent = money(total);
      $("[data-cart-order]").href = waLink(`Hello ${store.name}! I'd like to order:\n${orderLines.join("\n")}\nTotal: ${money(total)}`);
    };
    render();
  }

  // ---------- product photos: swipe, dots, thumbnails ----------
  const gallery = $("[data-gallery]");
  if (gallery) {
    const track = $("[data-track]", gallery), dots = $$("[data-dot]", gallery), thumbs = $$("[data-thumb]", gallery);
    const on = "bg-zinc-900 dark:bg-white".split(" "), off = "bg-zinc-300 dark:bg-zinc-700".split(" ");
    const paint = i => {
      dots.forEach((d, k) => { d.classList.remove(...(k === i ? off : on)); d.classList.add(...(k === i ? on : off)); });
      thumbs.forEach((t, k) => { t.classList.toggle("border-brand", k === i); t.classList.toggle("border-transparent", k !== i); });
    };
    track.addEventListener("scroll", () => paint(Math.round(track.scrollLeft / track.clientWidth)), { passive: true });
    thumbs.forEach(t => t.addEventListener("click", () => {
      const i = Number(t.dataset.thumb);
      track.scrollTo({ left: i * track.clientWidth, behavior: "smooth" });
      paint(i);
    }));
  }

  // ---------- home slideshow: moves on by itself; the filling dot shows when ----------
  const show = $("[data-slides]");
  if (show) {
    const track = $("[data-slide-track]", show), slides = $$("[data-slide]", show), dots = $$("[data-slide-dot]", show);
    const seconds = Number(show.dataset.seconds || 6);
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;   // no automatic sliding for them
    let current = 0, scrolling = null;

    const center = i => slides[i].offsetLeft - (track.clientWidth - slides[i].clientWidth) / 2;
    const activate = i => {
      current = i;
      slides.forEach((sl, k) => sl.toggleAttribute("data-current", k === i));
      dots.forEach((d, k) => {
        d.toggleAttribute("data-active", k === i);
        d.setAttribute("aria-selected", k === i);
        const fill = $("[data-fill]", d);
        fill.style.animation = "none";
        void fill.offsetWidth;                                  // restart the fill from empty
        fill.style.animation = k === i && !still ? `slide-fill ${seconds}s linear forwards` : "";
        if (k === i && still) fill.style.width = "100%";
        fill.style.animationPlayState = show.matches(":hover") ? "paused" : "running";
      });
    };
    const go = i => {
      i = (i + slides.length) % slides.length;
      track.scrollTo({ left: center(i), behavior: "smooth" });
      activate(i);
    };
    // when the fill reaches the end, the next photo comes
    dots.forEach((d, k) => {
      $("[data-fill]", d).addEventListener("animationend", () => k === current && go(current + 1));
      d.addEventListener("click", () => go(k));
    });
    // swiping: when the track settles, the photo in the middle becomes the current one
    track.addEventListener("scroll", () => {
      clearTimeout(scrolling);
      scrolling = setTimeout(() => {
        const mid = track.scrollLeft + track.clientWidth / 2;
        let best = 0;
        slides.forEach((sl, k) => { if (Math.abs(sl.offsetLeft + sl.clientWidth / 2 - mid) < Math.abs(slides[best].offsetLeft + slides[best].clientWidth / 2 - mid)) best = k; });
        if (best !== current) activate(best);
      }, 120);
    }, { passive: true });
    // pause while the visitor looks closely (mouse over it, finger on it) or the tab is hidden
    const pause = on => dots.forEach(d => ($("[data-fill]", d).style.animationPlayState = on ? "paused" : "running"));
    show.addEventListener("mouseenter", () => pause(true));
    show.addEventListener("mouseleave", () => pause(false));
    show.addEventListener("touchstart", () => pause(true), { passive: true });
    show.addEventListener("touchend", () => pause(false), { passive: true });
    document.addEventListener("visibilitychange", () => pause(document.hidden));
    addEventListener("resize", () => track.scrollTo({ left: center(current) }));
    track.scrollLeft = center(0);
    activate(0);
  }

  // ---------- one-line rows with ‹ › buttons (shop categories) ----------
  $$("[data-scroller]").forEach(box => {
    const track = $("[data-scroll-track]", box), prev = $("[data-scroll-prev]", box), next = $("[data-scroll-next]", box);
    const update = () => {
      const max = track.scrollWidth - track.clientWidth;
      prev.hidden = track.scrollLeft <= 2;            // nothing more to the left
      next.hidden = track.scrollLeft >= max - 2;      // nothing more to the right
    };
    const step = dir => track.scrollBy({ left: dir * track.clientWidth * 0.7, behavior: "smooth" });
    prev.addEventListener("click", () => step(-1));
    next.addEventListener("click", () => step(1));
    track.addEventListener("scroll", update, { passive: true });
    addEventListener("resize", update);
    update();                                         // arrows first: they make the row narrower
    const active = $("[data-active]", track);
    if (active) {                                     // start with the chosen category in the middle of the row
      const t = track.getBoundingClientRect(), a = active.getBoundingClientRect();
      track.style.scrollBehavior = "auto";
      track.scrollLeft += a.left - t.left - (t.width - a.width) / 2;
      track.style.scrollBehavior = "";
    }
    update();
  });

  // ---------- share and like ----------
  $$("[data-share]").forEach(btn => btn.addEventListener("click", async () => {
    const data = { title: btn.dataset.title, url: location.href.split("#")[0] };
    if (navigator.share) { try { await navigator.share(data); } catch (e) {} return; }
    try { await navigator.clipboard.writeText(data.url); toast("Link copied"); } catch (e) { toast("Copy the link from the address bar"); }
  }));
  $$("[data-like]").forEach(btn => {
    const slug = btn.dataset.like;
    btn.setAttribute("aria-pressed", read("liked", []).includes(slug));
    btn.addEventListener("click", () => {
      let liked = read("liked", []);
      const on = !liked.includes(slug);
      liked = on ? [...liked, slug] : liked.filter(s => s !== slug);
      write("liked", liked);
      btn.setAttribute("aria-pressed", on);
      toast(on ? "Added to your likes" : "Removed from your likes");
    });
  });

  // ---------- floating WhatsApp button: shows after a little scrolling ----------
  const wa = $("[data-wa-float]");
  if (wa) {
    const show = () => {
      const visible = scrollY > 240;
      wa.classList.toggle("opacity-0", !visible);
      wa.classList.toggle("translate-y-3", !visible);
      wa.classList.toggle("pointer-events-none", !visible);
    };
    addEventListener("scroll", show, { passive: true });
    show();
  }

  // ---------- portfolio: tap a photo to see it big ----------
  const box = $("[data-lightbox]");
  if (box) {
    $$("[data-zoom]").forEach(b => b.addEventListener("click", () => {
      $("img", box).src = b.dataset.zoom.replace(/w=\d+/, "w=1600");
      $("p", box).textContent = b.dataset.title;
      box.showModal();
    }));
    box.addEventListener("click", e => { if (e.target === box || e.target.closest("[data-close]")) box.close(); });
  }

  // ---------- contact form -> WhatsApp ----------
  const contact = $("[data-contact]");
  if (contact) contact.addEventListener("submit", e => {
    e.preventDefault();
    const f = new FormData(contact);
    window.open(waLink(`Hello ${store.name}! I'm ${f.get("name")}. About: ${f.get("topic")}.\n${f.get("message")}`), "_blank", "noopener");
  });
})();
