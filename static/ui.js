// Ortak durum bileşenleri: iskelet, boş durum, hata.
window.Ui = (() => {
  const e = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const skeleton = (n = 3) => `<div class="skeleton-list" role="status" aria-label="Yükleniyor">${'<div class="card skeleton"><i></i><i></i><i></i></div>'.repeat(n)}</div>`;
  const empty = (title, text = "") => `<div class="state state-empty"><div class="state-ico" aria-hidden="true">∅</div><b>${e(title)}</b>${text ? `<p class="muted">${e(text)}</p>` : ""}</div>`;
  const error = (msg) => `<div class="state state-error" role="alert"><div class="state-ico" aria-hidden="true">!</div><b>Bir sorun oluştu</b><p class="muted">${e(String(msg).replace(/^Hata:\s*/, "").slice(0, 160))}</p></div>`;
  return { skeleton, empty, error };
})();
