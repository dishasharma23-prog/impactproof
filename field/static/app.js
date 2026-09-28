/* ImpactProof Field UI. Talks only to this device's local API, which works offline. */
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let status = null, stream = null, fix = null, pickedFile = null;

const STATE = { pending: "Waiting to sync", synced: "Synced", local_only: "Stays on device", skipped: "Not sent", conflict: "Conflict" };
const KIND = { capture: "Photo", note: "Note", fact: "Fact", hq_site: "HQ site", hq_evidence: "HQ evidence" };

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  let d = null;
  try { d = await r.json(); } catch {}
  if (!r.ok) throw new Error((d && d.detail) || `Request failed (${r.status})`);
  return d;
}
const post = (p, b) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
function toast(m) { const t = $("#toast"); t.textContent = m; t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), 3200); }
function ago(iso) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now"; if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`; return new Date(iso).toLocaleDateString();
}
function origin(i) {
  if (i.origin === "hq") return `<span class="chip o-hq">From HQ</span>`;
  if (i.origin === "peer") return `<span class="chip o-peer">From ${esc(i.device_name || i.device_id)}</span>`;
  return `<span class="chip">This device</span>`;
}
function thumb(i) {
  if (i.image_url) return `<img class="thumb" src="${esc(i.image_url)}" alt="">`;
  if (i.thumb_url && status?.connectivity?.online) return `<img class="thumb" src="${esc(i.thumb_url)}" alt="">`;
  return `<div class="glyph">${esc(KIND[i.kind] || i.kind)}</div>`;
}
function row(i, extra = "") {
  const photoNote = i.kind === "capture" && i.origin === "local" && i.photo_state
    ? `<span class="chip">${esc({ waiting_wifi: "Photo waits for Wi-Fi", at_hq: `At HQ: ${[i.hq_code, i.hq_status_label].filter(Boolean).join(" ")}`, kept_on_device: "Photo kept on device", waiting: "Photo upload retrying", not_paired: "Photo waits for sign-in" }[i.photo_state] || i.photo_state)}</span>` : "";
  const value = i.kind === "fact" ? ` = <b>${esc(i.value)}</b>` : "";
  return `<li class="item ${i.sync_state === "conflict" ? "conflict" : ""}">${thumb(i)}
    <div class="body">
      <div class="title">${esc(i.title || i.key || KIND[i.kind])}${value}</div>
      ${i.text && i.kind !== "fact" && i.text !== i.title ? `<div class="text">${esc(i.text)}</div>` : ""}
      <div class="chips"><span class="chip">${esc(KIND[i.kind] || i.kind)}</span>${origin(i)}
        <span class="chip s-${esc(i.sync_state)}">${esc(STATE[i.sync_state] || i.sync_state)}</span>${photoNote}
        ${i.site ? `<span class="chip">${esc(i.site)}</span>` : ""}${i.rank ? `<span class="chip">#${i.rank}</span>` : ""}
        <span class="chip">${esc(ago(i.updated_at || i.created_at))}</span></div>
      ${i.sync_reason ? `<div class="reason">${esc(i.sync_reason)}</div>` : ""}
    </div>${extra}</li>`;
}

/* ---------------- tabs ---------------- */
function show(tab) {
  $$(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
  $$(".tab").forEach((s) => (s.hidden = s.id !== `tab-${tab}`));
  try { localStorage.setItem("field.tab", tab); } catch {}
  if (tab === "memory") loadMemory();
  if (tab === "sync") loadSync();
  if (tab === "activity") loadActivity();
}
$$(".tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));

/* ---------------- status ---------------- */
async function refresh() {
  try { status = await api("/api/status"); } catch { return; }
  document.title = `${status.device_name} · ImpactProof Field`;
  $("#deviceName").textContent = status.volunteer ? `${status.volunteer.name} · ${status.device_name}` : status.device_name;
  const vol = status.volunteer;
  $("#volSignedIn").hidden = !vol; $("#volForm").hidden = !!vol;
  if (vol) { $("#volName").textContent = vol.name; $("#volMeta").textContent = `${vol.phone_masked} · photos upload in this volunteer's name`; }
  const on = status.connectivity.online;
  const pill = $("#connPill");
  pill.className = `pill ${on ? "on" : "off"}`;
  pill.textContent = on ? (status.network === "mobile" ? "Online, mobile data" : "Online, Wi-Fi") : "Offline";
  const pending = status.sync_states.pending;
  $("#sNet").textContent = on ? (status.network === "mobile" ? "MOBILE" : "WI-FI") : "OFFLINE";
  $("#sNet").className = on ? "ok" : "bad";
  $("#sSync").textContent = `${pending} PENDING${status.waiting_photos ? ` · ${status.waiting_photos} PHOTO` : ""}`;
  const banner = $("#banner");
  if (!on) {
    banner.hidden = false;
    banner.textContent = `Working offline. Everything is saved and searchable on this device${pending ? `; ${pending} item(s) will sync when back online` : ""}.`;
  } else banner.hidden = true;
  const c = status.sync_states.conflict;
  $("#conflictBadge").hidden = !c; $("#conflictBadge").textContent = c;
  $("#syncBtn").disabled = !on;
  const sites = new Set();
  (await api("/api/items?kind=hq_site").catch(() => [])).forEach((s) => sites.add(s.title));
  $("#siteList").innerHTML = [...sites].map((s) => `<option value="${esc(s)}">`).join("");
}
$("#connPill").addEventListener("click", () => show("sync"));
$("#syncBtn").addEventListener("click", async () => {
  $("#syncBtn").disabled = true; $("#syncBtn").textContent = "Syncing…";
  try {
    const s = await api("/api/sync", { method: "POST" });
    toast(s.online === false ? s.reason : `Synced: sent ${s.pushed.sent}, received ${s.pulled.received}${s.pushed.conflicts + s.pulled.conflicts ? `, ${s.pushed.conflicts + s.pulled.conflicts} conflict(s)` : ""}`);
  } catch (e) { toast(e.message); }
  $("#syncBtn").textContent = "Sync now";
  await refresh(); rerender();
});
function rerender() {
  const t = $$(".tabs button").find((b) => b.getAttribute("aria-selected") === "true")?.dataset.tab;
  if (t === "memory") loadMemory(); if (t === "sync") loadSync(); if (t === "activity") loadActivity();
}

