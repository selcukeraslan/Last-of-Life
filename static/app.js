const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (p) => (p * 100).toFixed(0) + "%";
const api = async (url, opts) => {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.text()) || r.status);
  return r.json();
};

const savedLeague = localStorage.getItem("league") || "tur.1";
const state = { league: savedLeague, tab: "matches", leagues: [], model: {}, smallLeaguesOpen: savedLeague.startsWith("small:"), picksCategory: "main", couponDate: new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" }), couponReq: 0, matchReq: 0, live: new Map() };

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
  } catch { /* canlı skor geçici olarak alınamazsa mevcut görünüm korunur */ }
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
  el.textContent = iso ? fmtAgo(iso) + " güncellendi" : "Henüz veri yok";
  el.title = iso ? fmtDateTime(iso) : "";
}
function confBadge(label, reason) { return `<span class="badge ${label === "Yüksek" ? "b-good" : label === "Orta" ? "b-warn" : "b-bad"}"${reason ? ` title="${esc(reason)}"` : ""}>${label} güven</span>`; }
function formDots(s) { return `<span class="formdots">${[...(s || "")].map((c) => `<span class="f-${c}">${c}</span>`).join("")}</span>`; }
function img(src) { return src ? `<img src="${esc(src)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : ""; }
function oddsValue(iddaa, claude, move = "") {
  return `<b class="iddaa-odd">${iddaa ?? "-"}</b><span class="claude-odd">Claude oran: ${claude ?? "-"}</span>${move}`;
}
function matchOddsValue(match, market, move = "") {
  if (!match.small_league) return oddsValue(match.iddaa_odds?.[market], match.markets[market]?.suggested, move);
  const odd = match.iddaa_odds?.[market];
  return `<b class="iddaa-odd">${odd ?? "-"}</b>${odd == null
    ? `<span class="claude-odd">iddaa oranı yok</span>`
    : `<span class="src src-iddaa">iddaa</span>`}${move}`;
}
function matchProbability(match, market) {
  const probability = match.markets?.[market]?.p;
  if (!Number.isFinite(probability)) return "veri yok";
  return `${match.small_league ? "piyasa " : ""}${pct(probability)}`;
}

function renderLeagueChips() {
  const main = state.leagues.map((l) =>
    `<button type="button" class="chip ${l.id === state.league ? "active" : ""}" data-league="${esc(l.id)}">${esc(l.name)} <span class="muted">${l.played || 0}</span></button>`).join("");
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
  $("#leagueChips").innerHTML = `<div class="league-group main-league-group"><b>Ana Ligler</b>${main}</div>` +
    (groups.length ? `<div class="league-picker"><button type="button" class="chip small-leagues-toggle ${activeSmall ? "active" : ""}" data-small-leagues-toggle aria-expanded="${state.smallLeaguesOpen}" aria-controls="smallLeagueOptions">Küçük Ligler <span class="muted">${state.smallLeagues.length}</span></button>
      <div id="smallLeagueOptions" class="small-league-options ${state.smallLeaguesOpen ? "" : "hidden"}">${smallOptions}</div></div>` : "");
}

async function loadLeagues() {
  const d = await api("/api/leagues");
  state.leagues = d.leagues;
  state.smallLeagues = d.small_leagues || [];
  const selected = [...state.leagues, ...state.smallLeagues].find((l) =>
    l.id === state.league || l.slug === state.league || l.name === state.league || l.aliases?.includes(state.league));
  state.league = selected?.id || state.leagues[0]?.id || "tur.1";
  localStorage.setItem("league", state.league);
  state.model = d.model;
  state.lastUpdate = d.last_update;
  showLastUpdate();
  $("#marginPct").textContent = Math.round(d.model.margin * 100);
  $("#params").innerHTML = `<table>${Object.entries(d.model).map(([k, v]) => `<tr><td class="l"><code>${k}</code></td><td>${v}</td></tr>`).join("")}</table>`;
  renderLeagueChips();
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
    const k = m.markets;
    const detailId = m.small_league ? (m.iddaa_event_id || m.id) : m.id;
    const has1x2Probabilities = ["1", "X", "2"].every((key) => Number.isFinite(k[key]?.p));
    const live = state.live.get(String(m.id));
    html += `<div class="card match" data-home="${esc(m.home)}" data-away="${esc(m.away)}" data-id="${esc(m.id)}" data-match-id="${esc(detailId)}" data-event-id="${esc(m.iddaa_event_id || (m.small_league ? m.id : ""))}" data-competition-id="${esc(m.competition_id ?? "")}" role="button" tabindex="0" aria-label="${esc(m.home)} - ${esc(m.away)} maç detayı">
      <div class="time">${live ? liveBadge(live) : fmtTime(m.kickoff)}</div>
      <div class="teams">
        <div>${window.Extras ? Extras.star(m.home) : ""}${img(m.home_logo)}<b>${esc(m.home)}</b><span class="xg">${Number.isFinite(m.lambda_home) ? m.lambda_home.toFixed(2) + " xG" : "xG verisi yok"}</span></div>
        <div>${window.Extras ? Extras.star(m.away) : ""}${img(m.away_logo)}<b>${esc(m.away)}</b><span class="xg">${Number.isFinite(m.lambda_away) ? m.lambda_away.toFixed(2) + " xG" : "xG verisi yok"}</span></div>
      </div>
      <div>
        ${has1x2Probabilities ? `<div class="probbar"><div class="h" style="width:${k["1"].p * 100}%"></div><div class="d" style="width:${k["X"].p * 100}%"></div><div class="a" style="width:${k["2"].p * 100}%"></div></div>` : `<div class="muted">Olasılık verisi yok</div>`}
        <div class="odds3">
          ${["1", "X", "2"].map((s) => `<div class="odd"><small>${s} · ${matchProbability(m, s)}</small>${matchOddsValue(m, s, oddsMove(m, s))}</div>`).join("")}
        </div>
      </div>
      <div class="pick">
        ${m.pick ? `<div><span class="badge b-info">${esc(m.pick.market)}</span> ${matchOddsValue(m, m.pick.market, oddsMove(m, m.pick.market))}</div><div class="muted" style="font-size:12px">olasılık ${pct(m.pick.p)}</div>` : (m.small_league ? `<div class="muted">Model önerisi yok</div>` : "")}
        <div style="margin-top:4px">${m.small_league ? `<span class="badge b-info">Model verisi yok</span>` : confBadge(m.confidence_label, m.confidence_reason)}</div>
        ${m.pick ? Slip.button(m, m.pick.market) : ""}
      </div>
    </div>`;
  }
  el.innerHTML = (window.Extras ? Extras.filterButton() : "") + (leagueTitle ? `<div class="day-head">${leagueTitle}</div>` : "") + html;
  window.Extras?.afterMatches(list);
}

async function renderPicks() {
  const el = $("#picks");
  el.innerHTML = `<p class="muted">Yükleniyor…</p>`;
  const small = state.picksCategory === "small";
  $("#pickConfControl").classList.toggle("hidden", small);
  const list = await api(`/api/picks?category=${state.picksCategory}&days=${$("#pickDays").value}&min_conf=${$("#pickConf").value}`);
  if (!list.length) { el.innerHTML = `<div class="card muted">${small ? "Tam 1X2 bülteni ve en az %50 piyasa olasılığı olan küçük lig maçı yok." : "Öneri yok."}</div>`; return; }
  const footnote = small
    ? "Yalnızca tam İddaa 1X2 bülteninden hesaplanan piyasa olasılığı gösterilir. Bağımsız model tahmini, takım formu ve değer bahsi hesabı yoktur."
    : "Kombine kuponda olasılıklar çarpılır: 3 maçlık %70'lik kupon ≈ %34 tutar.";
  el.innerHTML = `<div class="card"><table>
    <tr><th class="l">Maç</th><th>Lig</th><th>Tarih</th><th>${small ? "Pazar" : "Tahmin"}</th><th>Olasılık</th><th>Oranlar</th><th>${small ? "Model verisi" : "Güven"}</th></tr>
    ${list.slice(0, 40).map((p) => `<tr class="clickable" data-match-id="${esc(p.id)}" data-competition-id="${esc(p.competition_id ?? "")}" role="button" tabindex="0" style="cursor:pointer">
      <td class="l"><b>${esc(p.home)}</b> – ${esc(p.away)}</td><td>${esc(p.league_name)}</td>
      <td>${fmtDateTime(p.kickoff)}</td><td>${small ? `<span class="badge b-info">${esc(p.pick.market)}</span> <span class="muted">${esc(p.recommendation_label || "İddaa piyasa favorisi")}</span>` : `<span class="badge b-info">${esc(p.pick.market)}</span>`}</td>
      <td>${pct(p.pick.p)}${small ? `<span class="muted"> piyasa</span>` : ""}</td>
      <td>${small && p.recommendation_source === "iddaa_market"
        ? `<b class="iddaa-odd">${esc(p.pick.odds ?? p.iddaa_odds?.[p.pick.market] ?? "-")}</b><span class="src src-iddaa">iddaa</span>`
        : oddsValue(p.iddaa_odds?.[p.pick.market], p.pick.suggested, oddsMove(p, p.pick.market))}</td>
      <td>${small ? `<span class="badge b-info">Model verisi yok</span>` : confBadge(p.confidence_label, p.confidence_reason)}</td></tr>`).join("")}
  </table><p class="muted">${footnote}</p></div>`;
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
  if (!state.leagues.some((l) => l.id === state.league)) {
    el.innerHTML = `<div class="card muted">Bu lig için puan durumu mevcut değil.</div>`;
    return;
  }
  el.innerHTML = `<p class="muted">Yükleniyor…</p>`;
  let rows;
  try {
    const query = new URLSearchParams({ league: state.league });
    rows = await api(`/api/standings?${query}`);
  } catch (e) {
    el.innerHTML = `<div class="card muted">Puan durumu yüklenemedi: ${esc(e.message)}</div>`;
    return;
  }
  el.innerHTML = `<div class="card"><table>
    <tr><th>#</th><th class="l">Takım</th><th>O</th><th>G</th><th>B</th><th>M</th><th>A</th><th>Y</th><th>AV</th><th>P</th><th>Ev P/M</th><th>Dep P/M</th><th>Form</th><th>Elo</th></tr>
    ${rows.map((r) => `<tr><td>${r.pos}</td><td class="l">${esc(r.team)}</td><td>${r.p}</td><td>${r.w}</td><td>${r.d}</td><td>${r.l}</td>
      <td>${r.gf}</td><td>${r.ga}</td><td>${r.gd > 0 ? "+" : ""}${r.gd}</td><td><b>${r.pts}</b></td>
      <td>${r.hp ? (r.hpts / r.hp).toFixed(2) : "-"}</td><td>${r.ap ? (r.apts / r.ap).toFixed(2) : "-"}</td>
      <td>${formDots(r.form)}</td><td>${r.elo}</td></tr>`).join("")}
  </table></div>`;
}

async function renderModel() {
  const d = await api("/api/backtest");
  renderBlendBacktest(d);
  const el = $("#backtest");
  $("#btnBacktest").disabled = d.running;
  if (d.running) { el.innerHTML = `<p class="muted">Test çalışıyor… (birkaç dakika sürebilir)</p>`; setTimeout(renderModel, 4000); return; }
  if (!d.data) { el.innerHTML = `<p class="muted">Henüz test çalıştırılmadı.</p>`; return; }
  const name = Object.fromEntries(state.leagues.map((l) => [l.id, l.name]));
  el.innerHTML = `<table><tr><th class="l">Lig</th><th>Test edilen maç</th><th>1X2 isabet</th><th>Brier</th><th>Log-loss</th><th>Ü/A 2.5 isabet</th></tr>
    ${Object.values(d.data.results).map((r) => `<tr><td class="l">${esc(name[r.league] || r.league)}</td><td>${r.n}</td>
      <td>${r.n ? pct(r.accuracy_1x2) : "-"}</td><td>${r.brier ?? "-"}</td><td>${r.logloss ?? "-"}</td><td>${r.n ? pct(r.accuracy_ou25) : "-"}</td></tr>`).join("")}
  </table><p class="muted">Son test: ${fmtDateTime(d.data.at)}</p>`;
}

function newsList(n) {
  if (!n.items.length) return `<p class="muted">Son 7 günde haber bulunamadı.</p>`;
  return `<ul class="news">${n.items.map((i) => `<li>
    ${i.injury ? `<span class="badge b-bad">sakatlık/ceza</span>` : ""}
    <span class="badge ${i.sentiment > 0 ? "b-good" : i.sentiment < 0 ? "b-bad" : "b-info"}">${i.sentiment > 0 ? "+" : ""}${i.sentiment}</span>
    <a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a> <span class="muted">· ${esc(i.source)} · ${fmtDateTime(i.published)}</span></li>`).join("")}</ul>`;
}

function formList(f) {
  if (!f.length) return `<span class="muted">veri yok</span>`;
  return f.map((x) => `<div><span class="formdots"><span class="f-${x.result}">${x.result}</span></span> ${x.venue} ${x.gf}-${x.ga} ${esc(x.opponent)} <span class="muted">${x.date}</span></div>`).join("");
}

function renderSmallMatch(m) {
  const order = ["1", "X", "2", "1X", "12", "X2", "Ü1.5", "A1.5", "Ü2.5", "A2.5", "Ü3.5", "A3.5", "KG Var", "KG Yok"];
  const odds = Object.entries(m.iddaa_odds || {}).sort((a, b) => {
    const ai = order.indexOf(a[0]), bi = order.indexOf(b[0]);
    return (ai < 0 ? order.length : ai) - (bi < 0 ? order.length : bi) || a[0].localeCompare(b[0]);
  });
  const marketRows = odds.map(([market, odd]) => {
    const probability = m.markets?.[market]?.market_p;
    return `<tr><td class="l"><b>${esc(market)}</b></td><td><b class="iddaa-odd">${Number(odd).toFixed(2)}</b></td>
      <td>${Number.isFinite(probability) ? pct(probability) : `<span class="muted">kaynakta yok</span>`}</td></tr>`;
  }).join("");
  const updated = m.iddaa_updated_at ? fmtDateTime(m.iddaa_updated_at) : "bilinmiyor";
  const sourceSummary = odds.length ? "Bültende gerçek event oranları var." : "Bu event için bültende oran verisi yok.";
  $("#modalBody").innerHTML = `
    <button class="close" onclick="closeModal()">×</button>
    <div class="muted" style="text-align:center">${esc(m.league_name)} · ${fmtDay(m.kickoff)} ${fmtTime(m.kickoff)}</div>
    <div style="text-align:center"><a class="muted" href="/mac/${encodeURIComponent(m.id)}" target="_blank" rel="noopener">🔗 Paylaş linki</a></div>
    <div class="mhead">
      <div class="team"><h3>${esc(m.home)}</h3><div class="muted">Takım verisi yok</div></div>
      <div><div class="vs">vs</div><div class="muted">başlama saati</div></div>
      <div class="team"><h3>${esc(m.away)}</h3><div class="muted">Takım verisi yok</div></div>
    </div>
    <div class="card row-between">
      <div><b>Model tahmini yok</b><p class="muted">${sourceSummary} Bu görünümde takım formu, puan durumu, xG, skor ve haber verisi sağlanmadığı için model tahmini sunulmuyor.</p></div>
      <div><span class="badge b-info">İddaa bülteni</span></div>
    </div>
    <div class="card">
      <h3>Gerçek iddaa bülten oranları</h3>
      <p class="muted">Olasılık, yalnızca ilgili pazarın oran seti tam olduğunda marjı arındırılmış piyasa değeridir. Model oranı veya öneri üretilmez.</p>
      ${odds.length ? `<table><tr><th class="l">Pazar</th><th>İddaa oranı</th><th>Piyasa olasılığı</th></tr>${marketRows}</table>` : `<p class="muted">Bu event için bültende oran verisi yok.</p>`}
    </div>
    <div class="card">
      <h3>Kaynak ve maç bilgisi</h3>
      <div class="kv">
        <span>Event ID</span><b>${esc(m.iddaa_event_id || m.event_id || m.id)}</b>
        <span>Competition ID</span><b>${m.competition_id == null ? "kaynakta yok" : esc(m.competition_id)}</b>
        <span>Oran verisi güncellemesi</span><b>${esc(updated)}</b>
      </div>
      <p class="muted">Puan durumu, takım formu, xG, önceki skorlar ve sakatlık/haber alanları bu bülten kaynağında bulunmuyor.</p>
    </div>`;
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
    $("#modalBody").innerHTML = `<button class="close" onclick="closeModal()">×</button><p style="color:var(--bad)">Maç detayı yüklenemedi: ${esc(e.message)}</p>`;
    return;
  }
  if (req !== state.matchReq) return;
  if (m.small_league) { renderSmallMatch(m); return; }
  const f = m.factors, k = m.markets;
  const th = f.table.home, ta = f.table.away;
  const pk = m.pick;
  const iddaaPick = pk ? m.iddaa_odds?.[pk.market] : null;
  const hero = pk
    ? `<div class="hero-label">Model önerisi</div>
       <div class="hero-pick"><span class="hero-market">${esc(pk.market)}</span> ${esc(marketText(pk.market, m))}</div>
       <div class="hero-stats">
         <div><div class="hero-num">${pct(pk.p)}</div><div class="muted">olasılık</div></div>
         <div><div class="hero-num">${pk.suggested}</div><div class="muted">önerilen oran</div></div>
         ${iddaaPick ? `<div><div class="hero-num ${iddaaPick >= pk.suggested ? "good" : ""}">${iddaaPick}</div><div class="muted">iddaa oranı</div></div>` : ""}
       </div>
       <div class="hero-foot">${confBadge(m.confidence_label, m.confidence_reason)}<span class="muted">${esc(m.confidence_reason || "")}</span>${iddaaPick ? `<span class="muted">${iddaaPick >= pk.suggested ? "iddaa oranı önerilen orandan yüksek, oynamaya değer." : "iddaa oranı önerilen orandan düşük."}</span>` : ""}</div>
       <div class="hero-foot">${Slip.button(m, pk.market)}</div>`
    : `<div class="hero-label">Model önerisi</div><div class="hero-pick">Bu maç için belirgin bir öneri yok</div><div class="hero-foot">${confBadge(m.confidence_label, m.confidence_reason)}<span class="muted">${esc(m.confidence_reason || "")}</span></div>`;

  const marketsRows = ["1", "X", "2", "1X", "X2", "Ü2.5", "A2.5", "KG Var", "KG Yok"].map((key) =>
    `<tr${pk && pk.market === key ? ' class="hl"' : ""}><td class="l"><b>${esc(key)}</b> <span class="muted">${esc(marketText(key, m))}</span>${blendDetail(k[key])}</td><td>${pct(k[key].p)}</td><td>${k[key].suggested ?? "-"}</td><td>${m.iddaa_odds?.[key] ?? "-"}${oddsMove(m, key)}</td><td>${Slip.button(m, key)}</td></tr>`).join("");
  const extra = Object.entries(m.extra_markets || {}).map(([key, item]) =>
    `<tr><td class="l"><b>${esc(key)}</b></td><td>${item.p == null ? "-" : pct(item.p)}</td><td>${item.suggested ?? "-"}</td><td>${m.iddaa_odds?.[key] ?? "-"}</td><td></td></tr>`).join("");
  const markets = `${blendNote(m)}<table><tr><th class="l">Tahmin</th><th>Olasılık</th><th>Önerilen</th><th>iddaa</th><th></th></tr>${marketsRows}${extra}</table>
    <h4>En olası skorlar</h4><div class="scores">${m.scores.slice(0, 6).map((s) => `<span><b>${s.score}</b> ${pct(s.p)}</span>`).join("")}</div>
    <div id="oddsHistory"></div>`;

  const row = (label, h, a) => `<span>${label}</span><span class="h">${h ?? "-"}</span><span class="a">${a ?? "-"}</span>`;
  const compare = `<div class="kv"><span></span><b class="h">${esc(m.home)}</b><b class="a">${esc(m.away)}</b>
    ${row("Lig sırası", th && th.pos, ta && ta.pos)}
    ${row("Puan", th && th.pts, ta && ta.pts)}
    ${row("Beklenen gol", m.lambda_home.toFixed(2), m.lambda_away.toFixed(2))}
    ${row("Form (son maçlar, maç başı puan)", f.form.home_ppg, f.form.away_ppg)}
    ${row("Güç puanı (Elo)", f.elo.home, f.elo.away)}
    ${row("Sakatlık/ceza haberi", f.news.home.injuries, f.news.away.injuries)}
    ${row("Dinlenme (gün)", f.rest.home_days, f.rest.away_days)}</div>`;

  const recent = `<div class="grid2"><div><b style="color:var(--home)">${esc(m.home)}</b>${formList(f.form.home)}</div>
      <div><b style="color:var(--away)">${esc(m.away)}</b>${formList(f.form.away)}</div></div>
    <h4>Aralarındaki son maçlar</h4>
    ${f.h2h.length ? f.h2h.map((h) => `<div>${h.date} · ${esc(h.home)} <b>${h.score}</b> ${esc(h.away)}</div>`).join("") : `<span class="muted">Veri setinde yok</span>`}
    <div id="matchInsights"></div>`;

  const news = `<div class="grid2"><div><h4>${esc(m.home)}</h4>${newsList(f.news.home)}</div><div><h4>${esc(m.away)}</h4>${newsList(f.news.away)}</div></div>`;

  $("#modalBody").innerHTML = `
    <button class="close" onclick="closeModal()" aria-label="Kapat">×</button>
    <div class="muted" style="text-align:center">${esc(m.league_name)} · ${fmtDay(m.kickoff)} ${fmtTime(m.kickoff)}</div>
    <div class="mhead">
      <div class="team">${img(m.home_logo)}<h3>${esc(m.home)}</h3></div>
      <div class="vs muted">–</div>
      <div class="team">${img(m.away_logo)}<h3>${esc(m.away)}</h3></div>
    </div>
    <div class="card hero">${hero}</div>
    <div class="card">
      <div class="probbar big"><div class="h" style="width:${k["1"].p * 100}%"></div><div class="d" style="width:${k["X"].p * 100}%"></div><div class="a" style="width:${k["2"].p * 100}%"></div></div>
      <div class="prob3"><span style="color:var(--home)">1 · ${pct(k["1"].p)}</span><span>X · ${pct(k["X"].p)}</span><span style="color:var(--away)">2 · ${pct(k["2"].p)}</span></div>
    </div>
    <div class="details-head muted">Ayrıntılar</div>
    ${detail("Diğer tahminler ve skorlar", markets)}
    ${detail("Takım karşılaştırması", compare)}
    ${detail("Son maçlar", recent)}
    ${detail("Haberler", news)}`;
  $("#modal").classList.remove("hidden");
  renderOddsHistory(m);
  renderMatchInsights(m);
}
function closeModal() { state.matchReq += 1; $("#modal").classList.add("hidden"); }
window.closeModal = closeModal;

async function render() {
  $("#leagueChips").classList.toggle("hidden", state.tab === "picks" || state.tab === "model" || state.tab === "value" || state.tab === "ledger");
  try {
    if (state.tab === "matches") await renderMatches();
    if (state.tab === "picks") await renderPicks();
    if (state.tab === "table") await renderTable();
    if (state.tab === "coupons") await renderCoupons();
    if (state.tab === "value") await renderValue();
    if (state.tab === "slip") await Slip.render();
    if (state.tab === "ledger") Extras.renderLedger();
    if (state.tab === "model") await renderModel();
  } catch (e) {
    $(`#tab-${state.tab}`).insertAdjacentHTML("afterbegin", Ui.error(e.message));
  }
}

