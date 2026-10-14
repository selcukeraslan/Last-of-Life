// Ana sayfa üst çubuğu: giriş durumu; yönetici dışına veri güncelleme/backtest düğmelerini gizler.
(async () => {
  const box = document.getElementById("authBox");
  if (!box) return;
  let user = null;
  try { user = (await (await fetch("/api/auth/me")).json()).user; } catch (e) { return; }
  const isAdmin = user?.role === "admin";
  for (const id of ["btnUpdate", "btnBacktest"]) document.getElementById(id)?.classList.toggle("hidden", !isAdmin);
  if (!user) { box.innerHTML = '<a href="/giris" class="btn ghost">Giriş</a>'; return; }
  box.textContent = "";
  const who = document.createElement("span");
  who.className = "muted";
  who.textContent = user.email + (isAdmin ? " · yönetici" : "");
  const out = document.createElement("button");
  out.className = "btn ghost";
  out.textContent = "Çıkış";
  out.addEventListener("click", async () => { await fetch("/api/auth/logout", { method: "POST" }); location.reload(); });
  box.append(who, " ", out);
})();
