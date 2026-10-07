const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function load(league) {
  const calls = [], el = { innerHTML: "x" };
  const ctx = { state: { league }, $: () => el, esc: String, fmtDateTime: String,
    api: async (url) => { calls.push(url); return { matches: [], min_pct: 10 }; } };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(__dirname + "/../../static/odds-history.js", "utf8"), ctx);
  return { ctx, calls, el };
}

test("small leagues do not request /api/odds/drops (endpoint 404s for them)", async () => {
  const { ctx, calls, el } = load("small:br:brezilya-serie-a");
  await ctx.renderOddsDrops();
  assert.deepEqual(calls, []);
  assert.equal(el.innerHTML, "");
});

test("main leagues still request drops", async () => {
  const { ctx, calls } = load("tur.1");
  await ctx.renderOddsDrops();
  assert.equal(calls.length, 1);
});
