// Photo pickers in the admin pop-ups (templates/admin/_photos.html).
// Choose one or many photos: each is made smaller here (at most 2000 px, JPEG), uploaded on its own to
// /admin/upload (Vercel Blob), and shown as a tile. × removes a photo; tapping a photo makes it the cover.
(() => {
  const MAX_SIDE = 2000, QUALITY = 0.85;
  const $ = (s, el = document) => el.querySelector(s), $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const urls = p => $("[data-photos-value]", p).value.split("\n").map(s => s.trim()).filter(Boolean);
  const setUrls = (p, list) => { $("[data-photos-value]", p).value = list.join("\n"); render(p); };
  const error = (p, text) => { const e = $("[data-photos-error]", p); e.textContent = text || ""; e.hidden = !text; };

  const X = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" class="size-3.5"><path d="M6 6l12 12M18 6 6 18"/></svg>';

  function render(p) {
    const list = $("[data-photos-list]", p), add = $("[data-photos-add]", p), multiple = p.dataset.multiple === "1";
    $$("[data-photo-tile]", list).forEach(t => t.remove());
    urls(p).forEach((url, i) => {
      const tile = document.createElement("div");
      tile.dataset.photoTile = "";
      tile.className = "group relative aspect-square overflow-hidden rounded-xl bg-zinc-100 dark:bg-zinc-800";
      tile.innerHTML = `<button type="button" data-cover class="block size-full" title="${multiple && i ? "Make it the cover" : ""}"><img alt="" class="size-full object-cover"></button>
        ${multiple && i === 0 ? '<span class="pointer-events-none absolute bottom-1 left-1 rounded-md bg-black/60 px-1.5 py-0.5 text-[10px] font-semibold text-white">Cover</span>' : ""}
        <button type="button" data-drop aria-label="Remove this photo" class="absolute right-1 top-1 grid size-6 place-items-center rounded-full bg-black/60 text-white transition hover:bg-sale">${X}</button>`;
      $("img", tile).onerror = e => { e.target.style.opacity = 0; };   // can't load: grey tile, × still works
      $("img", tile).src = url;
      $("[data-cover]", tile).onclick = () => { if (multiple && i) { const l = urls(p); l.unshift(...l.splice(i, 1)); setUrls(p, l); } };
      $("[data-drop]", tile).onclick = () => { const l = urls(p); l.splice(i, 1); setUrls(p, l); };
      list.insertBefore(tile, $("[data-uploading]", list) || add);
    });
    add.hidden = !multiple && (urls(p).length > 0 || !!$("[data-uploading]", list));
  }

  // smaller JPEG, right way up (phones store the rotation separately)
  async function shrink(file) {
    const img = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_SIDE / Math.max(img.width, img.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale); canvas.height = Math.round(img.height * scale);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height);    // see-through parts become white
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return new Promise(done => canvas.toBlob(done, "image/jpeg", QUALITY));
  }

  function send(p, blob, onProgress) {
    const form = p.closest("form"), data = new FormData();
    data.append("csrf_token", $("[name=csrf_token]", form)?.value || "");
    data.append("folder", p.dataset.folder);
    data.append("name", form.elements.name?.value || form.elements.instagram?.value || p.dataset.folder);
    data.append("file", blob, "photo.jpg");
    return new Promise((ok, fail) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", p.dataset.upload);
      xhr.upload.onprogress = e => e.lengthComputable && onProgress(e.loaded / e.total);
      xhr.onload = () => {
        let body = {}; try { body = JSON.parse(xhr.responseText); } catch (e) {}
        xhr.status === 200 && body.url ? ok(body.url) : fail(new Error(body.error || "The photo didn't upload. Try again."));
      };
      xhr.onerror = () => fail(new Error("No connection: the photo didn't upload."));
      xhr.send(data);
    });
  }

  // every chosen photo gets its tile and progress bar at once; 3 upload at the same time; order is kept
  async function upload(p, files) {
    error(p);
    const list = $("[data-photos-list]", p), multiple = p.dataset.multiple === "1";
    const chosen = (multiple ? files : files.slice(0, 1)).filter(f => {
      if (f.type.startsWith("image/")) return true;
      error(p, `${f.name} is not a photo.`); return false;
    });
    if (!chosen.length) return;
    if (!multiple) setUrls(p, []);                                      // one photo: the new one replaces the old
    const jobs = chosen.map(file => {
      const tile = document.createElement("div");
      tile.dataset.uploading = "";
      tile.className = "relative aspect-square overflow-hidden rounded-xl bg-zinc-100 dark:bg-zinc-800";
      tile.innerHTML = '<img alt="" class="size-full object-cover opacity-40 transition-opacity"><span class="absolute inset-x-2 bottom-2 h-1.5 overflow-hidden rounded-full bg-black/20"><span data-bar class="block h-full w-[4%] rounded-full bg-brand transition-[width]"></span></span>';
      const preview = URL.createObjectURL(file);
      $("img", tile).src = preview;
      list.insertBefore(tile, $("[data-photos-add]", list));
      return { file, tile, preview, url: null };
    });
    render(p);
    const failed = [];
    let next = 0;
    const worker = async () => {
      while (next < jobs.length) {
        const job = jobs[next++];
        try {
          job.url = await send(p, await shrink(job.file), f => { $("[data-bar]", job.tile).style.width = `${Math.max(4, f * 100)}%`; });
          $("img", job.tile).classList.remove("opacity-40");          // done: full colour, bar full
          $("[data-bar]", job.tile).style.width = "100%";
        } catch (e) {
          failed.push(e.message || "A photo didn't upload. Try again.");
          job.tile.remove();
        }
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    jobs.forEach(j => { j.tile.remove(); URL.revokeObjectURL(j.preview); });
    setUrls(p, multiple ? [...urls(p), ...jobs.filter(j => j.url).map(j => j.url)] : jobs.filter(j => j.url).map(j => j.url).slice(0, 1));
    if (failed.length) error(p, failed.length === 1 ? failed[0] : `${failed.length} photos didn't upload: ${failed[0]}`);
  }

  document.addEventListener("change", e => {
    if (!e.target.matches("[data-photos-input]")) return;
    const files = [...e.target.files];
    e.target.value = "";                                              // the same photo can be chosen again
    upload(e.target.closest("[data-photos]"), files);
  });

  // before saving: wait for uploads; a photo is required where the picker says so
  document.addEventListener("submit", e => {
    for (const p of $$("[data-photos]", e.target)) {
      if ($("[data-uploading]", p)) { error(p, "Wait a moment: photos are still uploading."); }
      else if (p.dataset.required === "1" && !urls(p).length) { error(p, "Add at least one photo."); }
      else continue;
      e.preventDefault(); e.stopImmediatePropagation();               // the page's "Saving…" script doesn't run
      return;
    }
  }, true);

  // a pop-up opens (its fields were just filled in): show its photos
  const refresh = d => $$("[data-photos]", d).forEach(p => { error(p); $$("[data-uploading]", p).forEach(t => t.remove()); render(p); });
  $$("dialog").forEach(d => new MutationObserver(() => d.open && refresh(d)).observe(d, { attributes: true, attributeFilter: ["open"] }));
  $$("[data-photos]").forEach(render);
})();
