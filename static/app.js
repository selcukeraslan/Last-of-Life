const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (p) => (p * 100).toFixed(0) + "%";
const api = async (url, opts) => {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.text()) || r.status);
  return r.json();
};

const savedLeague = localStorage.getItem("league") || "tur.1";
const state = { league: savedLeague, tab: "matches", leagues: [], smallLeaguesOpen: savedLeague.startsWith("small:"), couponDate: new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" }), couponReq: 0, matchReq: 0, live: new Map() };

function selectionResult(market, h, a, state) {
  if (state === "post") return selectionWins(market, h, a) ? "tuttu" : "yattı";
  if (selectionWins(market, h, a)) return "tutuyor";
  if (selectionImpossible(market, h, a)) return "yatıyor";
  return "bekliyor";
}
function selectionWins(m, h, a) {
  const total = h + a, result = h > a ? "1" : h < a ? "2" : "X";
  if (["1", "X", "2"].includes(m)) return result === m;
  if (m === "1X") return h >= a; if (m === "12") return h !== a; if (m === "X2") return h <= a;
  const g = Number(m.match(/[0-9.]+/)?.[0]);
  if (m.startsWith("Ü")) return total > g;
  if (m.startsWith("A")) return total < g;
  if (m === "KG Var") return h > 0 && a > 0; if (m === "KG Yok") return h === 0 || a === 0;
  return false;
}
function selectionImpossible(m, h, a) {
  const total = h + a;
  if (m.startsWith("Ü")) return total >= Number(m.match(/[0-9.]+/)?.[0]);
  if (m.startsWith("A")) return total > Number(m.match(/[0-9.]+/)?.[0]);
  if (m === "KG Var") return h === 0 || a === 0;
  if (m === "KG Yok") return h > 0 && a > 0;
  if (["1", "X", "2"].includes(m)) return (m === "1" && a > h) || (m === "2" && h > a) || (m === "X" && h !== a);
  if (m === "1X") return a > h; if (m === "12") return h === a; if (m === "X2") return h > a;
  return false;
}
function liveBadge(m) { return m ? `<span class="badge ${m.state === "in" ? "b-bad" : "b-info"}">${esc(m.home_goals)}–${esc(m.away_goals)} · ${esc(m.minute)}</span>` : ""; }
function pickLive(p) {
  return state.live.get(String(p.id)) || [...state.live.values()].find((m) => m.home === p.home && m.away === p.away);
}
async function refreshLive() {
  try {
    const data = await api("/api/live");
    state.live = new Map((data.matches || []).map((m) => [String(m.id), m]));
    if ($("#liveState")) $("#liveState").textContent = data.stale ? "Canlı skorların bir kısmı güncel değil; son alınan veriler gösteriliyor." : "";
    document.querySelectorAll(".match[data-id]").forEach((card) => {
      const m = state.live.get(card.dataset.id), time = card.querySelector(".time");
      if (time && m) time.innerHTML = liveBadge(m);
    });
    document.querySelectorAll("[data-live-match]").forEach((row) => {
      const m = pickLive({ id: row.dataset.liveMatch, home: row.dataset.home, away: row.dataset.away });
      const status = row.querySelector(".live-status");
      const score = row.querySelector(".live-score");
      if (status) {
        const result = m && selectionResult(row.dataset.market, m.home_goals, m.away_goals, m.state);
        status.innerHTML = result ? `<span class="badge ${result === "yatıyor" || result === "yattı" ? "b-bad" : "b-good"}">${result}</span>` : "";
      }
      if (score) score.innerHTML = m ? liveBadge(m) : "";
    });
    if (state.tab === "slip") Slip.render();
    window.Extras?.onLive();
  } catch { if ($("#liveState")) $("#liveState").textContent = "Canlı skorlar güncellenemedi; son alınan veriler gösteriliyor."; }
}

function fmtTime(iso) { return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }); }
function fmtDay(iso) { return new Date(iso).toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" }); }
function fmtDateTime(iso) { return new Date(iso).toLocaleString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
function fmtAgo(iso) {
  const min = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "az önce";
  if (min < 60) return min + " dk önce";
  if (min < 1440) return Math.floor(min / 60) + " sa önce";
  return Math.floor(min / 1440) + " gün önce";
}
function showLastUpdate() {
  const el = $("#lastUpdate");
  const iso = state.lastUpdate;
  el.textContent = iso ? fmtAgo(iso) + " güncellendi" : state.catalogFallback ? "Son güncelleme doğrulanamadı" : "Henüz veri yok";
  el.title = iso ? fmtDateTime(iso) : "";
}
function formDots(s) { return `<span class="formdots">${[...(s || "")].map((c) => `<span class="f-${c}">${c}</span>`).join("")}</span>`; }
function img(src) { return src ? `<img src="${esc(src)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : ""; }

function renderLeagueChips() {
  const main = state.leagues.map((l) =>
    `<button type="button" class="chip ${l.id === state.league ? "active" : ""}" data-league="${esc(l.id)}">${esc(l.name)} </button>`).join("");
  const byName = new Map();
  for (const league of state.smallLeagues || []) {
    const name = league.name || "Diğer";
    if (!byName.has(name)) byName.set(name, []);
    byName.get(name).push(league);
  }
  const groups = [...byName.entries()].sort(([a], [b]) => a.localeCompare(b, "tr"));
  const smallOptions = groups.map(([name, leagues]) => `<div class="small-league-name-group">
    <b>${esc(name)}</b><div class="small-league-countries">${leagues.sort((a, b) => (a.country || "").localeCompare(b.country || "", "tr")).map((l) =>
      `<button type="button" class="chip small-league-chip ${l.id === state.league ? "active" : ""}" data-league="${esc(l.id)}" aria-label="${esc(`${l.country || "Ülke belirtilmemiş"} · ${name}`)}" title="${esc(`${l.country || "Ülke belirtilmemiş"} · ${name}`)}">${esc(l.country || "Ülke belirtilmemiş")}</button>`).join("")}</div>
  </div>`).join("");
  const activeSmall = state.league.startsWith("small:");
  $("#leagueChips").innerHTML = `<div class="league-group main-league-group">${main}</div>` +
    (groups.length ? `<div class="league-picker"><button type="button" class="chip small-leagues-toggle ${activeSmall ? "active" : ""}" data-small-leagues-toggle aria-expanded="${state.smallLeaguesOpen}" aria-controls="smallLeagueOptions">Diğer ligler <span class="muted">${state.smallLeagues.length}</span></button>
      <div id="smallLeagueOptions" class="small-league-options ${state.smallLeaguesOpen ? "" : "hidden"}">${smallOptions}</div></div>` : "");
}

async function loadLeagues() {
  let d;
  try {
    d = await api(UpdateStatus.freshUrl("/api/leagues"), { cache: "no-store" });
    state.catalogFallback = false;
    try { localStorage.setItem("leagueCatalog.v1", JSON.stringify({ leagues: d.leagues, small_leagues: d.small_leagues })); } catch (_) {}
  } catch (error) {
    try { d = JSON.parse(localStorage.getItem("leagueCatalog.v1")); } catch (_) {}
    if (!d?.leagues) throw error;
    state.catalogFallback = true; // çevrimdışı katalogda güncelleme zamanı tutulmaz
  }
  state.leagues = d.leagues;
  state.smallLeagues = d.small_leagues || [];
  const selected = [...state.leagues, ...state.smallLeagues].find((l) =>
    l.id === state.league || l.slug === state.league || l.name === state.league || l.aliases?.includes(state.league));
  state.league = selected?.id || state.leagues[0]?.id || "tur.1";
  localStorage.setItem("league", state.league);
  UpdateStatus.apply(state, d);
  showLastUpdate();
  renderLeagueChips();
}

function matchCard(m) {
  const detailId = m.small_league ? (m.iddaa_event_id || m.id) : m.id;
  const live = state.live.get(String(m.id));
  return `<div class="card match" data-home="${esc(m.home)}" data-away="${esc(m.away)}" data-id="${esc(m.id)}" data-match-id="${esc(detailId)}" data-event-id="${esc(m.iddaa_event_id || (m.small_league ? m.id : ""))}" data-competition-id="${esc(m.competition_id ?? "")}" role="button" tabindex="0" aria-label="${esc(m.home)} - ${esc(m.away)} maç detayı">
    <div class="m-head">
      <div class="m-teams">
        <div class="m-team">${window.Extras ? Extras.star(m.home) : ""}${img(m.home_logo)}<b>${esc(m.home)}</b></div>
        <div class="m-team">${window.Extras ? Extras.star(m.away) : ""}${img(m.away_logo)}<b>${esc(m.away)}</b></div>
      </div>
      <div class="time">${live ? liveBadge(live) : fmtTime(m.kickoff)}</div>
    </div>
    <div class="m-pick">${Simple.pickBlock(m)}
      ${m.pick ? `<div class="m-actions">${Slip.button(m, m.pick.market)}<span class="m-more">Ayrıntılar ›</span></div>` : `<div class="m-actions"><span class="m-more">Ayrıntılar ›</span></div>`}
    </div>
  </div>`;
}

async function renderMatches() {
  const el = $("#matches");
  el.innerHTML = window.Ui ? Ui.skeleton(4) : `<p class="muted">Yükleniyor…</p>`;
  renderOddsDrops();
  window.Today?.render();
  const query = new URLSearchParams({ league: state.league, days: "14" });
  const list = await api(`/api/upcoming?${query}`);
  if (!list.length) { el.innerHTML = Ui.empty("Maç bulunamadı", "Önümüzdeki 14 günde maç yok. Verileri güncellemeyi deneyin."); return; }
  const selectedLeague = [...state.leagues, ...(state.smallLeagues || [])].find((l) => l.id === state.league);
  const leagueTitle = selectedLeague ? `${selectedLeague.country ? esc(selectedLeague.country) + " · " : ""}${esc(selectedLeague.name)}` : "";
  let html = "", lastDay = "";
  for (const m of list) {
    const day = fmtDay(m.kickoff);
    if (day !== lastDay) { html += `<div class="day-head">${day}</div>`; lastDay = day; }
    html += matchCard(m);
  }
  el.innerHTML = (window.Extras ? Extras.filterButton() : "") + (leagueTitle ? `<div class="day-head">${leagueTitle}</div>` : "") + html;
  window.Extras?.afterMatches(list);
  renderTable();
}

async function renderCoupons() {
  const el = $("#coupons"), req = ++state.couponReq;
  el.innerHTML = `<p class="muted">Kuponlar hesaplanıyor…</p>`;
  const d = await api(`/api/coupons?day=${state.couponDate}`);
  if (req !== state.couponReq) return; // daha yeni bir gün seçildi
  const data = d && typeof d === "object" ? d : {};
  const dateText = data.date && !Number.isNaN(new Date(`${data.date}T12:00:00Z`).getTime())
    ? fmtDay(`${data.date}T12:00:00Z`) : "Gün bilgisi yok";
  const matches = Number.isFinite(Number(data.matches)) ? Number(data.matches) : 0;
  el.innerHTML = `<p class="muted">${esc(dateText)} · ana ligler: ${matches} maç</p>` +
    CouponView.couponGroup(data, "banko", "b-good", data.date) +
    CouponView.couponGroup(data, "surprise", "b-warn", data.date) +
    CouponView.couponCard(data.small_leagues, "Küçük Ligler Kuponu", "b-warn", { kind: "small_leagues", index: 0, date: data.date });
  el.querySelectorAll("[data-share-coupon]").forEach((button) => button.addEventListener("click", () => {
    const type = button.dataset.shareType, index = Number(button.dataset.shareIndex) || 0;
    const coupon = type === "small_leagues" ? data.small_leagues : CouponView.alternatives(data, type)[index];
    if (coupon?.picks?.length) window.CouponShare?.share({ title: button.closest(".coupon-card").querySelector("h3").textContent, date: data.date, picks: coupon.picks, totalOdds: coupon.total_odds }, button.parentElement.querySelector("[data-share-size]").value);
  }));
}

async function renderTable() {
  const el = $("#table");
  if (!el) return;
  if (!state.leagues.some((l) => l.id === state.league)) { el.innerHTML = ""; return; }
  let rows;
  try {
    rows = await api(`/api/standings?${new URLSearchParams({ league: state.league })}`);
  } catch { el.innerHTML = ""; return; }
  el.innerHTML = `<details class="detail"><summary>Puan durumu</summary><div class="detail-body"><table>
    <tr><th>#</th><th class="l">Takım</th><th>O</th><th>G</th><th>B</th><th>M</th><th>AV</th><th>P</th><th>Form</th></tr>
    ${rows.map((r) => `<tr><td>${r.pos}</td><td class="l">${esc(r.team)}</td><td>${r.p}</td><td>${r.w}</td><td>${r.d}</td><td>${r.l}</td>
      <td>${r.gd > 0 ? "+" : ""}${r.gd}</td><td><b>${r.pts}</b></td><td>${formDots(r.form)}</td></tr>`).join("")}
  </table></div></details>`;
}

function newsList(n) {
  if (!n.items.length) return `<p class="muted">Son 7 günde haber bulunamadı.</p>`;
  return `<ul class="news">${n.items.slice(0, 5).map((i) => `<li>
    ${i.counted ? `<span class="badge ${i.att_pct < 0 ? "b-bad" : "b-good"}">${esc(i.label)}</span> ` : ""}<a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a> <span class="muted">· ${esc(i.source)}</span></li>`).join("")}</ul>`;
}

function renderSmallMatch(m) {
  const order = ["1", "X", "2", "1X", "12", "X2", "Ü1.5", "A1.5", "Ü2.5", "A2.5", "Ü3.5", "A3.5", "KG Var", "KG Yok"];
  const odds = Object.entries(m.iddaa_odds || {}).sort((a, b) => {
    const ai = order.indexOf(a[0]), bi = order.indexOf(b[0]);
    return (ai < 0 ? order.length : ai) - (bi < 0 ? order.length : bi) || a[0].localeCompare(b[0]);
  });
  const marketRows = odds.map(([market, odd]) => `<tr><td class="l"><b>${esc(Simple.headline(market))}</b> <span class="muted">${esc(Simple.title(market))}</span></td><td><b class="iddaa-odd">${Number(odd).toFixed(2)}</b></td></tr>`).join("");
  $("#modalBody").innerHTML = `
    <button class="close" onclick="closeModal()" aria-label="Kapat">×</button>
    <div class="m-meta">${esc(m.league_name)} · ${fmtDay(m.kickoff)} ${fmtTime(m.kickoff)}</div>
    <div class="mhead">
      <div class="team"><h3>${esc(m.home)}</h3></div>
      <div class="vs muted">–</div>
      <div class="team"><h3>${esc(m.away)}</h3></div>
    </div>
    <div class="card hero">
      <div class="hero-label">İddaa favorisi</div>
      ${Simple.pickBlock(m)}
      ${m.pick ? `<div class="hero-foot">${Slip.button(m, m.pick.market)}</div>` : ""}
    </div>
    ${detail("Detaylar", odds.length ? `<table><tr><th class="l">Seçenek</th><th>iddaa oranı</th></tr>${marketRows}</table>` : `<p class="muted">Bu maç için oran verisi yok.</p>`)}`;
}

function marketText(key, m) {
  const t = {
    "1": `${m.home} kazanır`, "X": "Beraberlik", "2": `${m.away} kazanır`,
    "1X": `${m.home} kaybetmez`, "X2": `${m.away} kaybetmez`, "12": "Beraberlik olmaz",
    "Ü1.5": "2 veya daha fazla gol", "A1.5": "En fazla 1 gol",
    "Ü2.5": "3 veya daha fazla gol", "A2.5": "En fazla 2 gol",
    "Ü3.5": "4 veya daha fazla gol", "A3.5": "En fazla 3 gol",
    "KG Var": "İki takım da gol atar", "KG Yok": "En az bir takım gol atamaz",
    "Ev 0.5Ü": `${m.home} gol atar`, "Dep 0.5Ü": `${m.away} gol atar`,
  };
  return t[key] || key;
}

function detail(title, body, open = false) {
  return `<details class="detail"${open ? " open" : ""}><summary>${title}</summary><div class="detail-body">${body}</div></details>`;
}
async function openMatch(id, competitionId = null) {
  const req = ++state.matchReq;
  $("#modal").classList.remove("hidden");
  $("#modalBody").innerHTML = `<p class="muted">Maç detayı yükleniyor…</p>`;
  let m;
  try {
    const query = competitionId ? `?competition_id=${encodeURIComponent(competitionId)}` : "";
    m = await api(`/api/match/${encodeURIComponent(id)}${query}`);
  } catch (e) {
    if (req !== state.matchReq) return;
    $("#modalBody").innerHTML = `<button class="close" onclick="closeModal()" aria-label="Kapat">×</button><p style="color:var(--bad)">Maç detayı yüklenemedi: ${esc(e.message)}</p>`;
    return;
  }
  if (req !== state.matchReq) return;
  if (m.small_league) { renderSmallMatch(m); return; }
  const f = m.factors, k = m.markets;
  const th = f.table.home, ta = f.table.away;
  const pk = m.pick, s = Simple.info(m);
  const hero = pk
    ? `<div class="hero-label">Bizim önerimiz</div>${Simple.pickBlock(m)}<div class="hero-foot">${Slip.button(m, pk.market)}</div>`
    : `<div class="hero-label">Bizim önerimiz</div>${Simple.pickBlock(m)}`;

  const rowFor = (key, hl) => `<tr${hl ? ' class="hl"' : ""}><td class="l"><b>${esc(Simple.headline(key))}</b> <span class="muted">${esc(marketText(key, m))}</span></td><td>${k[key] ? pct(k[key].p) : "-"}</td><td>${m.iddaa_odds?.[key] ?? "-"}${oddsMove(m, key)}</td><td>${Slip.button(m, key)}</td></tr>`;
  const marketsRows = ["1", "X", "2", "1X", "X2", "Ü2.5", "A2.5", "KG Var", "KG Yok"].map((key) => rowFor(key, pk && pk.market === key)).join("");
  const extra = Object.entries(m.extra_markets || {}).filter(([, item]) => item.p != null).map(([key, item]) =>
    `<tr><td class="l"><b>${esc(key)}</b> <span class="muted">(deneysel)</span></td><td>${pct(item.p)}</td><td>${m.iddaa_odds?.[key] ?? "-"}</td><td></td></tr>`).join("");
  const markets = `<table><tr><th class="l">Seçenek</th><th>Şans</th><th>Oran</th><th></th></tr>${marketsRows}${extra}</table>
    <h4>En olası skorlar</h4><div class="scores">${m.scores.slice(0, 5).map((x) => `<span><b>${x.score}</b> ${pct(x.p)}</span>`).join("")}</div>
    <div id="oddsHistory"></div>`;

  const row = (label, h, a) => `<span>${label}</span><span class="h">${h ?? "-"}</span><span class="a">${a ?? "-"}</span>`;
  const compare = `<div class="kv"><span></span><b class="h">${esc(m.home)}</b><b class="a">${esc(m.away)}</b>
    ${row("Lig sırası", th && th.pos, ta && ta.pos)}
    ${row("Puan", th && th.pts, ta && ta.pts)}
    ${row("Son maçlarda form (maç başı puan)", f.form.home_ppg, f.form.away_ppg)}
    ${row("Eksik oyuncu (haberlere göre)", f.news.home.absences, f.news.away.absences)}
    ${row("Son maçtan beri dinlenme (gün)", f.rest.home_days, f.rest.away_days)}</div>`;

  const news = `<div class="grid2"><div><h4>${esc(m.home)}</h4>${newsList(f.news.home)}</div><div><h4>${esc(m.away)}</h4>${newsList(f.news.away)}</div></div>`;

  $("#modalBody").innerHTML = `
    <button class="close" onclick="closeModal()" aria-label="Kapat">×</button>
    <div class="m-meta">${esc(m.league_name)} · ${fmtDay(m.kickoff)} ${fmtTime(m.kickoff)}</div>
    <div class="mhead">
      <div class="team">${img(m.home_logo)}<h3>${esc(m.home)}</h3></div>
      <div class="vs muted">–</div>
      <div class="team">${img(m.away_logo)}<h3>${esc(m.away)}</h3></div>
    </div>
    <div class="card hero">${hero}</div>
    ${detail("Detaylar", `<h4>Diğer seçenekler</h4>${markets}<h4>Takımlar</h4>${compare}<div id="matchInsights"></div><h4>Haberler</h4>${news}`)}`;
  $("#modal").classList.remove("hidden");
  renderOddsHistory(m);
  renderMatchInsights(m);
}
function closeModal() { state.matchReq += 1; $("#modal").classList.add("hidden"); }
window.closeModal = closeModal;

const TAB_GROUPS = { coupons: ["coupons", "slip", "coupon-history", "ledger"] };
const groupOf = (tab) => Object.keys(TAB_GROUPS).find((g) => TAB_GROUPS[g].includes(tab)) || tab;

async function render() {
  $("#leagueChips").classList.toggle("hidden", state.tab !== "matches");
  try {
    if (state.tab === "matches") await renderMatches();
    if (state.tab === "coupons") await renderCoupons();
    if (state.tab === "slip") await Slip.render();
    if (state.tab === "ledger") Extras.renderLedger();
    if (state.tab === "coupon-history") await renderCouponHistory();
    if (state.tab === "report") await renderModelReport();
  } catch (e) {
    $(`#tab-${state.tab}`).insertAdjacentHTML("afterbegin", Ui.error(e.message));
  }
}

function updateMessage(r) {
  if (r.status === "cooldown") return `Veriler yakın zamanda güncellendi; ${Math.max(1, Math.ceil(r.cooldown_seconds / 60))} dk sonra tekrar güncelleyebilirsiniz.`;
  if (r.status === "busy") return "Başka bir güncelleme sürüyor…";
  if (r.status === "partial" || r.outcome === "partial") return "Veriler kısmen güncellendi. " + (r.error || "Bazı kaynaklara ulaşılamadı.");
  if (r.status === "error" || r.error) return "Hata: " + (r.error || "güncellenemedi");
  return "Güncelleme tamamlandı.";
}

async function showUpdateResult(r) {
  UpdateStatus.apply(state, r);
  showLastUpdate();
  const bar = $("#updateBar");
  bar.classList.remove("hidden");
  bar.textContent = updateMessage(r);
  setTimeout(() => bar.classList.add("hidden"), 5000);
  await loadLeagues();
  render();
}

async function pollUpdate() {
  const s = await api("/api/update/status", { cache: "no-store" });
  const changed = UpdateStatus.apply(state, s);
  showLastUpdate();
  const bar = $("#updateBar");
  $("#btnUpdate").disabled = s.running;
  if (s.running) {  // başka biri (veya cron) güncelliyor
    bar.classList.remove("hidden");
    bar.textContent = "Güncelleniyor: " + (s.message || "lütfen bekleyin");
    setTimeout(() => pollUpdate().catch(showLastUpdate), 3000);
  } else if (!bar.classList.contains("hidden")) {
    await showUpdateResult(s);
  } else if (changed) {
    await loadLeagues();
    await render();
  }
}
$("#leagueChips").addEventListener("click", (e) => {
  const smallToggle = e.target.closest("[data-small-leagues-toggle]");
  if (smallToggle) {
    state.smallLeaguesOpen = !state.smallLeaguesOpen;
    renderLeagueChips();
    return;
  }
  const chip = e.target.closest(".chip[data-league]");
  if (chip) {
    state.league = chip.dataset.league;
    state.smallLeaguesOpen = state.league.startsWith("small:");
    localStorage.setItem("league", state.league);
    renderLeagueChips();
    render();
  }
});

function setTab(name) {
  const group = groupOf(name);
  document.querySelectorAll(".tabs button[data-tab]").forEach((b) => {
    const on = b.dataset.tab === group;
    b.classList.toggle("active", on);
    if (on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  document.querySelectorAll("#couponSeg button[data-tab]").forEach((b) => {
    const on = b.dataset.tab === name;
    b.classList.toggle("active", on);
    b.setAttribute("aria-pressed", String(on));
  });
  $("#couponSeg").classList.toggle("hidden", group !== "coupons");
  state.tab = name;
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("hidden", s.id !== "tab-" + name));
}
document.addEventListener("click", (e) => {
  const tab = e.target.closest(".tabs button[data-tab], #couponSeg button[data-tab]");
  if (!tab) return;
  setTab(tab.dataset.tab);
  window.scrollTo({ top: 0 });
  render();
});
MatchEvents.bind(document, openMatch, closeModal);

$("#btnUpdate").addEventListener("click", async () => {
  const btn = $("#btnUpdate"), bar = $("#updateBar");
  btn.disabled = true;
  bar.classList.remove("hidden");
  bar.textContent = "Maçlar ve oranlar güncelleniyor… Birkaç dakika sürebilir.";
  try {
    const r = await api("/api/update", { method: "POST" });
    if (r.status === "busy") pollUpdate(); else await showUpdateResult(r);
  } catch (e) {
    bar.textContent = "Hata: " + e.message;
  } finally {
    btn.disabled = false;
  }
});
$("#couponDate").value = state.couponDate;
function setCouponDay(day) { if (!day) return; state.couponDate = day; $("#couponDate").value = day; renderCoupons().catch((e) => { $("#coupons").innerHTML = `<div class="card" style="color:var(--bad)">Hata: ${esc(e.message)}</div>`; }); }
$("#couponDate").addEventListener("change", (e) => setCouponDay(e.target.value));
function shiftCouponDay(n) { const d = new Date(state.couponDate + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); setCouponDay(d.toISOString().slice(0, 10)); }
$("#couponPrev").addEventListener("click", () => shiftCouponDay(-1));
$("#couponNext").addEventListener("click", () => shiftCouponDay(1));

setInterval(() => {
  if (!document.hidden) pollUpdate().catch(showLastUpdate);
  else showLastUpdate();
}, 30000);
setInterval(() => { if (!document.hidden) refreshLive(); }, 60000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshLive(); });
(async () => {
  await refreshLive();
  await loadLeagues();
  const hashTab = location.hash.slice(1);
  if (document.getElementById("tab-" + hashTab)) setTab(hashTab);
  render();
  pollUpdate().catch(showLastUpdate);
  const sharedMatch = new URLSearchParams(location.search).get("match");  // SEO sayfasından gelen /?match=<id>
  if (sharedMatch) openMatch(sharedMatch);
})();
