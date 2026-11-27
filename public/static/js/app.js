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
  const setCart = cart => { write("cart", cart); paintCount(); paintCards(); paintProduct(); };
  const paintCount = () => {
    const n = Object.values(getCart()).reduce((a, b) => a + b, 0);
    $$("[data-cart-count]").forEach(el => { el.textContent = n > 99 ? "99+" : n; el.hidden = !n; });
  };
  // product cards: + on the photo, then − qty + (the − becomes a bin at 1)
  function paintCards() {
    const cart = getCart();
    $$("[data-card-cart]").forEach(box => {
      const qty = cart[box.dataset.slug] || 0, stock = Number(box.dataset.stock || 0);
      $("[data-card-add]", box).hidden = qty > 0;
      $("[data-card-stepper]", box).hidden = !qty;
      $("[data-card-qty]", box).textContent = qty;
      $("[data-card-minus]", box).hidden = qty === 1;
      $("[data-card-bin]", box).hidden = qty !== 1;
      $("[data-card-dec]", box).setAttribute("aria-label", qty === 1 ? `Remove ${box.dataset.name} from cart` : `One less ${box.dataset.name}`);
      $("[data-card-inc]", box).disabled = qty >= stock;
    });
  }
  document.addEventListener("click", e => {
    const btn = e.target.closest("[data-card-add], [data-card-inc], [data-card-dec]");
    if (!btn) return;
    e.preventDefault();
    const box = btn.closest("[data-card-cart]"), slug = box.dataset.slug, stock = Number(box.dataset.stock || 0);
    const cart = getCart(), qty = cart[slug] || 0;
    if (btn.matches("[data-card-dec]")) {
      if (qty <= 1) { delete cart[slug]; toast(`${box.dataset.name} removed from your cart`); }
      else cart[slug] = qty - 1;
    } else if (qty >= stock) {
      toast(`Only ${stock} in stock`); return;
    } else {
      cart[slug] = qty + 1;
      if (!qty) toast(`${box.dataset.name} added to your cart`);
    }
    setCart(cart);
  });
  paintCount();
  paintCards();
  window.addEventListener("storage", e => { if (e.key === "cart") { paintCount(); paintCards(); paintProduct(); } });   // another tab changed it

  // product page: the quantity box and "Add to cart" follow the cart.
  // Not in the cart yet: choose how many, then Add to cart.
  // In the cart: the box changes the cart itself (the − is a bin at 1), the button opens the cart.
  const addBtn = $("[data-add]"), qtyInput = $("[data-qty]");
  function paintProduct() {
    if (!addBtn || !qtyInput) return;
    const slug = addBtn.dataset.add, inCart = getCart()[slug] || 0, note = $("[data-in-cart]");
    if (inCart) qtyInput.value = inCart;
    addBtn.textContent = inCart ? "Go to cart" : "Add to cart";
    $("[data-step-minus]").hidden = inCart === 1;
    $("[data-step-bin]").hidden = inCart !== 1;
    if (note) { note.hidden = !inCart; $("span", note).textContent = `${inCart} in your cart`; }
  }
  if (addBtn && qtyInput) {
    const slug = addBtn.dataset.add, stock = Number(addBtn.dataset.stock || 99);
    const setQty = n => {                       // n = the wanted quantity
      const cart = getCart();
      if (!cart[slug]) { qtyInput.value = Math.min(stock, Math.max(1, n)); return; }   // not in the cart: just the box
      if (n < 1) { delete cart[slug]; qtyInput.value = 1; toast("Removed from your cart"); }
      else { if (n > stock) toast(`Only ${stock} in stock`); cart[slug] = Math.min(stock, n); }
      setCart(cart);
    };
    $$("[data-step]").forEach(b => b.addEventListener("click", () => setQty(Number(qtyInput.value || 1) + Number(b.dataset.step))));
    qtyInput.addEventListener("change", () => setQty(Math.max(1, Number(qtyInput.value) || 1)));
    addBtn.addEventListener("click", () => {
      const cart = getCart();
      if (cart[slug]) { location.href = addBtn.dataset.cartUrl; return; }
      cart[slug] = Math.min(stock, Math.max(1, Number(qtyInput.value || 1)));
      setCart(cart);
      toast("Added to your cart");
    });
    paintProduct();
  }

  // cart page
  const cartBox = $("[data-cart]");
  if (cartBox && window.CATALOG) {
    const lines = $("[data-cart-lines]"), tpl = $("template[data-line]");
    const render = () => {
      const cart = getCart();
      Object.keys(cart).forEach(slug => { if (!CATALOG[slug]) delete cart[slug]; });   // products no longer sold
      const slugs = Object.keys(cart);
      lines.innerHTML = "";
      let total = 0, before = 0;
      const orderLines = [];
      slugs.forEach(slug => {
        const p = CATALOG[slug], qty = cart[slug], line = tpl.content.firstElementChild.cloneNode(true);
        const was = p.discount ? p.was : p.price;
        total += p.price * qty;
        before += was * qty;
        orderLines.push(`• ${qty} × ${p.short} (${p.sku}): ${money(p.price * qty)}${p.discount ? ` (−${p.discount}%)` : ""}`);
        $$("[data-link]", line).forEach(a => (a.href = p.url));
        $("[data-img]", line).src = p.image;
        $("[data-name]", line).textContent = p.short;
        $("[data-sku]", line).textContent = p.sku;
        $("[data-each]", line).textContent = `${money(p.price)} each`;
        $("[data-each]", line).classList.toggle("text-sale", !!p.discount);
        $("[data-was]", line).hidden = $("[data-off]", line).hidden = !p.discount;
        $("[data-was]", line).textContent = money(was);
        $("[data-off]", line).textContent = `−${p.discount}%`;
        $("[data-saved]", line).hidden = !p.discount;
        $("[data-saved]", line).textContent = `You save ${money((was - p.price) * qty)}`;
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
      const saved = before - total;
      $("[data-cart-savings]").hidden = $("[data-cart-saved]").hidden = saved <= 0;
      $("[data-cart-before]").textContent = money(before);
      $("[data-cart-discount]").textContent = `−${money(saved)}`;
      $("[data-cart-saved]").textContent = `You save ${money(saved)} with today's discounts`;
      $("[data-cart-total]").textContent = money(total);
      $("[data-cart-order]").href = waLink(`Hello ${store.name}! I'd like to order:\n${orderLines.join("\n")}\n`
        + (saved > 0 ? `Discounts: −${money(saved)}\n` : "") + `Total: ${money(total)}`);
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

  // ---------- home slideshow: endless loop, moves on by itself; the filling dot shows when ----------
  const show = $("[data-slides]");
  if (show) {
    const track = $("[data-slide-track]", show), slides = $$("[data-slide]", show), dots = $$("[data-slide-dot]", show);
    const n = slides.length, seconds = Number(show.dataset.seconds || 6);
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;   // no automatic sliding for them
    let current = 0, settle = null, held = still;

    // a copy of the last photo before the first and of the first after the last, so a photo always peeks in
    // on both sides and the loop never runs backwards through every photo
    const copy = el => { const c = el.cloneNode(true); c.setAttribute("aria-hidden", "true"); c.removeAttribute("data-slide");
                         c.querySelectorAll("a").forEach(a => a.tabIndex = -1); return c; };
    const before = copy(slides[n - 1]), after = copy(slides[0]);
    track.prepend(before); track.append(after);
    const twin = i => (i === 0 ? after : i === n - 1 ? before : null);   // the copy that looks like slide i

    const left = el => el.offsetLeft - (track.clientWidth - el.clientWidth) / 2;
    const jump = el => { track.style.scrollSnapType = "none"; track.scrollLeft = left(el); void track.offsetWidth; track.style.scrollSnapType = ""; };

    const activate = i => {
      current = i;
      slides.forEach((sl, k) => sl.toggleAttribute("data-current", k === i));
      [before, after].forEach(c => c.toggleAttribute("data-current", c === twin(i)));
      dots.forEach((d, k) => {
        d.toggleAttribute("data-active", k === i);
        d.setAttribute("aria-selected", k === i);
        const fill = $("[data-fill]", d);
        fill.style.animation = "none";
        void fill.offsetWidth;                                  // restart the fill from empty
        fill.style.animation = k === i ? `slide-fill ${seconds}s linear forwards` : "";
        fill.style.animationPlayState = show.matches(":hover") || held ? "paused" : "running";
      });
    };
    const go = i => {
      const target = i >= n ? after : i < 0 ? before : slides[i];   // past the end: slide onto the copy, then hop back
      track.scrollTo({ left: left(target), behavior: "smooth" });
      activate((i + n) % n);
    };

    // when the fill reaches the end, the next photo comes
    dots.forEach((d, k) => {
      $("[data-fill]", d).addEventListener("animationend", () => k === current && go(current + 1));
      d.addEventListener("click", () => go(k));
    });
    // when scrolling stops: on a copy, hop to the real photo; after a swipe, follow the photo in the middle
    track.addEventListener("scroll", () => {
      clearTimeout(settle);
      settle = setTimeout(() => {
        const mid = track.scrollLeft + track.clientWidth / 2;
        const all = [...track.children];
        const near = all.reduce((best, el) => Math.abs(el.offsetLeft + el.clientWidth / 2 - mid) < Math.abs(best.offsetLeft + best.clientWidth / 2 - mid) ? el : best);
        if (near === before) { jump(slides[n - 1]); if (current !== n - 1) activate(n - 1); }
        else if (near === after) { jump(slides[0]); if (current !== 0) activate(0); }
        else { const k = slides.indexOf(near); if (k !== current) activate(k); }
      }, 140);
    }, { passive: true });

    // pause while the visitor looks closely (mouse over it, finger on it), the tab is hidden, or ‖ was pressed
    const pauseBtn = $("[data-slide-pause]", show);
    const pause = on => dots.forEach(d => ($("[data-fill]", d).style.animationPlayState = on || held ? "paused" : "running"));
    if (pauseBtn) {
      pauseBtn.setAttribute("aria-pressed", held);
      pauseBtn.addEventListener("click", e => {
        e.stopPropagation();
        held = !held;
        pauseBtn.setAttribute("aria-pressed", held);
        pauseBtn.setAttribute("aria-label", held ? "Play the slideshow" : "Pause the slideshow");
        pause(false);
      });
    }
    show.addEventListener("mouseenter", () => pause(true));
    show.addEventListener("mouseleave", () => pause(false));
    show.addEventListener("touchstart", () => pause(true), { passive: true });
    show.addEventListener("touchend", () => pause(false), { passive: true });
    document.addEventListener("visibilitychange", () => pause(document.hidden));
    addEventListener("resize", () => jump(slides[current]));
    jump(slides[0]);
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
