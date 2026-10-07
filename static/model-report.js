// "Model Karnesi" sekmesi: /api/model-report (cron önbelleği). app.js yardımcıları: $, esc, api.
const mrPct = (v, d = 1) => (v == null ? "–" : (v * 100).toFixed(d) + "%");
const mrDiff = (v) => (v == null ? "–" : `<span class="${v >= 0 ? "ch-win" : "ch-loss"}">${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(1)} puan</span>`);

function mrCalibrationSvg(buckets) {
  const S = 260, P = 28, W = S - P - 8;
  const x = (v) => P + v * W, y = (v) => S - P - v * W;
  const pts = buckets.filter((b) => b.n > 0);
  const grid = [0, 0.2, 0.4, 0.6, 0.8, 1].map((t) => `<line x1="${x(0)}" y1="${y(t)}" x2="${x(1)}" y2="${y(t)}" stroke="var(--line)"/><text x="${P - 4}" y="${y(t) + 3}" text-anchor="end" font-size="9" fill="var(--muted)">${t * 100}</text><text x="${x(t)}" y="${S - P + 12}" text-anchor="middle" font-size="9" fill="var(--muted)">${t * 100}</text>`).join("");
  const line = pts.map((b) => `${x(b.predicted)},${y(b.actual)}`).join(" ");
  const dots = pts.map((b) => `<circle cx="${x(b.predicted)}" cy="${y(b.actual)}" r="${Math.min(7, 2 + Math.sqrt(b.n) / 12)}" fill="var(--accent)"><title>${mrPct(b.lo, 0)}–${mrPct(b.hi, 0)}: tahmin ${mrPct(b.predicted)}, gerçek ${mrPct(b.actual)} (${b.n})</title></circle>`).join("");
  return `<svg viewBox="0 0 ${S} ${S}" class="mr-chart" role="img" aria-label="Kalibrasyon grafiği">${grid}<line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" stroke="var(--muted)" stroke-dasharray="4 3"/><polyline points="${line}" fill="none" stroke="var(--accent)" stroke-width="1.5"/>${dots}<text x="${S / 2}" y="${S - 2}" text-anchor="middle" font-size="9" fill="var(--muted)">Tahmin edilen %</text><text x="8" y="${S / 2}" font-size="9" fill="var(--muted)" transform="rotate(-90 8 ${S / 2})" text-anchor="middle">Gerçekleşen %</text></svg>`;
}

function mrTrendSvg(days) {
  const W = 320, H = 120, P = 24;
  if (days.length < 2) return `<p class="muted">Son 30 günde yeterli maç yok.</p>`;
  const x = (i) => P + (i / (days.length - 1)) * (W - P - 8), y = (v) => H - 18 - v * (H - 30);
  const line = days.map((d, i) => `${x(i)},${y(d.accuracy)}`).join(" ");
  const grid = [0, 0.5, 1].map((t) => `<line x1="${P}" y1="${y(t)}" x2="${W - 8}" y2="${y(t)}" stroke="var(--line)"/><text x="${P - 4}" y="${y(t) + 3}" text-anchor="end" font-size="9" fill="var(--muted)">${t * 100}</text>`).join("");
  const dots = days.map((d, i) => `<circle cx="${x(i)}" cy="${y(d.accuracy)}" r="2.5" fill="var(--accent2)"><title>${d.day}: ${mrPct(d.accuracy)} (${d.n} maç)</title></circle>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" class="mr-chart" role="img" aria-label="Günlük isabet">${grid}<polyline points="${line}" fill="none" stroke="var(--accent2)" stroke-width="1.5"/>${dots}<text x="${P}" y="${H - 4}" font-size="9" fill="var(--muted)">${days[0].day.slice(5)}</text><text x="${W - 8}" y="${H - 4}" text-anchor="end" font-size="9" fill="var(--muted)">${days[days.length - 1].day.slice(5)}</text></svg>`;
}

function mrCouponRow(label, c) {
  if (!c) return "";
  return `<tr><td class="l">${label}</td><td>${c.won}/${c.won + c.lost}</td><td>${mrPct(c.hit_rate, 0)}</td><td>${c.roi == null ? "–" : `<span class="${c.roi >= 0 ? "ch-win" : "ch-loss"}">${(c.roi * 100).toFixed(1)}%</span>`}</td></tr>`;
}

async function renderModelReport() {
  const box = $("#modelReport");
  const r = await api("/api/model-report");
  if (!r.computed_at || !r.overall.n) { box.innerHTML = `<div class="card"><p class="muted">Karne henüz hazırlanmadı; veri güncellemesinden sonra burada görünecek.</p></div>`; return; }
  const o = r.overall, c = r.coupons;
  box.innerHTML = `
    <div class="mr-kpis">
      <div class="card"><div class="muted">1X2 isabet</div><div class="ch-big">${mrPct(o.accuracy)}</div><div class="muted">${o.n.toLocaleString("tr-TR")} maç · ev sahibi baz ${mrPct(o.home_baseline)} (${mrDiff(o.vs_home)})</div></div>
      <div class="card"><div class="muted">Brier / Log-loss</div><div class="ch-big">${o.brier.toFixed(3)}</div><div class="muted">log-loss ${o.logloss.toFixed(3)} · rastgele baz 0.667 / 1.099</div></div>
      <div class="card"><div class="muted">Rastgeleye göre</div><div class="ch-big">${mrDiff(o.vs_random)}</div><div class="muted">rastgele tahmin %33,3</div></div>
    </div>
    <div class="card"><h3>Lig bazında</h3><div class="mr-scroll"><table><tr><th class="l">Lig</th><th>Maç</th><th>İsabet</th><th>Brier</th><th>Log-loss</th><th>Ev baz.</th><th>Fark</th><th>Rastgele fark</th></tr>
      ${r.leagues.map((l) => `<tr><td class="l">${esc(l.name)}</td><td>${l.n}</td><td>${mrPct(l.accuracy)}</td><td>${l.brier.toFixed(3)}</td><td>${l.logloss.toFixed(3)}</td><td>${mrPct(l.home_baseline)}</td><td>${mrDiff(l.vs_home)}</td><td>${mrDiff(l.vs_random)}</td></tr>`).join("")}</table></div></div>
    <div class="grid2">
      <div class="card"><h3>Kalibrasyon</h3>${mrCalibrationSvg(r.calibration)}<p class="muted">Noktalar çapraza yakınsa olasılıklar güvenilir. %10'luk kovalar; nokta boyutu örnek sayısı.</p></div>
      <div class="card"><h3>Son 30 gün isabet</h3>${mrTrendSvg(r.trend)}<p class="muted">${r.trend.reduce((s, d) => s + d.n, 0)} maç</p></div>
    </div>
    ${c ? `<div class="card"><h3>Kupon geçmişi</h3><table><tr><th class="l">Kupon</th><th>Tutan</th><th>Tutma</th><th>ROI</th></tr>${mrCouponRow("Banko", c.banko)}${mrCouponRow("Sürpriz", c.surprise)}${mrCouponRow("Toplam", c.total)}</table></div>` : ""}
    <p class="muted">Walk-forward: her maç yalnız öncesindeki veriyle tahmin edildi (haber etkisi yok). Güncelleme: ${new Date(r.computed_at).toLocaleString("tr-TR")}</p>`;
}

document.addEventListener("click", (e) => {
  if (!e.target.closest('.tabs button[data-tab="report"]')) return;
  $("#leagueChips").classList.add("hidden");
  renderModelReport().catch((err) => { $("#modelReport").innerHTML = `<div class="card" style="color:var(--bad)">Hata: ${esc(err.message)}</div>`; });
});
