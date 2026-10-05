const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (p) => (p * 100).toFixed(0) + "%";
const api = async (url, opts) => {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.text()) || r.status);
  return r.json();
};

const state = { league: localStorage.getItem("league") || "tur.1", tab: "matches", leagues: [], model: {} };

function fmtTime(iso) { return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }); }
function fmtDay(iso) { return new Date(iso).toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" }); }
function fmtDateTime(iso) { return new Date(iso).toLocaleString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
function confBadge(label) { return `<span class="badge ${label === "Yüksek" ? "b-good" : label === "Orta" ? "b-warn" : "b-bad"}">${label} güven</span>`; }
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
        <div style="margin-top:4px">${confBadge(m.confidence_label)}</div>
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
      <td>${pct(p.pick.p)}</td><td>${oddsValue(p.iddaa_odds[p.pick.market], p.pick.suggested)}</td><td>${confBadge(p.confidence_label)}</td></tr>`).join("")}
  </table><p class="muted">Kombine kuponda olasılıklar çarpılır: 3 maçlık %70'lik kupon ≈ %34 tutar.</p></div>`;
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

function evLine(p, odd) {
  if (!odd || odd <= 1) return "";
  const ev = p * odd - 1;
  const kelly = Math.max(0, (p * odd - 1) / (odd - 1));
  return ev > 0
    ? `<div class="ev" style="color:var(--good)">Değerli: +%${(ev * 100).toFixed(1)} beklenti · Kelly %${(kelly * 25).toFixed(1)} (¼)</div>`
    : `<div class="ev" style="color:var(--bad)">Değersiz: %${(ev * 100).toFixed(1)} beklenti</div>`;
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

async function openMatch(id) {
  const m = await api(`/api/match/${id}`);
  const f = m.factors, k = m.markets;
  const th = f.table.home, ta = f.table.away;
  const order = ["1", "X", "2", "1X", "12", "X2", "Ü1.5", "A1.5", "Ü2.5", "A2.5", "Ü3.5", "A3.5", "KG Var", "KG Yok", "Ev 0.5Ü", "Dep 0.5Ü"];
  $("#modalBody").innerHTML = `
    <button class="close" onclick="closeModal()">×</button>
    <div class="muted" style="text-align:center">${esc(m.league_name)} · ${fmtDay(m.kickoff)} ${fmtTime(m.kickoff)}</div>
    <div class="mhead">
      <div class="team">${img(m.home_logo)}<h3>${esc(m.home)}</h3><div class="muted">${th ? th.pos + ". sıra · " + th.pts + " puan" : ""}</div></div>
      <div><div class="vs">${m.lambda_home.toFixed(2)} : ${m.lambda_away.toFixed(2)}</div><div class="muted">beklenen gol</div></div>
      <div class="team">${img(m.away_logo)}<h3>${esc(m.away)}</h3><div class="muted">${ta ? ta.pos + ". sıra · " + ta.pts + " puan" : ""}</div></div>
    </div>
    <div class="card row-between">
      <div>${m.pick ? `Model önerisi: <span class="badge b-info">${esc(m.pick.market)}</span> olasılık <b>${pct(m.pick.p)}</b>, önerilen oran <b>${m.pick.suggested}</b>` : "Belirgin öneri yok"}</div>
      <div>${confBadge(m.confidence_label)}</div>
    </div>
    <div class="card">
      <h3>Pazarlar ve oranlar</h3>
      <p class="muted">İddaa oranı bulunan pazarlar otomatik doldurulur; değeri değiştirerek farklı bir oranı da hesaplayabilirsiniz.</p>
      <div class="mk-grid">${order.map((key) => `<div class="mk"><div class="k">${esc(key)}</div>
        <div class="p">${pct(k[key].p)} · adil ${k[key].fair ?? "-"}</div>
        <div class="market-odds">${oddsValue(m.iddaa_odds[key], k[key].suggested)}</div>
        <input type="number" step="0.01" min="1" placeholder="bahis oranı" data-p="${k[key].p}" value="${m.iddaa_odds[key] ?? ""}">
        <div class="evout"></div></div>`).join("")}</div>
      <h4>En olası skorlar</h4>
      <div class="mk-grid">${m.scores.map((s) => `<div class="mk"><div class="k">${s.score}</div><div class="p">${pct(s.p)} · oran ${s.suggested}</div></div>`).join("")}</div>
    </div>
    <div class="grid2">
      <div class="card"><h3>Güç parametreleri</h3>
        <div class="kv">
          <span></span><b class="h">Ev</b><b class="a">Dep</b>
          <span>Elo</span><span class="h">${f.elo.home}</span><span class="a">${f.elo.away}</span>
          <span>Hücum (ev/dep özel)</span><span class="h">${f.poisson.att_home}</span><span class="a">${f.poisson.att_away}</span>
          <span>Savunma (düşük iyi)</span><span class="h">${f.poisson.def_home}</span><span class="a">${f.poisson.def_away}</span>
          <span>Poisson xG</span><span class="h">${f.poisson.home}</span><span class="a">${f.poisson.away}</span>
          <span>Elo xG</span><span class="h">${f.elo.lambda_home}</span><span class="a">${f.elo.lambda_away}</span>
          <span>Form (maç başı puan)</span><span class="h">${f.form.home_ppg}</span><span class="a">${f.form.away_ppg}</span>
          <span>Haber skoru</span><span class="h">${f.news.home.score}</span><span class="a">${f.news.away.score}</span>
          <span>Sakatlık/ceza haberi</span><span class="h">${f.news.home.injuries}</span><span class="a">${f.news.away.injuries}</span>
          <span>Dinlenme (gün)</span><span class="h">${f.rest.home_days ?? "-"}</span><span class="a">${f.rest.away_days ?? "-"}</span>
          <span>Evde / deplasmanda P/M</span><span class="h">${th && th.hp ? (th.hpts / th.hp).toFixed(2) : "-"}</span><span class="a">${ta && ta.ap ? (ta.apts / ta.ap).toFixed(2) : "-"}</span>
        </div>
        <p class="muted" style="font-size:12px">Lig ortalaması: ev ${f.poisson.league_home_avg}, dep ${f.poisson.league_away_avg} gol. Elo ev avantajı dahil fark: ${f.elo.diff_with_home_adv}. Form etkisi ${f.form.log_adj}, haber etkisi ${f.news.log_adj} (log-xG).</p>
      </div>
      <div class="card"><h3>Son maçlar</h3>
        <div class="grid2"><div><b class="h" style="color:var(--home)">${esc(m.home)}</b>${formList(f.form.home)}</div>
        <div><b style="color:var(--away)">${esc(m.away)}</b>${formList(f.form.away)}</div></div>
        <h4>Aralarındaki son maçlar</h4>
        ${f.h2h.length ? f.h2h.map((h) => `<div>${h.date} · ${esc(h.home)} <b>${h.score}</b> ${esc(h.away)}</div>`).join("") : `<span class="muted">Veri setinde yok</span>`}
      </div>
    </div>
    <div class="grid2">
      <div class="card"><h3>${esc(m.home)} haberleri</h3>${newsList(f.news.home)}</div>
      <div class="card"><h3>${esc(m.away)} haberleri</h3>${newsList(f.news.away)}</div>
    </div>`;
  $("#modalBody").querySelectorAll(".mk input").forEach((inp) => {
    const updateEv = () => { inp.nextElementSibling.innerHTML = evLine(parseFloat(inp.dataset.p), parseFloat(inp.value)); };
    inp.addEventListener("input", updateEv);
    updateEv();
  });
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

(async () => {
  await loadLeagues();
  render();
  pollUpdate();
})();
