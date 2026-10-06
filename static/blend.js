// iddaa oranlarıyla harmanlama: Model sekmesi karşılaştırması ve maç detayı notları.
// app.js'ten önce yüklenir; `esc`, `pct`, `fmtDateTime` ve `state` app.js'te tanımlıdır (çağrı anında kullanılır).
const BLEND_GROUPS = { "1x2": "1X2", ou25: "Alt/Üst 2.5", btts: "KG Var/Yok" };
const BLEND_VARIANTS = [["model", "Model (harmansız)"], ["blend", "Harmanlı"], ["market", "Yalnız piyasa"]];

function blendOddsLogStatus(log) {
  if (!log || !log.available) return `<p class="muted">Oran kaydı henüz kullanılamıyor (veritabanı migration'ı uygulanmamış olabilir).</p>`;
  if (!log.matches) return `<p class="muted">Geçmiş iddaa oranı verisi yok; oranlar bundan sonra her güncellemede kaydedilir. Karşılaştırma, kayıtlı maçlar sonuçlandıkça burada belirecek.</p>`;
  return `<p class="muted">Oran kaydı: <b>${log.matches}</b> maç kaydedildi, <b>${log.completed}</b>'i sonuçlandı (karşılaştırmaya girer); ilk kayıt ${fmtDateTime(log.since)}. Anlamlı bir karşılaştırma için en az birkaç yüz sonuçlanmış maç gerekir.</p>`;
}

function blendGroupTable(name, rows, weight) {
  const sum = rows.reduce((a, r) => a + r.n, 0);
  const best = (key) => Math.min(...BLEND_VARIANTS.map(([v]) => rows.reduce((a, r) => a + r[v][key] * r.n, 0) / sum));
  const avg = (v, key) => rows.reduce((a, r) => a + r[v][key] * r.n, 0) / sum;
  const cell = (v, key, digits) => { const x = avg(v, key); return `<td>${x === best(key) ? "<b>" : ""}${x.toFixed(digits)}${x === best(key) ? "</b>" : ""}</td>`; };
  const sweepKeys = Object.keys(rows[0].sweep).sort((a, b) => a - b); // tamsayı anahtarlar JS'te öne geçer
  const sweep = sweepKeys.map((w) => rows.reduce((a, r) => a + r.sweep[w] * r.n, 0) / sum);
  const bestSweep = Math.min(...sweep);
  return `<h4>${BLEND_GROUPS[name]} · ${sum} maç</h4>
    <table><tr><th class="l">Olasılık</th><th>Brier</th><th>Log-loss</th><th>İsabet</th></tr>
    ${BLEND_VARIANTS.map(([v, label]) => `<tr><td class="l">${label}${v === "blend" ? ` <span class="muted">(w=${weight})</span>` : ""}</td>${cell(v, "brier", 3)}${cell(v, "logloss", 3)}<td>${pct(avg(v, "accuracy"))}</td></tr>`).join("")}</table>
    <table><tr><th class="l">Piyasa ağırlığı</th>${sweepKeys.map((w) => `<th>${w}</th>`).join("")}</tr>
    <tr><td class="l">Log-loss</td>${sweep.map((x) => `<td>${x === bestSweep ? "<b>" : ""}${x.toFixed(3)}${x === bestSweep ? "</b>" : ""}</td>`).join("")}</tr></table>`;
}

// d: /api/backtest yanıtı. #blendBacktest alanını doldurur.
function renderBlendBacktest(d) {
  const el = document.querySelector("#blendBacktest");
  if (!el) return;
  const results = d.data ? Object.values(d.data.results).filter((r) => r.blend && r.blend.matches) : [];
  let html = `<h4 style="margin-top:0">Harmanlı / harmansız karşılaştırma</h4>${blendOddsLogStatus(d.odds_log)}`;
  if (results.length) {
    const weight = results[0].blend.weight;
    for (const name of Object.keys(BLEND_GROUPS)) {
      const rows = results.map((r) => r.blend.groups[name]).filter(Boolean);
      if (rows.length) html += blendGroupTable(name, rows, weight);
    }
    html += `<p class="muted">Tüm ligler birlikte, yalnızca iddaa oranı kaydedilmiş maçlar üzerinde. Model olasılıkları o maçtan önceki verilerle (walk-forward) üretilir; en düşük değer en iyidir. Ağırlık satırı, piyasa ağırlığı arttıkça log-loss'un nasıl değiştiğini gösterir; <code>market_weight</code> bu taramaya göre ayarlanabilir.</p>`;
  }
  el.innerHTML = html;
}

// Maç detayı: harmanlama notu ve pazar başına model/piyasa olasılığı
function blendNote(m) {
  if (!m.blend || !m.blend.applied) return `<p class="muted">Bu maç için iddaa oranı yok; olasılıklar yalnızca modelden gelir.</p>`;
  return `<p class="muted">Olasılıklar iddaa.com oranlarından marjı temizlenmiş olasılıklarla harmanlandı (piyasa ağırlığı %${Math.round(m.blend.weight * 100)}). Harmanlanan pazarlarda model ve piyasa değerleri altta gösterilir.</p>`;
}
function blendDetail(item) {
  if (item.market_p == null) return "";
  return `<div class="muted" style="font-size:11px">model ${pct(item.model_p)} · piyasa ${pct(item.market_p)}</div>`;
}