/* ---------------- capture ---------------- */
if ("geolocation" in navigator) {
  navigator.geolocation.watchPosition(
    (p) => { fix = p.coords; $("#gps").textContent = `Location ±${Math.round(p.coords.accuracy)} m`; $("#sGps").textContent = `±${Math.round(p.coords.accuracy)} M`; },
    () => { $("#gps").textContent = "Location unavailable"; $("#sGps").textContent = "NO FIX"; }, { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 });
}
$("#camStart").addEventListener("click", async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
    $("#video").srcObject = stream; await $("#video").play();
    $("#camOff").hidden = true; $("#preview").hidden = true; $("#shoot").disabled = false; $("#camStop").hidden = false; pickedFile = null;
  } catch (e) { toast(window.isSecureContext ? "Camera unavailable: " + e.message : "The camera needs https or localhost."); }
});
$("#camStop").addEventListener("click", stopCam);
function stopCam() { stream?.getTracks().forEach((t) => t.stop()); stream = null; $("#camOff").hidden = false; $("#camStop").hidden = true; $("#shoot").disabled = !pickedFile; }
$("#fileInput").addEventListener("change", (e) => {
  pickedFile = e.target.files[0] || null;
  if (!pickedFile) return;
  $("#preview").src = URL.createObjectURL(pickedFile); $("#preview").hidden = false; $("#shoot").disabled = false;
});
$("#shoot").addEventListener("click", async () => {
  let blob = pickedFile;
  if (stream) {
    const v = $("#video"), c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight; c.getContext("2d").drawImage(v, 0, 0);
    blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
  }
  if (!blob) return;
  const fd = new FormData();
  fd.append("file", blob, "capture.jpg");
  fd.append("caption", $("#caption").value); fd.append("site", $("#site").value);
  fd.append("private", $("#capPrivate").checked ? "true" : "false");
  fd.append("tz_offset_min", String(new Date().getTimezoneOffset()));
  if (fix) { fd.append("lat", fix.latitude); fd.append("lng", fix.longitude); }
  $("#shoot").disabled = true;
  try {
    const it = await api("/api/captures", { method: "POST", body: fd });
    $("#capResult").textContent = `Saved on device. ${it.sync_reason}`;
    $("#caption").value = ""; $("#capPrivate").checked = false;
    if (!stream) { pickedFile = null; $("#preview").hidden = true; $("#fileInput").value = ""; }
  } catch (e) { $("#capResult").textContent = e.message; }
  $("#shoot").disabled = !stream; refresh();
});
$("#noteForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const it = await post("/api/notes", { text: $("#noteText").value, site: $("#noteSite").value, private: $("#notePrivate").checked });
    $("#noteResult").textContent = `Saved on device. ${it.sync_reason}`;
    $("#noteText").value = ""; $("#notePrivate").checked = false; refresh();
  } catch (x) { $("#noteResult").textContent = x.message; }
});
$("#factForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const it = await post("/api/facts", { key: $("#factKey").value, value: $("#factValue").value });
    $("#factResult").textContent = `Saved on device. ${it.sync_reason}`; $("#factValue").value = ""; refresh();
  } catch (x) { $("#factResult").textContent = x.message; }
});

