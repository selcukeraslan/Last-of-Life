/* Kupon oluşturucu hesapları: DOM'a ve ağa dokunmayan saf fonksiyonlar (tests/js/slip_calc.test.js).
 * Oran önceliği backend kuponlarıyla aynıdır: iddaa oranı varsa o, yoksa Claude oranı. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SlipCalc = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const MIN_ODDS = 1.01;
  const MAX_ITEMS = 30;
  const DEFAULT_STAKE = 100;

  const GROUPS = [
    { label: "1X2", markets: ["1", "X", "2"] },
    { label: "Çifte şans", markets: ["1X", "12", "X2"] },
    { label: "Alt/Üst", markets: ["Ü1.5", "A1.5", "Ü2.5", "A2.5", "Ü3.5", "A3.5"] },
    { label: "KG", markets: ["KG Var", "KG Yok"] },
  ];
  const MARKETS = GROUPS.flatMap((g) => g.markets);

  // Her pazarın (ev, deplasman) gol sayılarına göre tutup tutmadığı; çelişki kontrolü için.
  const RULES = {
    "1": (h, a) => h > a, "X": (h, a) => h === a, "2": (h, a) => h < a,
    "1X": (h, a) => h >= a, "12": (h, a) => h !== a, "X2": (h, a) => h <= a,
    "KG Var": (h, a) => h > 0 && a > 0, "KG Yok": (h, a) => h === 0 || a === 0,
  };
  for (const line of [1.5, 2.5, 3.5]) {
    RULES["Ü" + line] = (h, a) => h + a > line;
    RULES["A" + line] = (h, a) => h + a < line;
  }
  const MAX_GOALS = 5; // en yüksek çizgi 3.5; 0..5 gol her kombinasyonu denemeye yeter

  const round2 = (x) => Math.round(x * 100) / 100;
  const num = (x) => (typeof x === "number" && Number.isFinite(x) ? x : null);
  const keyOf = (sel) => sel.id + "|" + sel.market;

  /** iddaa oranı varsa o, yoksa Claude oranı; ikisi de yoksa null. */
  function effectiveOdds(sel) {
    const iddaa = num(sel.iddaaOdds), claude = num(sel.claudeOdds);
    if (iddaa !== null && iddaa >= MIN_ODDS) return { odds: round2(iddaa), source: "iddaa" };
    if (claude !== null && claude >= MIN_ODDS) return { odds: round2(claude), source: "claude" };
    return null;
  }

  function isValid(sel) {
    return !!sel && typeof sel === "object" && typeof sel.id === "string" && sel.id !== ""
      && MARKETS.includes(sel.market) && typeof sel.home === "string" && typeof sel.away === "string"
      && Number.isFinite(Date.parse(sel.kickoff)) && num(sel.p) !== null && sel.p > 0 && sel.p <= 1
      && effectiveOdds(sel) !== null;
  }

  /** /api/match ya da /api/upcoming yanıtındaki bir maç + pazardan kupon seçimi; olmuyorsa null. */
  function fromMatch(m, market, leagueName) {
    const mk = m && m.markets && m.markets[market];
    if (!mk || !MARKETS.includes(market)) return null;
    const sel = {
      id: String(m.id), market, leagueName: m.league_name || leagueName || "",
      home: m.home, away: m.away, kickoff: m.kickoff, p: num(mk.p),
      iddaaOdds: num((m.iddaa_odds || {})[market]), claudeOdds: num(mk.suggested),
    };
    return isValid(sel) ? sel : null;
  }

  /** Saklı seçimi taze maç verisiyle günceller (olasılık + oranlar); veri uymuyorsa eskisini korur. */
  function refreshSelection(sel, m) {
    return fromMatch(m, sel.market, sel.leagueName) || sel;
  }

  /** localStorage'dan okunan ham veriyi güvenli forma çevirir. */
  function sanitize(raw) {
    const out = { items: [], stake: DEFAULT_STAKE };
    if (!raw || typeof raw !== "object") return out;
    const seen = new Set();
    for (const sel of Array.isArray(raw.items) ? raw.items : []) {
      if (!isValid(sel) || seen.has(keyOf(sel)) || out.items.length >= MAX_ITEMS) continue;
      seen.add(keyOf(sel));
      out.items.push({
        id: sel.id, market: sel.market, leagueName: typeof sel.leagueName === "string" ? sel.leagueName : "",
        home: sel.home, away: sel.away, kickoff: sel.kickoff, p: sel.p,
        iddaaOdds: num(sel.iddaaOdds), claudeOdds: num(sel.claudeOdds),
      });
    }
    if ("stake" in raw) out.stake = raw.stake === null ? null : (num(raw.stake) !== null && raw.stake >= 0 ? raw.stake : DEFAULT_STAKE);
    return out;
  }

  /** "12,5" / "12.5" -> 12.5; boş ya da geçersiz/negatifse null. */
  function parseStake(text) {
    const s = String(text ?? "").trim().replace(",", ".");
    if (s === "") return null;
    const n = Number(s);
    return Number.isFinite(n) && n >= 0 ? n : null;
  }

  function addSelection(items, sel) {
    if (!isValid(sel)) return { items, status: "invalid" };
    if (items.some((i) => keyOf(i) === keyOf(sel))) return { items, status: "exists" };
    if (items.length >= MAX_ITEMS) return { items, status: "full" };
    return { items: [...items, sel], status: "added" };
  }
  const removeSelection = (items, key) => items.filter((i) => keyOf(i) !== key);
  const hasSelection = (items, id, market) => items.some((i) => i.id === String(id) && i.market === market);

  /** Aynı maçtaki pazarlar hiçbir skorda birlikte tutamıyorsa (örn. 1 ve X, Ü2.5 ve A1.5) true. */
  function conflicts(markets) {
    for (let h = 0; h <= MAX_GOALS; h++)
      for (let a = 0; a <= MAX_GOALS; a++)
        if (markets.every((mk) => RULES[mk](h, a))) return false;
    return true;
  }

  /** Kuponun tüm sayıları. `now` = ms (başlamış maç tespiti), `stake` = TL (null olabilir). */
  function summarize(items, stake, now) {
    const rows = items.map((sel) => {
      const o = effectiveOdds(sel);
      return { ...sel, key: keyOf(sel), odds: o ? o.odds : null, source: o ? o.source : null,
               started: Date.parse(sel.kickoff) <= now };
    });

    const byMatch = new Map();
    for (const r of rows) byMatch.set(r.id, [...(byMatch.get(r.id) || []), r]);
    const sameMatch = [...byMatch.values()].filter((g) => g.length > 1).map((g) => ({
      id: g[0].id, home: g[0].home, away: g[0].away, markets: g.map((r) => r.market),
      impossible: conflicts(g.map((r) => r.market)),
    }));

    const count = rows.length;
    const impossible = sameMatch.some((g) => g.impossible);
    const naiveProbability = count ? rows.reduce((acc, r) => acc * r.p, 1) : 0;
    const totalOdds = count ? round2(rows.reduce((acc, r) => acc * (r.odds ?? 1), 1)) : 0;
    const totalProbability = impossible ? 0 : naiveProbability;
    const ev = count ? totalProbability * totalOdds - 1 : null;
    const iddaaCount = rows.filter((r) => r.source === "iddaa").length;

    const money = stake !== null && stake !== undefined && Number.isFinite(stake) && stake >= 0 && count > 0;
    return {
      rows, count, sameMatch, impossible, iddaaCount,
      claudeCount: rows.filter((r) => r.source === "claude").length,
      startedCount: rows.filter((r) => r.started).length,
      source: !count ? null : iddaaCount === count ? "iddaa" : iddaaCount === 0 ? "claude" : "karışık",
      totalOdds, totalProbability, naiveProbability, ev,
      stake: money ? stake : null,
      payout: money ? round2(stake * totalOdds) : null,
      profit: money ? round2(stake * totalOdds - stake) : null,
      expectedValue: money ? round2(stake * ev) : null, // yatırılan tutarın beklenen net getirisi (TL)
    };
  }

  return {
    MIN_ODDS, MAX_ITEMS, DEFAULT_STAKE, GROUPS, MARKETS,
    keyOf, effectiveOdds, isValid, fromMatch, refreshSelection, sanitize, parseStake,
    addSelection, removeSelection, hasSelection, conflicts, summarize,
  };
});
