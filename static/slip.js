/* Kupon oluşturucu arayüzü ("Kuponum" sekmesi + maç kartlarındaki "Kupona ekle" düğmeleri).
 * Kupon yalnız bu tarayıcının localStorage'ında durur (giriş yok). Hesaplar: slip-calc.js.
 * app.js'ten kullanılan yüzey: Slip.button(m, market) ve Slip.render(). Bu dosya app.js'ten ÖNCE yüklenir. */
(function () {
  "use strict";
  const C = window.SlipCalc;
  const STORE_KEY = "iddiaoran.slip.v1";
  const REFRESH_AFTER_MS = 3 * 60 * 1000;

  const q = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (p, digits = 0) => (p * 100).toFixed(digits) + "%";
  const money = (n) => n.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ₺";
  const fmtDateTime = (iso) => new Date(iso).toLocaleString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  let data = load();
  const matchCache = new Map(); // kartlarda gösterilen maç verisi (id -> maç); düğme tıklanınca seçim buradan kurulur
  const missing = new Set();    // güncelleme sırasında listede bulunamayan maç id'leri (oynanmış olabilir)
  let lastRefresh = 0, refreshing = false, toastTimer = 0;

  function load() {
    try { return C.sanitize(JSON.parse(localStorage.getItem(STORE_KEY))); } catch { return C.sanitize(null); }
  }
  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(data)); } catch { /* özel mod / dolu depo: kupon bu oturumla sınırlı kalır */ }
  }
  function leagueName(m) {
    if (m.league_name) return m.league_name;
    const list = typeof state !== "undefined" && state.leagues ? state.leagues : [];
    return (list.find((l) => l.id === m.league) || {}).name || "";
  }

  // ---------- düğmeler (maç kartı + maç detayı) ----------
  function btnInner(on) { return on ? "✓ Kuponda" : "＋ Kupona ekle"; }
  function button(m, market) {
    if (!m || !C.MARKETS.includes(market) || !m.markets || !m.markets[market]) return "";
    matchCache.set(String(m.id), m);
    const on = C.hasSelection(data.items, m.id, market);
    return `<button type="button" class="slip-add${on ? " on" : ""}" data-slip-id="${esc(m.id)}" data-slip-market="${esc(market)}" aria-pressed="${on}" title="${esc(m.home)} – ${esc(m.away)}: ${esc(market)} seçimini kupona ekle / çıkar">${btnInner(on)}</button>`;
  }
  function syncButtons() {
    document.querySelectorAll(".slip-add").forEach((b) => {
      const on = C.hasSelection(data.items, b.dataset.slipId, b.dataset.slipMarket);
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", String(on));
      b.textContent = btnInner(on);
    });
    const badge = q("#slipCount");
    if (badge) { badge.textContent = data.items.length; badge.classList.toggle("hidden", !data.items.length); }
  }

  function toast(msg) {
    let el = q("#slipToast");
    if (!el) { el = document.createElement("div"); el.id = "slipToast"; el.className = "slip-toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 3000);
  }

  // ---------- durum değişiklikleri ----------
  const slipVisible = () => { const t = q("#tab-slip"); return !!t && !t.classList.contains("hidden"); };
  function changed() {
    save();
    syncButtons();
    if (slipVisible()) renderView();
  }
  function toggle(id, market) {
    if (C.hasSelection(data.items, id, market)) { data.items = C.removeSelection(data.items, id + "|" + market); return changed(); }
    const m = matchCache.get(String(id));
    const sel = m && C.fromMatch(m, market, leagueName(m));
    if (!sel) return toast("Bu seçim için oran bulunamadı.");
    const r = C.addSelection(data.items, sel);
    if (r.status === "full") return toast(`Kuponda en fazla ${C.MAX_ITEMS} seçim olabilir.`);
    data.items = r.items;
    changed();
  }

  async function fetchMatch(id) {
    try {
      const r = await fetch("/api/match/" + encodeURIComponent(id));
      if (r.status === 404) return { gone: true };
      return r.ok ? { m: await r.json() } : null;
    } catch { return null; } // ağ hatası: eldeki oranlar kalır
  }
  async function refresh() {
    const ids = [...new Set(data.items.map((i) => i.id))];
    if (!ids.length || refreshing) return;
    refreshing = true;
    if (slipVisible()) renderView();
    const results = await Promise.all(ids.map(fetchMatch));
    refreshing = false;
    lastRefresh = Date.now();
    const fresh = new Map(ids.map((id, i) => [id, results[i]]));
    for (const [id, r] of fresh) { if (r && r.gone) missing.add(id); else missing.delete(id); }
    data.items = data.items.map((sel) => { const r = fresh.get(sel.id); return r && r.m ? C.refreshSelection(sel, r.m) : sel; });
    changed();
  }

  // ---------- Kuponum sekmesi ----------
  function marketBadge(market) {
    const group = C.GROUPS.find((g) => g.markets.includes(market));
    return `<span class="badge b-info" title="${esc(group ? group.label : "")}">${esc(market)}</span>`;
  }
  function oddsCell(r) {
    return `<b class="iddaa-odd">${r.odds.toFixed(2)}</b>` + (r.source === "iddaa"
      ? `<span class="src src-iddaa">iddaa</span>`
      : `<span class="src src-claude">Claude oran</span><span class="claude-odd">iddaa oranı yok</span>`);
  }
  function rowHtml(r, dupIds) {
    const flags = [];
    if (dupIds.has(r.id)) flags.push(`<span class="badge b-warn" title="Aynı maçtan birden fazla seçim">aynı maç</span>`);
    if (r.started) flags.push(`<span class="badge b-bad">başladı</span>`);
    if (missing.has(r.id)) flags.push(`<span class="badge b-bad" title="Maç güncel listede yok; oynanmış olabilir">listede yok</span>`);
    const live = typeof state !== "undefined" && state.live && (state.live.get(String(r.id)) || [...state.live.values()].find((m) => m.home === r.home && m.away === r.away));
    const liveStatus = live && typeof selectionResult === "function" ? selectionResult(r.market, live.home_goals, live.away_goals, live.state) : "";
    return `<tr class="${dupIds.has(r.id) ? "slip-dup" : ""}" data-live-match="${esc(r.id)}" data-home="${esc(r.home)}" data-away="${esc(r.away)}" data-market="${esc(r.market)}">
      <td class="l"><b>${esc(r.home)}</b> – ${esc(r.away)}<span class="claude-odd">${esc(r.leagueName)}</span></td>
      <td>${fmtDateTime(r.kickoff)} <span class="live-score">${live ? `<span class="badge b-bad">${live.home_goals}–${live.away_goals} · ${esc(live.minute)}</span>` : ""}</span></td><td>${marketBadge(r.market)} <span class="live-status">${liveStatus ? `<span class="badge ${liveStatus === "yatıyor" || liveStatus === "yattı" ? "b-bad" : "b-good"}">${liveStatus}</span>` : ""}</span> ${flags.join(" ")}</td>
      <td>${oddsCell(r)}</td><td>${pct(r.p)}</td>
      <td><button type="button" class="slip-remove" data-slip-remove="${esc(r.key)}" aria-label="${esc(r.home)} – ${esc(r.away)} ${esc(r.market)} seçimini çıkar">×</button></td></tr>`;
  }
  function warningsHtml(s) {
    const out = [];
    for (const g of s.sameMatch) {
      const name = `<b>${esc(g.home)} – ${esc(g.away)}</b>`, mk = g.markets.map(esc).join(" + ");
      out.push(g.impossible
        ? `<div class="slip-warn bad">⚠ ${name}: ${mk} aynı anda gerçekleşemez; bu kupon kazanamaz (tutma ihtimali %0 sayıldı).</div>`
        : `<div class="slip-warn">⚠ ${name} maçından ${g.markets.length} seçim var (${mk}). Aynı maçın seçimleri birbirine bağlıdır; tutma ihtimali bağımsız varsayımıyla hesaplanan yaklaşık bir değerdir ve bahis sitelerinde bu birleşim kabul edilmeyebilir.</div>`);
    }
    if (s.startedCount) out.push(`<div class="slip-warn bad">⚠ ${s.startedCount} seçimin maçı başlamış; bunlar artık oynanamaz.</div>`);
    if (s.claudeCount) out.push(`<div class="slip-warn info">ℹ ${s.claudeCount} seçimde iddaa oranı yok, Claude oranı kullanıldı. Bu gerçek bahis oranı değildir; kazanç ve EV buna göre tahmindir.</div>`);
    return out.join("");
  }
  function resultHtml(s) {
    if (s.stake === null) return `<p class="muted">Olası kazancı görmek için yatırılacak tutarı girin.</p>`;
    const good = s.expectedValue >= 0;
    return `<div class="slip-result">
      <div><small>Olası kazanç</small><b class="slip-win">${money(s.payout)}</b></div>
      <div><small>Net kâr (tutarsa)</small><b>${money(s.profit)}</b></div>
      <div><small>Beklenen net getiri (EV)</small><b style="color:var(--${good ? "good" : "bad"})">${s.expectedValue > 0 ? "+" : ""}${money(s.expectedValue)}</b></div></div>`;
  }
  function summaryHtml(s) {
    const evColor = s.ev >= 0 ? "good" : "bad";
    return `<div class="slip-stats">
      <div><small>Toplam oran</small><b>${s.totalOdds.toFixed(2)}</b></div>
      <div><small>Model tutma ihtimali</small><b>${pct(s.totalProbability, s.totalProbability < 0.1 ? 1 : 0)}</b></div>
      <div><small>EV (1 ₺ başına)</small><b style="color:var(--${evColor})">${s.ev > 0 ? "+" : ""}${(s.ev * 100).toFixed(1)}%</b></div></div>`;
  }
  function sourceBadge(s) {
    if (s.source === "iddaa") return `<span class="badge b-info">oranlar: iddaa</span>`;
    if (s.source === "claude") return `<span class="badge b-warn">oranlar: Claude oran</span>`;
    return `<span class="badge b-info">oranlar: ${s.iddaaCount}/${s.count} iddaa, kalanı Claude oran</span>`;
  }

  function renderView() {
    const el = q("#slip");
    if (!el) return;
    const stakeInput = q("#slipStake");
    const focus = stakeInput && document.activeElement === stakeInput ? stakeInput.selectionStart : null;
    const s = C.summarize(data.items, data.stake, Date.now());
    if (!s.count) {
      el.innerHTML = `<div class="card muted">Kuponunuz boş. Maç kartlarındaki <b>＋ Kupona ekle</b> düğmesiyle (ya da maç detayında istediğiniz pazarı seçerek: 1X2, çifte şans, Alt/Üst, KG) seçim ekleyin.</div>`;
      return;
    }
    const dupIds = new Set(s.sameMatch.map((g) => g.id));
    el.innerHTML = `<div class="card slip-card">
      <div class="row-between"><h3>Kuponum</h3><span>${sourceBadge(s)} <span class="badge b-good">${s.count} seçim</span></span></div>
      ${warningsHtml(s)}
      <table><tr><th class="l">Maç</th><th>Saat</th><th>Seçim</th><th>Oran</th><th>Model</th><th></th></tr>${s.rows.map((r) => rowHtml(r, dupIds)).join("")}</table>
      ${summaryHtml(s)}
      <div class="slip-stake"><label>Yatırılacak tutar (₺) <input id="slipStake" type="text" inputmode="decimal" autocomplete="off" value="${data.stake === null ? "" : esc(String(data.stake).replace(".", ","))}" placeholder="örn. 100"></label></div>
      <div id="slipResult">${resultHtml(s)}</div>
      <div class="slip-actions">
        <button type="button" class="btn" id="slipShare">Paylaş</button>
        <select id="slipShareSize" aria-label="Görsel boyutu"><option value="square">Kare 1080×1080</option><option value="story">Story 1080×1920</option></select>
        <button type="button" class="btn" id="slipRefresh" ${refreshing ? "disabled" : ""}>${refreshing ? "Yenileniyor…" : "Oranları yenile"}</button>
        <button type="button" class="btn btn-ghost" id="slipClear">Kuponu temizle</button>
      </div>
      <p class="muted slip-note">Tutma ihtimali, seçimlerin model olasılıklarının çarpımıdır (seçimlerin birbirinden bağımsız olduğu varsayılır). Kupon bu tarayıcıda saklanır; oranlar zamanla değişebilir. Tahmindir, garanti değildir.</p>
    </div>`;
    if (focus !== null) { const inp = q("#slipStake"); inp.focus(); inp.setSelectionRange(focus, focus); }
  }

  /** app.js'in render() döngüsünden çağrılır (state.tab === "slip"). */
  async function render() {
    q("#leagueChips")?.classList.add("hidden");
    syncButtons();
    renderView();
    if (data.items.length && Date.now() - lastRefresh > REFRESH_AFTER_MS) await refresh();
  }

  // ---------- olaylar ----------
  // Yakalama aşamasında: kart içindeki düğme tıklaması maç detayını (app.js'teki [data-id] dinleyicisi) açmasın.
  document.addEventListener("click", (e) => {
    const t = e.target.closest(".slip-add, .slip-remove, #slipClear, #slipRefresh, #slipShare");
    if (!t) return;
    e.stopPropagation();
    if (t.classList.contains("slip-add")) toggle(t.dataset.slipId, t.dataset.slipMarket);
    else if (t.classList.contains("slip-remove")) { data.items = C.removeSelection(data.items, t.dataset.slipRemove); changed(); }
    else if (t.id === "slipClear") { data.items = []; missing.clear(); changed(); }
    else if (t.id === "slipRefresh") refresh();
    else if (t.id === "slipShare") { const s = C.summarize(data.items, data.stake, Date.now()); window.CouponShare?.share({ title: "Kuponum", date: new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" }), picks: s.rows.map((r) => ({ home: r.home, away: r.away, market: r.market, odds: r.odds, kickoff: r.kickoff })), totalOdds: s.totalOdds }, q("#slipShareSize").value); }
  }, true);

  document.addEventListener("input", (e) => {
    if (e.target.id !== "slipStake") return;
    data.stake = C.parseStake(e.target.value);
    save();
    q("#slipResult").innerHTML = resultHtml(C.summarize(data.items, data.stake, Date.now()));
  });

  // Başka sekmede/pencerede kupon değişirse burada da güncelle
  window.addEventListener("storage", (e) => {
    if (e.key !== STORE_KEY) return;
    data = load();
    syncButtons();
    if (slipVisible()) renderView();
  });

  document.addEventListener("DOMContentLoaded", syncButtons);
  window.Slip = { button, render };
})();
