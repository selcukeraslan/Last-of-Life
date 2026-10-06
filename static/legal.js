// Yasal uyarılar: 18+ onay kutusu (ilk ziyarette bir kez) ve kupon kartlarındaki kısa uyarı satırı.
(() => {
  const KEY = "ageConfirmed";
  const NOTE = "18+ · Tahminler garanti değildir. Sorumlu oynayın.";
  const store = {
    get() { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } },
    set() { try { localStorage.setItem(KEY, "1"); } catch { /* gizli sekme: oturum boyunca yeter */ } },
  };

  function showAgeGate() {
    const gate = document.createElement("div");
    gate.className = "age-gate";
    gate.innerHTML = `<div class="age-box" role="dialog" aria-modal="true" aria-labelledby="ageTitle">
      <h2 id="ageTitle">18 yaş sınırı</h2>
      <p>Bu site istatistiksel spor tahminleri içerir. Tahminler garanti değildir, yatırım tavsiyesi değildir. Devam etmek için 18 yaşından büyük olmalısınız.</p>
      <button type="button" class="btn age-yes">18 yaşından büyüğüm</button>
      <button type="button" class="age-no">Hayır</button>
      <p class="age-msg muted hidden">Bu siteyi kullanmak için 18 yaşından büyük olmalısınız.</p>
    </div>`;
    document.body.appendChild(gate);
    document.body.classList.add("age-locked");
    const yes = gate.querySelector(".age-yes");
    yes.addEventListener("click", () => { store.set(); gate.remove(); document.body.classList.remove("age-locked"); });
    gate.querySelector(".age-no").addEventListener("click", () => gate.querySelector(".age-msg").classList.remove("hidden"));
    yes.focus();
  }

  function addCouponNotes() {
    document.querySelectorAll(".coupon-card:not([data-legal])").forEach((card) => {
      card.dataset.legal = "1";
      const p = document.createElement("p");
      p.className = "legal-note muted";
      p.textContent = NOTE;
      card.appendChild(p);
    });
  }

  if (!store.get()) showAgeGate();
  addCouponNotes();
  new MutationObserver(addCouponNotes).observe(document.body, { childList: true, subtree: true });
})();