/* ---------------- search ---------------- */
$("#searchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#q").value.trim(); if (!q) return;
  const mode = document.querySelector("input[name=mode]:checked").value;
  try {
    const r = await api(`/api/search?q=${encodeURIComponent(q)}&mode=${mode}`);
    $("#searchMeta").textContent = `${r.results.length} result${r.results.length === 1 ? "" : "s"} in ${r.ms} ms, searched on this device${r.offline ? " with no network" : ""}.`;
    $("#results").innerHTML = r.results.length ? r.results.map((i, n) => row({ ...i, rank: n + 1 })).join("") : `<li class="empty">Nothing in this device's memory matches.</li>`;
  } catch (x) { toast(x.message); }
});
$$("input[name=mode]").forEach((r) => r.addEventListener("change", () => $("#q").value && $("#searchForm").requestSubmit()));

/* ---------------- memory ---------------- */
async function loadMemory() {
  if (status) {
    const m = status.memory;
    $("#memStats").innerHTML = [
      [m.points, "items on device"], [status.origins.local, "created here"], [status.origins.peer, "from other devices"],
      [status.origins.hq, "from HQ"], [status.sync_states.local_only, "never leave device"],
      [`${(m.disk_bytes / 1024 / 1024).toFixed(1)} MB`, "on disk"],
    ].map(([n, l]) => `<div class="stat"><b>${esc(n)}</b><span>${esc(l)}</span></div>`).join("");
  }
  const p = new URLSearchParams();
  if ($("#fKind").value) p.set("kind", $("#fKind").value);
  if ($("#fOrigin").value) p.set("origin", $("#fOrigin").value);
  if ($("#fState").value) p.set("state", $("#fState").value);
  const items = await api(`/api/items?${p}`).catch(() => []);
  $("#memList").innerHTML = items.length ? items.map((i) => row(i, i.origin === "local" ? `<div class="side">
      <button class="linkbtn" data-priv="${esc(i.id)}" data-val="${i.private ? "false" : "true"}">${i.private ? "Allow sync" : "Keep on device"}</button>
      <button class="linkbtn bad" data-del="${esc(i.id)}">Delete</button></div>` : "")).join("") : `<li class="empty">No items match.</li>`;
}
["#fKind", "#fOrigin", "#fState"].forEach((s) => $(s).addEventListener("change", loadMemory));
$("#memList").addEventListener("click", async (e) => {
  const d = e.target.dataset;
  if (d.del && confirm("Delete this item? If it has synced, other devices will drop it too.")) { await api(`/api/items/${d.del}`, { method: "DELETE" }); toast("Deleted"); }
  if (d.priv) { await post(`/api/items/${d.priv}/privacy`, { private: d.val === "true" }); toast(d.val === "true" ? "Kept on this device" : "Allowed to sync"); }
  if (d.del || d.priv) { await refresh(); loadMemory(); }
});

