// Canlı uçtan uca duman testi. Kullanım: NODE_PATH=<playwright'lı node_modules> node tests/e2e/live_smoke.js [url]
// Playwright repoya bağımlılık değildir; ayrıca kurulmalıdır (README: tests/e2e/README.md).
const { chromium } = require("playwright");
const BASE = process.argv[2] || "https://iddia-oran.vercel.app";
const OUT = process.env.E2E_OUT || "/tmp/e2e-shots";
require("fs").mkdirSync(OUT, { recursive: true });
const problems = [];

async function run(name, viewport) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport, serviceWorkers: "block" });
  const page = await ctx.newPage();
  let step = "init";
  const note = (kind, msg) => { problems.push(`[${name}] ${step}: ${kind}: ${String(msg).slice(0, 300)}`); };
  page.on("console", (m) => { if (m.type() === "error") note("console", m.text()); });
  page.on("pageerror", (e) => note("pageerror", e.message));
  page.on("response", (r) => { if (r.status() >= 500 || (r.status() >= 400 && r.url().includes("/api/"))) note("http" + r.status(), r.url()); });
  const shot = (s) => page.screenshot({ path: `${OUT}/${name}-${s}.png` }).catch(() => {});
  const check = async () => {
    const t = await page.evaluate(() => document.body.innerText);
    for (const m of t.matchAll(/Hata:\s*\{[^\n]*|undefined|\[object Object\]|NaN/g)) note("text", m[0]);
  };
  const tab = async (t) => { step = "tab " + t; const b = page.locator(`nav.tabs [data-tab="${t}"]`); if (!(await b.isVisible())) await page.click("#moreBtn"); await b.click(); await page.waitForTimeout(1500); await check(); await shot(t); };
  const tryDo = async (label, fn) => { step = label; try { await fn(); } catch (e) { note("exception", e.message.split("\n").slice(0, 4).join(" | ")); } };

  await page.goto(BASE, { waitUntil: "networkidle" });
  await tryDo("age gate", async () => { await page.click(".age-yes", { timeout: 5000 }); await page.waitForTimeout(500); });
  await check(); await shot("home");
  await tryDo("today summary", async () => { await page.waitForSelector("#today .today-grid", { timeout: 15000 }); if (!(await page.$("#themeToggle"))) note("missing", "tema düğmesi"); await page.click("#themeToggle"); await shot("home-toggled-theme"); await page.click("#themeToggle"); });

  step = "matches";
  const chips = await page.$$eval("#leagueChips .chip[data-league]:not(.small-league-chip)", (e) => e.map((x) => x.dataset.league));
  for (const id of chips) await tryDo("league " + id, async () => {
    await page.click(`#leagueChips .chip[data-league="${id}"]`); await page.waitForTimeout(1200); await check();
  });
  await tryDo("main match detail", async () => {
    await page.click(`#leagueChips .chip[data-league="${chips[0]}"]`); await page.waitForTimeout(1200);
    await page.click("#matches .card.match"); await page.waitForSelector("#modal:not(.hidden)");
    await page.waitForTimeout(2500);
    if ((await page.innerText("#modalBody")).trim().length < 80) note("empty", "main modal");
    if (!(await page.$("#matchInsights .card"))) note("empty", "main modal içgörüler (form/gol/haber) yok");
    await check(); await shot("modal-main");
    await page.keyboard.press("Escape"); await page.waitForTimeout(300);
    if (await page.$("#modal:not(.hidden)")) { await page.click("#modal", { position: { x: 2, y: 2 } }); await page.waitForTimeout(300); }
    if (await page.$("#modal:not(.hidden)")) note("modal", "ana modal kapanmadı");
  });
  await tryDo("small leagues", async () => {
    await page.click("[data-small-leagues-toggle]"); await page.waitForTimeout(500);
    const ids = await page.$$eval(".small-league-chip", (e) => e.map((x) => x.dataset.league));
    if (!ids.length) note("empty", "küçük lig yok");
    let opened = 0;
    for (const id of ids.slice(0, 6)) {
      await page.click(`.small-league-chip[data-league="${id}"]`); await page.waitForTimeout(1200); await check();
      if (!opened && await page.$("#matches .card.match")) {
        opened = 1; await shot("small-league");
        await page.click("#matches .card.match"); await page.waitForSelector("#modal:not(.hidden)"); await page.waitForTimeout(2500);
        if ((await page.innerText("#modalBody")).trim().length < 60) note("empty", "small modal");
        await check(); await shot("modal-small");
        await page.keyboard.press("Escape"); await page.waitForTimeout(300);
        if (await page.$("#modal:not(.hidden)")) await page.click("#modal", { position: { x: 2, y: 2 } });
      }
    }
    await page.click("[data-small-leagues-toggle]"); await page.waitForTimeout(300);
  });

  await tab("picks");
  await tryDo("picks small", async () => { await page.click('[data-picks-category="small"]'); await page.waitForTimeout(1500); await check(); await shot("picks-small"); });

  await tab("coupons");
  await tryDo("coupon nav", async () => {
    await page.click("#couponNext"); await page.waitForTimeout(1500); await check();
    await page.click("#couponPrev"); await page.click("#couponPrev"); await page.waitForTimeout(1500); await check(); await shot("coupons-prev");
    await page.click("#couponNext"); await page.waitForTimeout(1000);
    const alts = await page.$$("#coupons button");
    for (const b of alts.slice(0, 8)) { try { await b.click({ timeout: 1500 }); await page.waitForTimeout(300); } catch {} }
    await check();
  });
  await tab("coupon-history");
  await tab("report");
  await tab("value");
  await tryDo("value filters", async () => {
    await page.selectOption("#valueDays", { index: 0 }).catch(() => {});
    for (const sel of ["#valueMinProb", "#valueMinEv"]) {
      const n = await page.$$eval(sel + " option", (o) => o.length);
      for (let i = 0; i < n; i++) { await page.selectOption(sel, { index: i }); await page.waitForTimeout(500); await check(); }
    }
  });
  await tab("matches");
  await tryDo("slip add", async () => {
    await page.click(`#leagueChips .chip[data-league="${chips[0]}"]`); await page.waitForTimeout(1200);
    const btns = await page.$$("#matches .slip-add");
    for (const b of btns.slice(0, 2)) await b.click();
  });
  await tab("slip");
  await tryDo("slip remove", async () => { const r = await page.$(".slip-remove"); if (r) await r.click(); await page.waitForTimeout(500); await check(); await shot("slip-removed"); });

  await tab("table");
  await tryDo("standings", async () => {
    const ids = await page.$$eval("#leagueChips .chip[data-league]", (e) => e.map((x) => x.dataset.league));
    for (const id of ids) {
      const small = id.startsWith("small:");
      if (small && !(await page.$(".small-league-options:not(.hidden)"))) await page.click("[data-small-leagues-toggle]");
      await page.click(`.chip[data-league="${id}"]`); await page.waitForTimeout(1200); await check();
      if (!(await page.innerText("#table")).trim()) note("empty", "table " + id);
    }
  });
  await tab("model");
  await tryDo("backtest", async () => { await page.click("#btnBacktest"); await page.waitForTimeout(8000); await check(); await shot("backtest"); });
  await tryDo("update", async () => { if (await page.isDisabled("#btnUpdate")) { note("info", "Verileri güncelle pasif (güncelleme sürüyor?)"); return; }
    await page.click("#btnUpdate"); await page.waitForTimeout(6000); await check(); await shot("update"); });
  await browser.close();
}

(async () => {
  await run("desktop", { width: 1280, height: 900 });
  if (!process.env.E2E_DESKTOP_ONLY) await run("mobile", { width: 390, height: 844 });
  const uniq = [...new Set(problems)];
  console.log(uniq.length ? uniq.join("\n") : "CLEAN");
  process.exit(uniq.length ? 1 : 0);
})();
