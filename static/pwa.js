// PWA: service worker kaydı + çevrimdışı / "yeni sürüm" bandı. app.js'ten bağımsızdır.
(() => {
  if (!("serviceWorker" in navigator)) return;

  let bar, hideTimer;
  const showBar = (text, { action, sticky } = {}) => {
    if (!bar) {
      bar = document.createElement("div");
      bar.setAttribute("role", "status");
      bar.style.cssText = "position:fixed;left:8px;right:8px;bottom:8px;z-index:1000;display:flex;gap:10px;align-items:center;" +
        "justify-content:center;padding:8px 12px;border:1px solid var(--warn,#f59e0b);border-radius:8px;" +
        "background:var(--panel,#171e26);color:var(--text,#e6edf3);font-size:13px;box-shadow:0 2px 10px rgba(0,0,0,.35)";
      document.body.appendChild(bar);
    }
    clearTimeout(hideTimer);
    bar.replaceChildren(Object.assign(document.createElement("span"), { textContent: text }));
    if (action) {
      const btn = Object.assign(document.createElement("button"), { className: "btn", textContent: action.label });
      btn.addEventListener("click", action.run);
      bar.appendChild(btn);
    }
    bar.hidden = false;
    if (!sticky) hideTimer = setTimeout(hideBar, 8000);
  };
  const hideBar = () => { if (bar) bar.hidden = true; };

  const offlineText = "Çevrimdışısınız — son kaydedilen veriler gösteriliyor.";
  window.addEventListener("offline", () => showBar(offlineText, { sticky: true }));
  window.addEventListener("online", () => { hideBar(); });
  if (!navigator.onLine) window.addEventListener("DOMContentLoaded", () => showBar(offlineText, { sticky: true }));

  navigator.serviceWorker.addEventListener("message", (e) => {
    if (e.data?.type !== "sw-cache-hit" || !navigator.onLine) return; // çevrimdışıyken sabit bant zaten açık
    const when = e.data.cachedAt ? new Date(e.data.cachedAt).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" }) : "";
    showBar(`Güncel veri alınamadı — ${when ? when + " tarihli " : ""}kayıtlı veri gösteriliyor.`);
  });

  const hadController = !!navigator.serviceWorker.controller; // ilk kurulumda "yeni sürüm" gösterme
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (hadController) showBar("Yeni sürüm hazır.", { action: { label: "Yenile", run: () => location.reload() }, sticky: true });
  });

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" })
      .catch((err) => console.warn("Service worker kaydı başarısız:", err));
  });
})();
