// Sade gösterim yardımcıları: tek ana öneri, düz Türkçe etiket, 3 seviyeli güven rozeti.
// Sunucu `summary` alanını (app/explain.py) üretir; yoksa (küçük ligler, eski önbellek) buradan türetilir.
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Simple = api;
})(globalThis, function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const LEVELS = { "Yüksek": 3, "Orta": 2, "Düşük": 1 };

  function headline(market) {
    if (["1", "X", "2", "1X", "X2", "12"].includes(market)) return "MS " + market;
    const m = /^([ÜA])(\d+(?:\.\d+)?)$/.exec(market || "");
    if (m) return `${m[2]} ${m[1] === "Ü" ? "Üst" : "Alt"}`;
    return market || "";
  }

  function title(market) {
    const fixed = {
      "1": "Ev sahibi kazanır", "X": "Beraberlik", "2": "Deplasman kazanır",
      "1X": "Ev sahibi kaybetmez", "X2": "Deplasman kaybetmez", "12": "Beraberlik olmaz",
      "KG Var": "İki takım da gol atar", "KG Yok": "En az bir takım gol atamaz",
      "Ev 0.5Ü": "Ev sahibi gol atar", "Dep 0.5Ü": "Deplasman gol atar",
    };
    if (fixed[market]) return fixed[market];
    const m = /^([ÜA])(\d+(?:\.\d+)?)$/.exec(market || "");
    if (m) return m[1] === "Ü" ? `${Math.floor(Number(m[2])) + 1} veya daha fazla gol` : `En fazla ${Math.floor(Number(m[2]))} gol`;
    return market || "";
  }

  /** Bir maç/öneri nesnesinden gösterilecek tek öneri. */
  function info(m) {
    if (m.summary) return m.summary;
    const pick = m.pick;
    if (!pick) return { market: null, headline: "Net öneri yok", title: "Bu maçta güçlü bir seçenek göremedik", odds: null, level: 0, level_label: "", reason: "" };
    const small = !!m.small_league;
    return {
      market: pick.market, headline: headline(pick.market), title: title(pick.market),
      odds: pick.odds ?? m.iddaa_odds?.[pick.market] ?? null,
      level: small ? 0 : LEVELS[m.confidence_label] || 1, level_label: small ? "" : m.confidence_label || "",
      reason: small ? "Bu lig için ayrıntılı takım verisi yok; öneri iddaa oranlarındaki favoriye dayanır." : "",
    };
  }

  function levelBadge(level, label) {
    if (!level) return `<span class="conf conf-0">Sınırlı veri</span>`;
    const text = { 3: "Yüksek güven", 2: "Orta güven", 1: "Düşük güven" }[level];
    return `<span class="conf conf-${level}" aria-label="${esc(label || text)}"><span class="conf-bars" aria-hidden="true"><i></i><i></i><i></i></span>${text}</span>`;
  }

  function oddsBox(odds) {
    return `<div class="pick-odds"><small>iddaa oranı</small><b>${odds == null ? "–" : Number(odds).toFixed(2)}</b></div>`;
  }

  /** Büyük öneri bloğu: [MS 2] Deplasman kazanır · güven · oran. */
  function pickBlock(m) {
    const s = info(m);
    return `<div class="pick-main">
      <span class="pick-chip${s.market ? "" : " none"}">${esc(s.headline)}</span>
      <div class="pick-text"><b>${esc(s.title)}</b>${s.market ? levelBadge(s.level, s.level_label) : ""}</div>
      ${s.market ? oddsBox(s.odds) : ""}
    </div>${s.reason ? `<p class="pick-why">${esc(s.reason)}</p>` : ""}`;
  }

  return { headline, title, info, levelBadge, oddsBox, pickBlock };
});