function updateMessage(r) {
  if (r.status === "cooldown") return `Veriler yakın zamanda güncellendi; ${Math.max(1, Math.ceil(r.cooldown_seconds / 60))} dk sonra tekrar güncelleyebilirsiniz.`;
  if (r.status === "busy") return "Başka bir güncelleme sürüyor…";
  if (r.status === "error" || r.error) return "Hata: " + (r.error || "güncellenemedi");
  return "Güncelleme tamamlandı.";
}

async function showUpdateResult(r) {
  const bar = $("#updateBar");
  bar.classList.remove("hidden");
  bar.textContent = updateMessage(r);
  setTimeout(() => bar.classList.add("hidden"), 5000);
  await loadLeagues();
  render();
}

async function pollUpdate() {
  const s = await api("/api/update/status");
  const bar = $("#updateBar");
  $("#btnUpdate").disabled = s.running;
  if (s.running) {  // başka biri (veya cron) güncelliyor
    bar.classList.remove("hidden");
    bar.textContent = "Güncelleniyor: " + (s.message || "lütfen bekleyin");
    setTimeout(pollUpdate, 3000);
  } else if (!bar.classList.contains("hidden")) {
    await showUpdateResult(s);
  }
}

$("#pickCategories").addEventListener("click", (e) => {
  const picksCategory = e.target.closest("[data-picks-category]");
  if (picksCategory) {
    state.picksCategory = picksCategory.dataset.picksCategory;
    document.querySelectorAll("[data-picks-category]").forEach((button) => {
      const active = button === picksCategory;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    $("#pickConfControl").classList.toggle("hidden", state.picksCategory === "small");
    renderPicks();
  }
});

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
  document.querySelectorAll(".tabs button[data-tab]").forEach((b) => {
    const on = b.dataset.tab === name;
    b.classList.toggle("active", on);
    if (on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  $("#moreBtn").classList.toggle("active", !!$("#morePanel [data-tab].active"));
  state.tab = name;
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("hidden", s.id !== "tab-" + name));
}
function toggleMore(open) {
  const on = open ?? !$("#morePanel").classList.contains("open");
  $("#morePanel").classList.toggle("open", on);
  $("#moreBtn").setAttribute("aria-expanded", String(on));
}
document.addEventListener("click", (e) => {
  if (e.target.closest("#moreBtn")) { toggleMore(); return; }
  const tab = e.target.closest(".tabs button[data-tab]");
  if (tab) {
    setTab(tab.dataset.tab);
    toggleMore(false);
    window.scrollTo({ top: 0 });
    render();
  } else if (!e.target.closest("#morePanel")) toggleMore(false);
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") toggleMore(false); });
MatchEvents.bind(document, openMatch, closeModal);
$("#btnUpdate").addEventListener("click", async () => {
  const btn = $("#btnUpdate"), bar = $("#updateBar");
  btn.disabled = true;
  bar.classList.remove("hidden");
  bar.textContent = "Güncelleniyor… (birkaç saniye sürebilir)";
  try {
    const r = await api("/api/update", { method: "POST" });
    if (r.status === "busy") pollUpdate(); else await showUpdateResult(r);
  } catch (e) {
    bar.textContent = "Hata: " + e.message;
  } finally {
    btn.disabled = false;
  }
});
$("#btnBacktest").addEventListener("click", async () => { await api("/api/backtest", { method: "POST" }); renderModel(); });
$("#pickDays").addEventListener("change", renderPicks);
$("#pickConf").addEventListener("change", renderPicks);
$("#couponDate").value = state.couponDate;
function setCouponDay(day) { if (!day) return; state.couponDate = day; $("#couponDate").value = day; renderCoupons().catch((e) => { $("#coupons").innerHTML = `<div class="card" style="color:var(--bad)">Hata: ${esc(e.message)}</div>`; }); }
$("#couponDate").addEventListener("change", (e) => setCouponDay(e.target.value));
function shiftCouponDay(n) { const d = new Date(state.couponDate + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); setCouponDay(d.toISOString().slice(0, 10)); }
$("#couponPrev").addEventListener("click", () => shiftCouponDay(-1));
$("#couponNext").addEventListener("click", () => shiftCouponDay(1));

setInterval(showLastUpdate, 30000);
setInterval(() => { if (!document.hidden) refreshLive(); }, 60000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshLive(); });
(async () => {
  await refreshLive();
  await loadLeagues();
  render();
  pollUpdate();
  const sharedMatch = new URLSearchParams(location.search).get("match");  // SEO sayfasından gelen /?match=<id>
  if (sharedMatch) openMatch(sharedMatch);
})();
