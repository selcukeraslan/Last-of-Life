(() => {
  const root = document.documentElement, btn = document.getElementById("themeToggle");
  const mq = matchMedia("(prefers-color-scheme: light)");
  const current = () => root.dataset.theme || (mq.matches ? "light" : "dark");
  const apply = () => {
    const light = current() === "light";
    document.querySelector('meta[name="theme-color"]').content = light ? "#f5f7fa" : "#0b0f14";
    btn.setAttribute("aria-pressed", String(light));
    btn.title = light ? "Koyu temaya geç" : "Açık temaya geç";
  };
  btn.addEventListener("click", () => {
    const next = current() === "light" ? "dark" : "light";
    root.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch {}
    apply();
  });
  mq.addEventListener?.("change", apply);
  apply();
})();
