// Oran hareketi: hücre göstergesi (2.10 → 1.85 ↓), maç detayında oran geçmişi, "Oran düşüşü" listesi.
// app.js'ten önce yüklenir; $, esc, api, state, fmtDateTime vb. çağrı anında app.js'ten gelir.
const oddFmt = (n) => Number(n).toFixed(2);
const ODD_ARROW = { down: "↓", up: "↑", flat: "" };
const MARKET_ORDER = ["1", "X", "2", "1X", "12", "X2", "Ü1.5", "A1.5", "Ü2.5", "A2.5", "Ü3.5", "A3.5", "KG Var", "KG Yok"];

function moveText(mv) {
  return `${oddFmt(mv.open)} → ${oddFmt(mv.current)} ${ODD_ARROW[mv.direction]}`;
}

// item.iddaa_movement: {pazar: {open, current, change_pct, direction, opened_at}} (yalnız değişenler)
function oddsMove(item, market) {
  const mv = item && item.iddaa_movement && item.iddaa_movement[market];
  if (!mv) return "";
  const sign = mv.change_pct > 0 ? "+" : "";
  return `<span class="odd-move ${mv.direction}" title="Açılış ${oddFmt(mv.open)} (${fmtDateTime(mv.opened_at)}) · ${sign}%${mv.change_pct}">${moveText(mv)}</span>`;
}

async function renderOddsHistory(m) {
  const el = $("#oddsHistory");
  if (!el) return;
  let h;
  try { h = await api(`/api/odds/history/${m.id}`); } catch (e) { return; } // iddaa oranı/geçmişi yok
  const keys = MARKET_ORDER.filter((k) => h.markets[k]);
  if (!keys.length || !$("#oddsHistory")) return;
  const rows = keys.map((k) => {
    const s = h.markets[k], first = s[0], last = s[s.length - 1];
    const mv = oddsMove(m, k);
    const pctChange = first.odd ? ((last.odd - first.odd) / first.odd) * 100 : 0;
    const shown = s.length > 8 ? [s[0], ...s.slice(-7)] : s;
    const line = shown.map((p) => `<span title="${esc(fmtDateTime(p.at))}">${oddFmt(p.odd)}</span>`).join(" → ");
    return `<tr><td class="l"><b>${esc(k)}</b></td><td>${oddFmt(first.odd)}</td><td>${oddFmt(last.odd)}</td>
      <td>${s.length > 1 ? `${mv}<span class="muted"> ${pctChange > 0 ? "+" : ""}${pctChange.toFixed(1)}%</span>` : `<span class="muted">değişmedi</span>`}</td>
      <td class="l oh-line">${s.length > shown.length ? "… → " : ""}${line}</td></tr>`;
  }).join("");
  const since = Math.min(...keys.map((k) => new Date(h.markets[k][0].at).getTime()));
  el.innerHTML = `<div class="card"><h3>Oran hareketi</h3>
    <p class="muted">Açılış, iddaa.com oranının ilk kaydedildiği değerdir (${fmtDateTime(new Date(since).toISOString())}); yalnız değişimler saklanır.</p>
    <table class="oh-table"><tr><th class="l">Pazar</th><th>Açılış</th><th>Güncel</th><th>Değişim</th><th class="l">Geçmiş</th></tr>${rows}</table></div>`;
}

async function renderOddsDrops() {
  const el = $("#oddsDrops"), req = (state.dropsReq = (state.dropsReq || 0) + 1);
  if (!el) return;
  if (String(state.league).startsWith("small:")) { el.innerHTML = ""; return; }  // küçük liglerde düşüş endpoint'i yok
  let d;
  try { d = await api(`/api/odds/drops?league=${state.league}&limit=8`); } catch (e) { el.innerHTML = ""; return; }
  if (req !== state.dropsReq) return; // lig değişti, daha yeni istek var
  if (!d.matches.length) { el.innerHTML = ""; return; }
  el.innerHTML = `<div class="card drops"><div class="row-between"><h3>Oran düşüşü</h3><span class="muted">açılışa göre %${d.min_pct}+ düşenler</span></div>
    ${d.matches.map((m) => `<div class="drop-row ${m.match_id ? "clickable" : ""}" ${m.match_id ? `data-id="${esc(m.match_id)}" role="button" tabindex="0"` : ""}>
      <span class="drop-teams"><b>${esc(m.home)}</b> – ${esc(m.away)} <span class="muted">${fmtDateTime(m.kickoff)}</span></span>
      <span class="drop-markets">${m.markets.slice(0, 3).map((x) => `<span class="odd-move down" title="Açılış ${fmtDateTime(x.opened_at)}"><b>${esc(x.market)}</b> ${moveText(x)} <span class="drop-pct">%${Math.abs(x.change_pct)}</span></span>`).join("")}</span>
    </div>`).join("")}</div>`;
}
