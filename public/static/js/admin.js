// Vision Electronics admin — sidebar, theme, pop-ups and form helpers
(() => {
  const root = document.documentElement;
  const save = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };

  // ---------- Sidebar: ☰ closes/opens it (desktop remembers), slides over the page on phones ----------
  const desktop = () => matchMedia("(min-width: 900px)").matches;
  document.querySelector(".sb-toggle")?.addEventListener("click", () => {
    if (desktop()) save("adm-collapsed", root.classList.toggle("sb-collapsed") ? "1" : "0");
    else root.classList.toggle("sb-open");
  });
  document.querySelector(".sb-backdrop")?.addEventListener("click", () => root.classList.remove("sb-open"));
  document.addEventListener("keydown", e => { if (e.key === "Escape") root.classList.remove("sb-open"); });

  // ---------- Light / dark (shared with the website for this visit) ----------
  document.querySelectorAll(".theme-toggle").forEach(b => b.addEventListener("click", () => {
    const t = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = t;
    try { sessionStorage.setItem("theme", t); } catch (e) {}
  }));

  // ---------- User menu: close when clicking elsewhere ----------
  document.addEventListener("click", e => {
    const menu = document.querySelector(".tb-user");
    if (menu && menu.open && !menu.contains(e.target)) menu.open = false;
  });

  // ---------- Flash messages ----------
  document.querySelectorAll(".flash").forEach(f => {
    const close = () => { f.style.transition = "opacity .3s"; f.style.opacity = 0; setTimeout(() => f.remove(), 300); };
    f.querySelector(".flash-close")?.addEventListener("click", close);
    setTimeout(close, 5000);
  });

  // ---------- Photo shrinking ----------
  // Phone photos are often 5–12 MB. The server keeps at most 1600 px anyway, so resize to 2000 px
  // here first: uploads are faster and stay under the hosting limit (4.5 MB per request on Vercel).
  const MAX_SIDE = 2000;
  async function shrinkFile(file) {
    if (!file.type.startsWith("image/") || !window.createImageBitmap) return file;
    try {
      const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
      const scale = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
      if (scale === 1 && file.size < 1.5e6) { bmp.close?.(); return file; }   // already small
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(bmp.width * scale); canvas.height = Math.round(bmp.height * scale);
      canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
      bmp.close?.();
      // keep transparency for PNG/WebP, JPEG for everything else
      const type = /png|webp/.test(file.type) ? "image/webp" : "image/jpeg";
      const blob = await new Promise(r => canvas.toBlob(r, type, 0.9));
      if (!blob || blob.size >= file.size) return file;
      const ext = blob.type === "image/webp" ? "webp" : blob.type === "image/png" ? "png" : "jpg";
      return new File([blob], file.name.replace(/\.[^.]+$/, "") + "." + ext, { type: blob.type, lastModified: Date.now() });
    } catch (e) {
      return file;   // the browser can't read it (e.g. some AVIF): send as it is, the server checks it
    }
  }
  async function shrinkInput(inp) {
    if (!window.DataTransfer) return;
    const files = await Promise.all([...inp.files].map(shrinkFile));
    const dt = new DataTransfer();
    files.forEach(f => dt.items.add(f));
    inp.files = dt.files;
  }

  // ---------- Confirmation dialog ----------
  // askConfirm("Delete this message?") → Promise<boolean>. The action button is named after the
  // message's first word ("Delete", "Stop", "Hand over" …) and is red for actions that remove things.
  const ACTIONS = { Delete: "Delete", Remove: "Remove", Stop: "Stop", Start: "Start", Hand: "Hand over" };
  function askConfirm(message) {
    return new Promise(resolve => {
      const first = (message.match(/^\w+/) || [""])[0];
      const label = ACTIONS[first] || "Continue";
      const danger = ["Delete", "Remove", "Stop"].includes(first);
      const [title, ...rest] = message.split(/(?<=\?)\s+/);   // "Question?" + optional explanation
      const d = document.createElement("dialog");
      d.className = "confirm-box";
      d.innerHTML = `<p class="confirm-title"></p><p class="confirm-text"></p>
        <div class="confirm-actions"><button type="button" class="btn btn-outline" value="no">Cancel</button>
        <button type="button" class="btn${danger ? " btn-solid-danger" : ""}" value="yes"></button></div>`;
      d.querySelector(".confirm-title").textContent = title;
      d.querySelector(".confirm-text").textContent = rest.join(" ");
      d.querySelector("[value=yes]").textContent = label;
      let answer = false;
      d.querySelectorAll("button").forEach(btn => btn.addEventListener("click", () => { answer = btn.value === "yes"; d.close(); }));
      d.addEventListener("click", e => { if (e.target === d) d.close(); });     // click outside = cancel
      d.addEventListener("close", () => { d.remove(); resolve(answer); });   // Esc = cancel
      document.body.appendChild(d);
      d.showModal();
      d.querySelector("[value=yes]").focus();
    });
  }
  window.askConfirm = askConfirm;

  // ---------- Form helpers (run on the page and inside every pop-up) ----------
  function initForms(scope) {
    // "Are you sure?" — our own dialog, never the browser's
    scope.querySelectorAll("form[data-confirm]").forEach(f =>
      f.addEventListener("submit", async e => {
        if (f._confirmed) { f._confirmed = false; return; }
        e.preventDefault();
        e.stopImmediatePropagation();          // nothing else runs until the answer is yes
        const submitter = e.submitter;
        if (await askConfirm(f.dataset.confirm)) {
          f._confirmed = true;
          setTimeout(() => (f.requestSubmit ? f.requestSubmit(submitter || undefined) : f.submit()), 0);
        }
      }));
    scope.querySelectorAll("[data-confirm-click]").forEach(b =>
      b.addEventListener("click", async e => {
        if (b._confirmed) { b._confirmed = false; return; }
        e.preventDefault();
        e.stopImmediatePropagation();
        if (await askConfirm(b.dataset.confirmClick)) {
          b._confirmed = true;
          if (b.href) location.href = b.href; else b.click();
        }
      }));

    // photos: shrink in the browser, show their names, keep each save under the upload limit
    scope.querySelectorAll(".drop input[type=file]").forEach(inp => {
      inp.addEventListener("change", async () => {
        const drop = inp.closest(".drop"), list = drop.nextElementSibling;
        const say = t => { if (list && list.classList.contains("drop-list")) list.textContent = t; };
        drop.classList.toggle("has-files", inp.files.length > 0);
        if (!inp.files.length) { say(""); return; }
        const form = inp.form;
        say("Preparing photos…");
        const job = shrinkInput(inp);
        form._pending = (form._pending || []).concat(job);
        await job;
        const names = [...inp.files].map(f => f.name), mb = [...inp.files].reduce((s, f) => s + f.size, 0) / 1e6;
        say(`✓ ${names.length} photo${names.length > 1 ? "s" : ""} ready (${mb.toFixed(1)} MB): ${names.join(", ")}`);
      });
    });
    scope.querySelectorAll("form[enctype='multipart/form-data']").forEach(form => {
      form.addEventListener("submit", async e => {
        if (form._ready) return;              // second pass: photos are ready, really send
        e.preventDefault();
        await Promise.all(form._pending || []);
        const limit = parseInt(document.body.dataset.uploadLimit || "0", 10);
        const total = [...form.querySelectorAll("input[type=file]")].flatMap(i => [...i.files]).reduce((s, f) => s + f.size, 0);
        form.querySelector(".upload-error")?.remove();
        if (limit && total > limit) {
          const p = document.createElement("p");
          p.className = "upload-error";
          p.textContent = `These photos are ${(total / 1e6).toFixed(1)} MB together — the most one save can send is ${(limit / 1e6).toFixed(1)} MB. Choose fewer photos, save, then add the rest.`;
          form.querySelector(".drop")?.after(p);
          return;
        }
        form._ready = true;
        // next tick: the browser ignores a new submit while it is still handling this one
        const submitter = e.submitter;
        setTimeout(() => (form.requestSubmit ? form.requestSubmit(submitter || undefined) : form.submit()), 0);
      });
    });

    // fields that depend on a checkbox
    scope.querySelectorAll("[data-show-if]").forEach(el => {
      const box = scope.querySelector("#" + el.dataset.showIf);
      if (!box) return;
      const sync = () => { el.style.display = box.checked ? "" : "none"; };
      box.addEventListener("change", sync); sync();
    });

    // live price preview with discount
    const price = scope.querySelector("#f-price"), disc = scope.querySelector("#f-discount"), out = scope.querySelector("#price-preview");
    if (price && disc && out) {
      // written like the website writes prices: "$1,299.00", "£49.99", "RWF 12,000"
      const sym = price.dataset.symbol || "$", dec = parseInt(price.dataset.decimals || "2", 10);
      const fmt = n => {
        const num = n.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
        return /[A-Za-z]$/.test(sym) ? `${sym} ${num}` : sym + num;
      };
      const update = () => {
        const p = parseFloat((price.value || "").replace(/[^\d.]/g, "")), d = parseInt(disc.value || "0", 10);
        if (!p) { out.textContent = ""; return; }
        out.innerHTML = d > 0
          ? `Customers pay <b>${fmt(Math.round(p * (100 - d)) / 100)}</b> <s>${fmt(p)}</s> — they save ${fmt(p * d / 100)}`
          : `Customers pay <b>${fmt(p)}</b>`;
      };
      price.addEventListener("input", update); disc.addEventListener("input", update); update();
    }
  }
  initForms(document);

  // ---------- Pop-ups ----------
  // <a href="/altar/…/new" data-modal>  → loads that page's form into the pop-up
  // <button data-modal="#template-id">  → shows a form kept in a <template> on the page
  const modal = document.getElementById("modal");
  if (!modal) return;
  const body = modal.querySelector(".modal-body"), title = modal.querySelector("#modal-title");

  async function openModal(trigger) {
    const target = trigger.dataset.modal;
    title.textContent = trigger.dataset.modalTitle || trigger.textContent.replace("+", "").trim();
    body.innerHTML = '<p class="muted modal-loading">Loading…</p>';
    modal.showModal();
    document.body.classList.add("modal-open");
    let form;
    if (target && target.startsWith("#")) {
      const tpl = document.querySelector(target);
      form = tpl.content ? tpl.content.firstElementChild.cloneNode(true) : tpl.firstElementChild.cloneNode(true);
    } else {
      try {
        const res = await fetch(trigger.href, { credentials: "same-origin" });
        const doc = new DOMParser().parseFromString(await res.text(), "text/html");
        form = doc.querySelector("form.adm-form");
        if (!form) throw new Error("no form");
        form.action = trigger.href;
        form.querySelectorAll(".save-bar a.btn-outline").forEach(a => {   // "Cancel" closes the pop-up
          const b = document.createElement("button");
          b.type = "button"; b.className = a.className; b.textContent = a.textContent; b.dataset.modalClose = "";
          a.replaceWith(b);
        });
      } catch (e) {
        window.location = trigger.href;   // fall back to the full page
        return;
      }
    }
    // after saving, come back to this page
    const back = document.createElement("input");
    back.type = "hidden"; back.name = "_back"; back.value = location.pathname + location.search;
    form.appendChild(back);
    form.classList.add("in-modal");
    body.innerHTML = "";
    body.appendChild(form);
    initForms(body);
    form.querySelector("input:not([type=hidden]):not([type=file]), textarea, select")?.focus();
  }

  function closeModal() {
    modal.close();
  }
  modal.addEventListener("close", () => { body.innerHTML = ""; document.body.classList.remove("modal-open"); });
  modal.addEventListener("click", e => {
    if (e.target === modal || e.target.closest("[data-modal-close]")) closeModal();   // backdrop or Close/Cancel
  });
  document.addEventListener("click", e => {
    const t = e.target.closest("[data-modal]");
    if (!t || e.metaKey || e.ctrlKey || e.shiftKey) return;   // ⌘/Ctrl-click still opens the full page
    e.preventDefault();
    openModal(t);
  });
  // dashboard shortcut "Upload portfolio photos" opens the pop-up straight away
  if (location.hash === "#upload") document.querySelector('[data-modal="#pf-upload"]')?.click();
})();

/* Dates (<time datetime="…Z">) shown in the viewer's own time zone */
document.querySelectorAll("time[datetime$='Z']").forEach(t => {
  const d = new Date(t.getAttribute("datetime"));
  if (!isNaN(d)) t.textContent = d.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
});

/* Copy buttons (e.g. the giveaway test link) */
document.querySelectorAll("[data-copy]").forEach(b => b.addEventListener("click", () => {
  navigator.clipboard?.writeText(b.dataset.copy).then(() => { const t = b.textContent; b.textContent = "Copied"; setTimeout(() => { b.textContent = t; }, 1400); });
}));

/* Giveaway: show the device list or the amount, depending on the prize chosen */
document.querySelectorAll(".gw-kind").forEach(set => {
  const form = set.closest("form");
  const sync = () => {
    const money = form.querySelector("input[name=prize_kind]:checked")?.value === "money";
    form.querySelector(".gw-device").hidden = money;
    form.querySelector(".gw-money").hidden = !money;
    form.querySelector("[name=product_id]").required = !money;
    form.querySelector("[name=amount]").required = money;
  };
  set.addEventListener("change", sync);
  sync();
});
