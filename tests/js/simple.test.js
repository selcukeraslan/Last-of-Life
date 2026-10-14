const test = require("node:test");
const assert = require("node:assert/strict");
const Simple = require("../../static/simple.js");

test("plain Turkish labels", () => {
  assert.equal(Simple.headline("Ü2.5"), "2.5 Üst");
  assert.equal(Simple.title("Ü2.5"), "3 veya daha fazla gol");
  assert.equal(Simple.title("A2.5"), "En fazla 2 gol");
  assert.equal(Simple.title("KG Var"), "İki takım da gol atar");
});

test("server summary is rendered with 3-level badge and no jargon", () => {
  const html = Simple.pickBlock({ summary: { market: "2", headline: "MS 2", title: "Deplasman kazanır", odds: 2.1, level: 3, level_label: "Yüksek", reason: "Rakip zayıf." } });
  assert.match(html, /MS 2/);
  assert.match(html, /2\.10/);
  assert.match(html, /conf-3/);
  assert.doesNotMatch(html, /xG|EV|Kelly|Elo|lambda/i);
});
