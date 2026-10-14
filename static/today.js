// Ana sayfa "Bugün" özeti: günün en güçlü önerileri, banko kupon, canlı maçlar, favoriler.
window.Today = (() => {
  let req = 0;
  const topLi = (p) => {
    const s = Simple.info(p);
    return `<li class="clickable" data-id="${esc(p.id)}" role="button" tabindex="0"><span>${esc(p.home)} – ${esc(p.away)}</span><span class="badge b-info">${esc(s.headline)}</span><b class="iddaa-odd">${s.odds == null ? "–" : Number(s.odds).toFixed(2)}</b></li>`;
  };
  async function render() {
    const el = $("#today"), my = ++req;
    if (state.league.startsWith("small:")) { el.innerHTML = ""; return; }
    el.innerHTML = `<section class="today" aria-label="Bugün özeti"><h2 class="sec-title">Bugün</h2>${Ui.skeleton(1)}</section>`;
    const day = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
    const [c, p] = await Promise.all([
      api(`/api/coupons?day=${day}`).catch(() => null),
      api("/api/picks?category=main&days=2&min_conf=0.7").catch(() => null),
    ]);
    if (my !== req) return;
    const picks = c?.banko?.picks || [];
    const live = [...state.live.values()].filter((m) => m.state === "in").slice(0, 4);
    const top = (p || []).slice(0, 3);
    const upd = state.lastUpdate ? `Son güncelleme: ${esc(fmtAgo(state.lastUpdate))}` : "";
    el.innerHTML = `<section class="today" aria-label="Bugün özeti">
      <div class="row-between"><h2 class="sec-title">Bugün</h2><span class="muted small">${upd}</span></div>
      <div class="today-grid">
        <div class="card"><h3>En güçlü öneriler</h3>${top.length ? `<ul class="mini">${top.map(topLi).join("")}</ul>` : Ui.empty("Güçlü öneri yok", "Önümüzdeki günlerde yüksek güvenli maç bulunamadı.")}</div>
        <div class="card"><h3>Günün banko kuponu</h3>${picks.length ? `<ul class="mini">${picks.map((x) => `<li><span>${esc(x.home)} – ${esc(x.away)}</span><span class="badge b-info">${esc(Simple.headline(x.market))}</span><b class="iddaa-odd">${Number(x.odds).toFixed(2)}</b></li>`).join("")}</ul><div class="row-between"><span class="muted">Toplam oran</span><b class="iddaa-odd">${c.banko.total_odds}</b></div>` : Ui.empty("Banko kupon yok", "Bugün şartlara uyan seçim bulunamadı.")}</div>
        <div class="card" id="favToday"></div>
        <div class="card"><h3>Canlı maçlar</h3>${live.length ? `<ul class="mini">${live.map((m) => `<li><span>${esc(m.home)} – ${esc(m.away)}</span>${liveBadge(m)}</li>`).join("")}</ul>` : Ui.empty("Şu an canlı maç yok")}</div>
      </div></section>`;
    window.Extras?.renderFavToday();
  }
  return { render };
})();
