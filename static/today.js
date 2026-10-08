// Ana sayfa "Bugün" özeti: banko kupon, en değerli 3 oran, canlı maçlar, son güncelleme.
window.Today = (() => {
  let req = 0;
  async function render() {
    const el = $("#today"), my = ++req;
    if (state.league.startsWith("small:")) { el.innerHTML = ""; return; }
    el.innerHTML = `<section class="today" aria-label="Bugün özeti"><h2 class="sec-title">Bugün</h2>${Ui.skeleton(1)}</section>`;
    const day = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
    const [c, v] = await Promise.all([
      api(`/api/coupons?day=${day}`).catch(() => null),
      api("/api/value-bets?days=3&min_prob=0.3&min_ev=0.05").catch(() => null),
    ]);
    if (my !== req) return;
    const picks = c?.banko?.picks || [];
    const live = [...state.live.values()].filter((m) => m.state === "in").slice(0, 4);
    const top = (v?.items || []).slice(0, 3);
    const upd = state.lastUpdate ? `Son güncelleme: ${esc(fmtAgo(state.lastUpdate))}` : "";
    el.innerHTML = `<section class="today" aria-label="Bugün özeti">
      <div class="row-between"><h2 class="sec-title">Bugün</h2><span class="muted small">${upd}</span></div>
      <div class="today-grid">
        <div class="card"><h3>Günün banko kuponu</h3>${picks.length ? `<ul class="mini">${picks.map((p) => `<li><span>${esc(p.home)} – ${esc(p.away)}</span><span class="badge b-info">${esc(p.market)}</span><b class="iddaa-odd">${Number(p.odds).toFixed(2)}</b></li>`).join("")}</ul><div class="row-between"><span class="muted">Toplam oran</span><b class="iddaa-odd">${c.banko.total_odds}</b></div>` : Ui.empty("Banko kupon yok", "Bugün şartlara uyan seçim bulunamadı.")}</div>
        <div class="card"><h3>En değerli 3 oran</h3>${top.length ? `<ul class="mini">${top.map((x) => `<li class="clickable" data-id="${esc(x.id)}"><span>${esc(x.home)} – ${esc(x.away)}</span><span class="badge b-info">${esc(x.selection)}</span><b class="iddaa-odd">${x.iddaa_odds.toFixed(2)}</b><b class="ev-pos">+${(x.ev * 100).toFixed(0)}%</b></li>`).join("")}</ul>` : Ui.empty("Değerli oran yok")}</div>
        <div class="card"><h3>Canlı maçlar</h3>${live.length ? `<ul class="mini">${live.map((m) => `<li><span>${esc(m.home)} – ${esc(m.away)}</span>${liveBadge(m)}</li>`).join("")}</ul>` : Ui.empty("Şu an canlı maç yok")}</div>
      </div></section>`;
  }
  return { render };
})();
