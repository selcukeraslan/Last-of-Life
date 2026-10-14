const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (p) => (p * 100).toFixed(0) + "%";
const api = async (url, opts) => {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.text()) || r.status);
  return r.json();
};

const state = { league: localStorage.getItem("league") || "tur.1", tab: "matches", leagues: [], model: {}, couponDate: new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" }), couponReq: 0 };

function fmtTime(iso) { return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }); }
function fmtDay(iso) { return new Date(iso).toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" }); }
function fmtDateTime(iso) { return new Date(iso).toLocaleString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
function confBadge(label, reason) { return `<span class="badge ${label === "Yüksek" ? "b-good" : label === "Orta" ? "b-warn" : "b-bad"}"${reason ? ` title="${esc(reason)}"` : ""}>${label} güven</span>`; }
function formDots(s) { return `<span class="formdots">${[...(s || "")].map((c) => `<span class="f-${c}">${c}</span>`).join("")}</span>`; }
function img(src) { return src ? `<img src="${esc(src)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : ""; }
function oddsValue(iddaa, claude) {
  return `<b class="iddaa-odd">${iddaa ?? "-"}</b><span class="claude-odd">Claude oran: ${claude ?? "-"}</span>`;
}

async function loadLeagues() {
  const d = await api("/api/leagues");
  state.leagues = d.leagues;
  state.model = d.model;
  $("#lastUpdate").textContent = d.last_update ? "Son güncelleme: " + fmtDateTime(d.last_update) : "Henüz veri yok";
  $("#marginPct").textContent = Math.round(d.model.margin * 100);
  $("#params").innerHTML = `<table>${Object.entries(d.model).map(([k, v]) => `<tr><td class="l"><code>${k}</code></td><td>${v}</td></tr>`).join("")}</table>`;
  $("#leagueChips").innerHTML = d.leagues.map((l) =>
    `<button class="chip ${l.id === state.league ? "active" : ""}" data-league="${l.id}">${esc(l.name)} <span class="muted">${l.played || 0}</span></button>`).join("");
}

async function renderMatches() {
  const el = $("#matches");
  el.innerHTML = `<p class="muted">Yükleniyor…</p>`;
  const list = await api(`/api/upcoming?league=${state.league}&days=14`);
  if (!list.length) { el.innerHTML = `<div class="card muted">Önümüzdeki 14 günde maç bulunamadı. Verileri güncellemeyi deneyin.</div>`; return; }
  let html = "", lastDay = "";
  for (const m of list) {
    const day = fmtDay(m.kickoff);
    if (day !== lastDay) { html += `<div class="day-head">${day}</div>`; lastDay = day; }
    const k = m.markets;
    html += `<div class="card match" data-id="${m.id}" role="button" tabindex="0" aria-label="${esc(m.home)} - ${esc(m.away)} maç detayı">
      <div class="time">${fmtTime(m.kickoff)}</div>
      <div class="teams">
        <div>${img(m.home_logo)}<b>${esc(m.home)}</b><span class="xg">${m.lambda_home.toFixed(2)} xG</span></div>
        <div>${img(m.away_logo)}<b>${esc(m.away)}</b><span class="xg">${m.lambda_away.toFixed(2)} xG</span></div>
      </div>
      <div>
        <div class="probbar"><div class="h" style="width:${k["1"].p * 100}%"></div><div class="d" style="width:${k["X"].p * 100}%"></div><div class="a" style="width:${k["2"].p * 100}%"></div></div>
        <div class="odds3">
          ${["1", "X", "2"].map((s) => `<div class="odd"><small>${s} · ${pct(k[s].p)}</small>${oddsValue(m.iddaa_odds[s], k[s].suggested)}</div>`).join("")}
        </div>
      </div>
      <div class="pick">
        ${m.pick ? `<div><span class="badge b-info">${esc(m.pick.market)}</span> ${oddsValue(m.iddaa_odds[m.pick.market], m.pick.suggested)}</div><div class="muted" style="font-size:12px">olasılık ${pct(m.pick.p)}</div>` : ""}
        <div style="margin-top:4px">${confBadge(m.confidence_label, m.confidence_reason)}</div>
      </div>
    </div>`;
  }
  el.innerHTML = html;
}

async function renderPicks() {
  const el = $("#picks");
  el.innerHTML = `<p class="muted">Yükleniyor…</p>`;
  const list = await api(`/api/picks?days=${$("#pickDays").value}&min_conf=${$("#pickConf").value}`);
  if (!list.length) { el.innerHTML = `<div class="card muted">Öneri yok.</div>`; return; }
  el.innerHTML = `<div class="card"><table>
    <tr><th class="l">Maç</th><th>Lig</th><th>Tarih</th><th>Tahmin</th><th>Olasılık</th><th>Oranlar</th><th>Güven</th></tr>
    ${list.slice(0, 40).map((p) => `<tr class="clickable" data-id="${p.id}" style="cursor:pointer">
      <td class="l"><b>${esc(p.home)}</b> – ${esc(p.away)}</td><td>${esc(p.league_name)}</td>
      <td>${fmtDateTime(p.kickoff)}</td><td><span class="badge b-info">${esc(p.pick.market)}</span></td>
      <td>${pct(p.pick.p)}</td><td>${oddsValue(p.iddaa_odds[p.pick.market], p.pick.suggested)}</td><td>${confBadge(p.confidence_label, p.confidence_reason)}</td></tr>`).join("")}
  </table><p class="muted">Kombine kuponda olasılıklar çarpılır: 3 maçlık %70'lik kupon ≈ %34 tutar.</p></div>`;
}

function couponOdds(p) {
  const claude = `Claude oran: ${p.claude_odds}`;
  return p.odds_source === "iddaa"
    ? `<b class="iddaa-odd">${p.odds}</b><span class="src src-iddaa">iddaa</span><span class="claude-odd">${claude}</span>`
    : `<b class="iddaa-odd">${p.odds}</b><span class="src src-claude">Claude oran</span><span class="claude-odd">iddaa oranı yok</span>`;
}
function couponSource(c) {
  if (!c.picks.length) return "";
  if (c.odds_source === "iddaa") return `<span class="badge b-info">oranlar: iddaa</span>`;
  if (c.odds_source === "claude") return `<span class="badge b-warn">oranlar: Claude oran</span>`;
  return `<span class="badge b-info">oranlar: ${c.iddaa_picks}/${c.picks.length} iddaa, kalanı Claude oran</span>`;
}
function couponCard(c, title, cls) {
  const rows = c.picks.length ? c.picks.map((p) => `<tr><td class="l"><b>${esc(p.home)}</b> – ${esc(p.away)}</td><td>${esc(p.league_name)}</td><td>${fmtDateTime(p.kickoff)}</td><td><span class="badge ${cls}">${esc(p.market)}</span></td><td>${couponOdds(p)}</td><td>${pct(p.model_probability)}</td></tr>`).join("") : `<tr><td colspan="6" class="muted">Bu gün uygun seçim bulunamadı.</td></tr>`;
  return `<div class="card coupon-card"><div class="row-between"><h3>${title}</h3><span>${couponSource(c)} <span class="badge ${cls}">${c.picks.length} maç</span></span></div><table><tr><th class="l">Maç</th><th>Lig</th><th>Saat</th><th>Seçim</th><th>Oran</th><th>Model</th></tr>${rows}</table><div class="coupon-total"><b>Toplam oran:</b> ${c.total_odds} · <b>Toplam tutma:</b> ${pct(c.total_probability)}<br><span class="muted">${esc(c.stake_note)}</span></div></div>`;
}

async function renderCoupons() {
  const el = $("#coupons"), req = ++state.couponReq;
  el.innerHTML = `<p class="muted">Kuponlar hesaplanıyor…</p>`;
  const d = await api(`/api/coupons?day=${state.couponDate}`);
  if (req !== state.couponReq) return; // daha yeni bir gün seçildi
  el.innerHTML = `<p class="muted">${fmtDay(d.date + "T12:00:00Z")} · tüm ligler · ${d.matches} maç</p>` + couponCard(d.banko, "Banko Kupon", "b-good") + couponCard(d.surprise, "Sürpriz Kupon", "b-warn");
}

async function renderTable() {
  const el = $("#table");
  el.innerHTML = `<p class="muted">Yükleniyor…</p>`;
  const rows = await api(`/api/standings?league=${state.league}`);
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

async function openMatch(id) {
  const m = await api(`/api/match/${id}`);
  const f = m.factors, k = m.markets;
  const th = f.table.home, ta = f.table.away;
  const pk = m.pick;
  const iddaaPick = pk ? m.iddaa_odds[pk.market] : null;
  const hero = pk
    ? `<div class="hero-label">Model önerisi</div>
       <div class="hero-pick"><span class="hero-market">${esc(pk.market)}</span> ${esc(marketText(pk.market, m))}</div>
       <div class="hero-stats">
         <div><div class="hero-num">${pct(pk.p)}</div><div class="muted">olasılık</div></div>
         <div><div class="hero-num">${pk.suggested}</div><div class="muted">önerilen oran</div></div>
         ${iddaaPick ? `<div><div class="hero-num ${iddaaPick >= pk.suggested ? "good" : ""}">${iddaaPick}</div><div class="muted">iddaa oranı</div></div>` : ""}
       </div>
       <div class="hero-foot">${confBadge(m.confidence_label, m.confidence_reason)}<span class="muted">${esc(m.confidence_reason)}</span>${iddaaPick ? `<span class="muted">${iddaaPick >= pk.suggested ? "iddaa oranı önerilen orandan yüksek, oynamaya değer." : "iddaa oranı önerilen orandan düşük."}</span>` : ""}</div>`
    : `<div class="hero-label">Model önerisi</div><div class="hero-pick">Bu maç için belirgin bir öneri yok</div><div class="hero-foot">${confBadge(m.confidence_label, m.confidence_reason)}<span class="muted">${esc(m.confidence_reason)}</span></div>`;

  const marketsRows = ["1", "X", "2", "1X", "X2", "Ü2.5", "A2.5", "KG Var", "KG Yok"].map((key) =>
    `<tr${pk && pk.market === key ? ' class="hl"' : ""}><td class="l"><b>${esc(key)}</b> <span class="muted">${esc(marketText(key, m))}</span></td><td>${pct(k[key].p)}</td><td>${k[key].suggested ?? "-"}</td><td>${m.iddaa_odds[key] ?? "-"}</td></tr>`).join("");
  const markets = `<table><tr><th class="l">Tahmin</th><th>Olasılık</th><th>Önerilen</th><th>iddaa</th></tr>${marketsRows}</table>
    <h4>En olası skorlar</h4><div class="scores">${m.scores.slice(0, 6).map((s) => `<span><b>${s.score}</b> ${pct(s.p)}</span>`).join("")}</div>`;

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
    ${f.h2h.length ? f.h2h.map((h) => `<div>${h.date} · ${esc(h.home)} <b>${h.score}</b> ${esc(h.away)}</div>`).join("") : `<span class="muted">Veri setinde yok</span>`}`;

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
}
function closeModal() { $("#modal").classList.add("hidden"); }
window.closeModal = closeModal;

async function render() {
  $("#leagueChips").classList.toggle("hidden", state.tab === "picks" || state.tab === "model");
  try {
    if (state.tab === "matches") await renderMatches();
    if (state.tab === "picks") await renderPicks();
    if (state.tab === "table") await renderTable();
    if (state.tab === "coupons") await renderCoupons();
    if (state.tab === "model") await renderModel();
  } catch (e) {
    $(`#tab-${state.tab}`).insertAdjacentHTML("afterbegin", `<div class="card" style="color:var(--bad)">Hata: ${esc(e.message)}</div>`);
  }
}

async function pollUpdate() {
  const s = await api("/api/update/status");
  const bar = $("#updateBar");
  $("#btnUpdate").disabled = s.running;
  if (s.running) {
    bar.classList.remove("hidden");
    bar.textContent = "Güncelleniyor: " + s.message;
    setTimeout(pollUpdate, 1500);
  } else {
    if (!bar.classList.contains("hidden")) {
      bar.textContent = s.error ? "Hata: " + s.error : "Güncelleme tamamlandı.";
      setTimeout(() => bar.classList.add("hidden"), 4000);
      await loadLeagues();
      render();
    }
  }
}

document.addEventListener("click", (e) => {
  const tab = e.target.closest(".tabs button");
  if (tab) {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b === tab));
    state.tab = tab.dataset.tab;
    document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("hidden", s.id !== "tab-" + state.tab));
    render();
  }
  const chip = e.target.closest(".chip");
  if (chip) {
    state.league = chip.dataset.league;
    localStorage.setItem("league", state.league);
    document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === chip));
    render();
  }
  const row = e.target.closest("[data-id]");
  if (row && !e.target.closest(".modal")) openMatch(row.dataset.id);
  if (e.target.id === "modal") closeModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
  if ((e.key === "Enter" || e.key === " ") && e.target.matches(".match[data-id]")) openMatch(e.target.dataset.id);
});
$("#btnUpdate").addEventListener("click", async () => { await api("/api/update", { method: "POST" }); $("#updateBar").classList.remove("hidden"); pollUpdate(); });
$("#btnBacktest").addEventListener("click", async () => { await api("/api/backtest", { method: "POST" }); renderModel(); });
$("#pickDays").addEventListener("change", renderPicks);
$("#pickConf").addEventListener("change", renderPicks);
$("#couponDate").value = state.couponDate;
function setCouponDay(day) { if (!day) return; state.couponDate = day; $("#couponDate").value = day; renderCoupons().catch((e) => { $("#coupons").innerHTML = `<div class="card" style="color:var(--bad)">Hata: ${esc(e.message)}</div>`; }); }
$("#couponDate").addEventListener("change", (e) => setCouponDay(e.target.value));
function shiftCouponDay(n) { const d = new Date(state.couponDate + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); setCouponDay(d.toISOString().slice(0, 10)); }
$("#couponPrev").addEventListener("click", () => shiftCouponDay(-1));
$("#couponNext").addEventListener("click", () => shiftCouponDay(1));

(async () => {
  await loadLeagues();
  render();
  pollUpdate();
})();
