// Maç detayı ek içgörüler: form, H2H, gol istatistikleri, λ ve skor çubukları, 7 günlük haberler, oran mini grafiği.
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
  return `<div class="kv"><span>Attığı (ev / dep)</span><span class="h">${f(s.for_home)}</span><span class="a">${f(s.for_away)}</span>
    <span>Yediği (ev / dep)</span><span class="h">${f(s.against_home)}</span><span class="a">${f(s.against_away)}</span>
    <span>KG Var</span><span></span><b>%${s.btts}</b><span>Ü2.5</span><span></span><b>%${s.over25}</b>
    <span>Gol yemeden</span><span></span><b>%${s.clean_sheet}</b></div><div class="muted" style="font-size:12px">${s.n} maç</div>`;
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
  return `<div class="card"><h3>Oran hareketi grafiği</h3><div class="mi-sparks">${keys.map((k) => {
    const s = markets[k], a = s[0].odd, b = s[s.length - 1].odd;
    return `<div class="mi-sp"><b>${esc(k)}</b>${miSpark(s, b < a ? "var(--good)" : "var(--bad)")}<span class="muted">${a.toFixed(2)} → ${b.toFixed(2)}</span></div>`;
  }).join("")}</div></div>`;
}

async function renderMatchInsights(m) {
  const el = $("#matchInsights");
  if (!el) return;
  const req = state.matchReq;
  let d;
  try { d = await api(`/api/match/${encodeURIComponent(m.id)}/insights`); } catch (e) { return; }
  if (req !== state.matchReq || !$("#matchInsights")) return;
  const maxL = Math.max(m.lambda_home, m.lambda_away, 1.5);
  el.innerHTML = `
    <div class="card"><h3>Beklenen goller (λ) ve en olası skorlar</h3>
      ${miBar(esc(m.home), m.lambda_home.toFixed(2), maxL, "var(--home)")}${miBar(esc(m.away), m.lambda_away.toFixed(2), maxL, "var(--away)")}
      <h4>En olası 5 skor</h4>
      ${(m.scores || []).slice(0, 5).map((s) => miBar(s.score, (s.p * 100).toFixed(1) + "%", m.scores[0].p, "var(--accent2)", s.p)).join("")}
    </div>
    <div class="grid2">
      <div class="card"><h3>Son 5 maç</h3><b style="color:var(--home)">${esc(m.home)}</b>${miForm(d.form.home)}<b style="color:var(--away)">${esc(m.away)}</b>${miForm(d.form.away)}
        <h4>Son 5 karşılaşma</h4>${d.h2h.length ? d.h2h.map((h) => `<div>${h.date} · ${esc(h.home)} <b>${h.score}</b> ${esc(h.away)}</div>`).join("") : `<span class="muted">veri yok</span>`}</div>
      <div class="card"><h3>Gol istatistikleri</h3><b style="color:var(--home)">${esc(m.home)}</b>${miGoals(d.goals.home)}<b style="color:var(--away)">${esc(m.away)}</b>${miGoals(d.goals.away)}</div>
    </div>
    <div class="grid2">
      <div class="card"><h3>${esc(m.home)} · son 7 gün</h3>${miNews(d.news.home)}</div>
      <div class="card"><h3>${esc(m.away)} · son 7 gün</h3>${miNews(d.news.away)}</div>
    </div>${miOdds(d.odds)}`;
}
