// Maç detayı ek içgörüler ("Detaylar" içinde): son maçlar, aralarındaki maçlar, gol istatistikleri, oran grafiği.
// app.js'ten önce yüklenir; $, esc, api, pct, fmtDateTime çağrı anında app.js'ten gelir.
const MI_RES = { G: "var(--good)", B: "var(--draw)", M: "var(--bad)" };

function miBar(label, value, max, color, raw = value) {
  const w = Math.max(2, Math.min(100, (raw / max) * 100));
  return `<div class="mi-bar"><span class="mi-bl">${label}</span><span class="mi-track"><i style="width:${w}%;background:${color}"></i></span><b>${value}</b></div>`;
}

function miForm(list) {
  if (!list.length) return `<span class="muted">veri yok</span>`;
  return list.map((g) => `<div class="mi-form"><span class="mi-res" style="background:${MI_RES[g.res]}">${g.res}</span>
    <span>${g.venue === "E" ? "Ev" : "Dep"} · ${esc(g.opp)}</span><b>${g.gf}-${g.ga}</b></div>`).join("");
}

function miGoals(s) {
  if (!s) return `<span class="muted">veri yok</span>`;
  const f = (v) => (v == null ? "-" : v);
  return `<div class="kv"><span>Attığı gol (evde / deplasmanda)</span><span class="h">${f(s.for_home)}</span><span class="a">${f(s.for_away)}</span>
    <span>Yediği gol (evde / deplasmanda)</span><span class="h">${f(s.against_home)}</span><span class="a">${f(s.against_away)}</span>
    <span>İki takım da gol attı</span><span></span><b>%${s.btts}</b><span>3+ gol olan maç</span><span></span><b>%${s.over25}</b>
    <span>Gol yemeden bitirdi</span><span></span><b>%${s.clean_sheet}</b></div><div class="muted" style="font-size:12px">${s.n} maç</div>`;
}

function miNews(list) {
  if (!list.length) return `<span class="muted">Son ${7} günde haber yok</span>`;
  return list.map((n) => `<div class="mi-news${n.injury ? " inj" : ""}">${n.injury ? `<span class="badge b-warn">Sakatlık/ceza</span> ` : ""}
    ${/^https?:\/\//i.test(n.link || "") ? `<a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a>` : esc(n.title)}</div>`).join("");
}

// Kütüphanesiz SVG çizgi grafiği; seri: [{at, odd}]
function miSpark(series, color) {
  const W = 120, H = 36, P = 3;
  if (series.length < 2) return `<span class="muted">değişmedi</span>`;
  const t = series.map((p) => new Date(p.at).getTime()), o = series.map((p) => p.odd);
  const t0 = t[0], dt = (t[t.length - 1] - t0) || 1, lo = Math.min(...o), hi = Math.max(...o), dv = (hi - lo) || 1;
  const pts = series.map((p, i) => `${(P + ((t[i] - t0) / dt) * (W - 2 * P)).toFixed(1)},${(H - P - ((o[i] - lo) / dv) * (H - 2 * P)).toFixed(1)}`).join(" ");
  return `<svg class="mi-spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Oran ${o[0].toFixed(2)} → ${o[o.length - 1].toFixed(2)}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/></svg>`;
}

function miOdds(markets) {
  const keys = MARKET_ORDER.filter((k) => markets[k] && markets[k].length > 1).slice(0, 6);
  if (!keys.length) return "";
  return `<h4>Oran hareketi</h4><div class="mi-sparks">${keys.map((k) => {
    const s = markets[k], a = s[0].odd, b = s[s.length - 1].odd;
    return `<div class="mi-sp"><b>${esc(k)}</b>${miSpark(s, b < a ? "var(--good)" : "var(--bad)")}<span class="muted">${a.toFixed(2)} → ${b.toFixed(2)}</span></div>`;
  }).join("")}</div>`;
}

async function renderMatchInsights(m) {
  const el = $("#matchInsights");
  if (!el) return;
  const req = state.matchReq;
  let d;
  try { d = await api(`/api/match/${encodeURIComponent(m.id)}/insights`); } catch (e) { return; }
  if (req !== state.matchReq || !$("#matchInsights")) return;
  el.innerHTML = `
    <h4>Son 5 maç</h4>
    <div class="grid2"><div><b style="color:var(--home)">${esc(m.home)}</b>${miForm(d.form.home)}</div><div><b style="color:var(--away)">${esc(m.away)}</b>${miForm(d.form.away)}</div></div>
    <h4>Aralarındaki son maçlar</h4>${d.h2h.length ? d.h2h.map((h) => `<div>${h.date} · ${esc(h.home)} <b>${h.score}</b> ${esc(h.away)}</div>`).join("") : `<span class="muted">veri yok</span>`}
    <h4>Gol istatistikleri</h4>
    <div class="grid2"><div><b style="color:var(--home)">${esc(m.home)}</b>${miGoals(d.goals.home)}</div><div><b style="color:var(--away)">${esc(m.away)}</b>${miGoals(d.goals.away)}</div></div>`;
}

// Oyuncu gol atar: olasılık + adil oran; az veri işaretli.
async function renderMatchPlayers(m) {
  const el = $("#matchPlayers");
  if (!el) return;
  const req = state.matchReq;
  let d;
  try { d = await api(`/api/match/${encodeURIComponent(m.id)}/players`); } catch (e) { return; }
  if (req !== state.matchReq || !$("#matchPlayers")) return;
  const side = (name, color, s) => `<b style="color:${color}">${esc(name)}</b>` + (!s.available || !s.players.length
    ? `<div class="muted">Yeterli oyuncu verisi yok</div>`
    : `<table><tr><th class="l">Oyuncu</th><th>Olasılık</th><th>Adil oran</th></tr>${s.players.map((p) =>
      `<tr><td class="l">${esc(p.name)} <span class="muted">${esc(p.position || "")}</span>${p.low_data ? ` <span class="badge b-warn" title="${p.apps} maç, ${p.minutes} dk">Az veri</span>` : ""}</td><td>${pct(p.p)}</td><td>${p.fair}</td></tr>`).join("")}</table>`);
  el.innerHTML = `<div class="card"><h3>Oyuncu gol atar</h3><div class="grid2"><div>${side(m.home, "var(--home)", d.home)}</div><div>${side(m.away, "var(--away)", d.away)}</div></div><div class="muted" style="font-size:12px">${esc(d.note || "")}</div></div>`;
}