/* ---------------- sync ---------------- */
async function loadSync() {
  if (!status) return;
  const on = status.connectivity.online;
  $("#connDetail").textContent = on ? "Online" : "Offline";
  $("#connDetail").insertAdjacentHTML("beforeend", `<span class="meta" style="display:block;font-weight:400;font-family:Figtree,system-ui,sans-serif;letter-spacing:0;font-size:13px">${esc(status.connectivity.reason)} Server: ${esc(status.server)}${status.hq ? `. HQ: ${esc(status.hq)}` : ""}</span>`);
  $("#offlineToggle").checked = status.simulated_offline;
  $$("input[name=net]").forEach((r) => (r.checked = r.value === status.network));
  $("#mediaMobile").checked = status.allow_media_on_mobile;
  const ls = status.last_sync;
  $("#lastSync").textContent = ls ? `Last sync ${ago(ls.at)}: sent ${ls.pushed.sent}, received ${ls.pulled.received}, ${ls.photos.uploaded} photo(s) to HQ, took ${ls.ms} ms. Auto-sync every ${status.auto_sync_seconds} s when online.` : `Not synced yet. Auto-sync every ${status.auto_sync_seconds} s when online.`;
  const s = status.sync_states;
  $("#policy").innerHTML = `
    <li><b>${s.pending}</b> waiting to sync. Facts go first, then notes, then photo details.</li>
    <li><b>${status.waiting_photos}</b> photo file(s) waiting for Wi-Fi.</li>
    <li><b>${s.local_only}</b> never leave this device: marked private, or containing a phone number, email or ID number.</li>
    <li><b>${s.skipped}</b> not sent: near-duplicate photos taken moments apart.</li>
    <li><b>${s.synced}</b> synced. Items from other devices and HQ are kept up to ${status.budget}; the least recently useful are dropped first.</li>`;
  $("#storage").textContent = `Qdrant Edge shard: ${status.memory.points} points, ${status.memory.segments} segment(s), ${(status.memory.disk_bytes / 1024 / 1024).toFixed(1)} MB. Embeddings: ${status.memory.embedder === "fastembed" ? "on-device models (bge-small, CLIP)" : "simple fallback (run setup_models while online)"}.`;
  const conflicts = await api("/api/items?state=conflict").catch(() => []);
  $("#conflicts").innerHTML = conflicts.length ? conflicts.map((i) => `<li class="item conflict"><div class="body">
      <div class="title">${esc(i.key)}</div>
      <div class="vs"><div><span class="meta">This device</span><b>${esc(i.value)}</b></div>
        <div><span class="meta">${esc(i.conflict?.device_name || i.conflict?.device_id)}</span><b>${esc(i.conflict?.value)}</b></div></div>
      <div class="actions"><button class="btn small" data-res="mine" data-id="${esc(i.id)}">Keep mine</button>
        <button class="btn small ghost" data-res="theirs" data-id="${esc(i.id)}">Keep theirs</button>
        <input style="max-width:140px" placeholder="Other value" aria-label="Merged value" data-merge="${esc(i.id)}">
        <button class="btn small ghost" data-res="merge" data-id="${esc(i.id)}">Use this</button></div></div></li>`).join("")
    : `<li class="empty">No conflicts.</li>`;
  const queue = await api("/api/items?state=pending").catch(() => []);
  $("#queue").innerHTML = queue.length ? queue.map((i) => row(i)).join("") : `<li class="empty">Nothing waiting. Everything that should sync has synced.</li>`;
}
$("#conflicts").addEventListener("click", async (e) => {
  const d = e.target.dataset; if (!d.res) return;
  const body = { choice: d.res };
  if (d.res === "merge") body.value = document.querySelector(`[data-merge="${d.id}"]`).value;
  try { await post(`/api/items/${d.id}/resolve`, body); toast("Resolved. It will sync next time you're online."); await refresh(); loadSync(); }
  catch (x) { toast(x.message); }
});
$("#offlineToggle").addEventListener("change", async (e) => { await post("/api/network", { offline: e.target.checked }); await refresh(); loadSync(); });
$$("input[name=net]").forEach((r) => r.addEventListener("change", async () => { await post("/api/network", { network: r.value }); await refresh(); loadSync(); }));
$("#mediaMobile").addEventListener("change", async (e) => { await post("/api/network", { allow_media_on_mobile: e.target.checked }); await refresh(); });

