// "Değerli Oranlar" sekmesi: modelin olasılığı iddaa.com oranından yüksek (EV > 0) seçimler.
// app.js'in yardımcılarını ($, esc, api, pct, fmtDateTime) kullanır; app.js'ten sonra yüklenir.
let valueReq = 0;

async function renderValue() {
  const el = $("#valueBets"), req = ++valueReq;
  el.innerHTML = `<p class="muted">Değerli oranlar hesaplanıyor…</p>`;
  const q = new URLSearchParams({
    days: $("#valueDays").value,
    min_prob: $("#valueMinProb").value,
    min_ev: $("#valueMinEv").value,
  });
  const d = await api(`/api/value-bets?${q}`);
  if (req !== valueReq) return; // daha yeni bir filtre seçildi
  const head = `<p class="muted">${d.matches} yaklaşan maç · ${d.matches_with_odds} maçta iddaa oranı var · ${d.items.length} değerli seçim${d.iddaa_last_update ? " · oranlar " + fmtAgo(d.iddaa_last_update) : ""}</p>`;
  if (!d.items.length) { el.innerHTML = head + `<div class="card muted">${esc(d.message)}</div>`; return; }
  el.innerHTML = head + `<div class="card"><table class="value-table">
    <tr><th class="l">Maç</th><th class="l">Lig</th><th>Saat</th><th class="l">Pazar</th><th>Seçim</th><th>Model</th><th>iddaa oranı</th><th>Örtük</th><th>EV</th></tr>
    ${d.items.map((v) => `<tr class="clickable" data-id="${esc(v.id)}">
      <td class="l"><b>${esc(v.home)}</b> – ${esc(v.away)}</td><td class="l">${esc(v.league_name)}</td>
      <td>${fmtDateTime(v.kickoff)}</td><td class="l">${esc(v.market)}</td>
      <td><span class="badge b-info">${esc(v.selection)}</span></td>
      <td>${(v.model_probability * 100).toFixed(1)}%</td><td><b class="iddaa-odd">${v.iddaa_odds.toFixed(2)}</b></td>
      <td>${(v.implied_probability * 100).toFixed(1)}%</td><td><b class="ev-pos">+${(v.ev * 100).toFixed(1)}%</b></td></tr>`).join("")}
  </table><p class="muted">EV = model olasılığı × iddaa oranı − 1. Pozitif EV uzun vadede kâr garantisi değildir; model hatalı olabilir.</p></div>`;
}

for (const id of ["#valueDays", "#valueMinProb", "#valueMinEv"]) {
  $(id).addEventListener("change", () => {
    renderValue().catch((e) => { $("#valueBets").innerHTML = `<div class="card" style="color:var(--bad)">Hata: ${esc(e.message)}</div>`; });
  });
}