/* ---------------- activity ---------------- */
async function loadActivity() {
  const a = await api("/api/activity").catch(() => []);
  $("#activity").innerHTML = a.map((e) => `<li class="k-${esc(e.kind)}"><time>${esc(new Date(e.at).toLocaleString())}</time>${esc(e.message)}</li>`).join("") || `<li>No activity yet.</li>`;
}

let startTab = "capture";
try { startTab = localStorage.getItem("field.tab") || "capture"; } catch {}
refresh().then(() => show(startTab));
setInterval(async () => {
  await refresh();
  const t = $$(".tabs button").find((b) => b.getAttribute("aria-selected") === "true")?.dataset.tab;
  const typing = document.activeElement && ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName);
  if ((t === "sync" || t === "activity") && !typing) rerender();
}, 4000);

// light / dark switch, remembered on this device
(function () {
  const btn = document.getElementById("themeBtn");
  const paint = () => { const dark = document.documentElement.dataset.theme === "dark"; btn.innerHTML = dark ? "&#9788;" : "&#9790;"; btn.title = dark ? "Light mode" : "Dark mode"; };
  btn.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("field-theme", next); } catch (e) {}
    paint();
  });
  paint();
})();

// instrument strip: clock and battery
(function () {
  const tick = () => { $("#sTime").textContent = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }); };
  tick(); setInterval(tick, 1000);
  if (navigator.getBattery) {
    navigator.getBattery().then((b) => {
      const paint = () => { $("#sBatt").textContent = `${Math.round(b.level * 100)}%${b.charging ? " +" : ""}`; $("#sBatt").className = b.level < 0.2 && !b.charging ? "bad" : ""; };
      paint(); b.addEventListener("levelchange", paint); b.addEventListener("chargingchange", paint);
    }).catch(() => { $("#sBattWrap").hidden = true; });
  } else { $("#sBattWrap").hidden = true; }
})();

// volunteer sign-in (phone number + pairing code from ImpactProof)
$("#volForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const res = $("#volResult"); res.textContent = "Signing in…";
  try {
    const v = await post("/api/pair", { phone: $("#volPhone").value, code: $("#volCode").value.replace(/\s/g, "") });
    res.textContent = ""; $("#volCode").value = "";
    toast(`Signed in as ${v.name}`); refresh();
  } catch (x) { res.textContent = x.message; }
});
$("#volOut").addEventListener("click", async () => {
  if (!confirm("Sign out? Photos will stay on this device until someone signs in.")) return;
  await api("/api/pair", { method: "DELETE" }); toast("Signed out"); refresh();
});
