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

test('league list puts high, medium and low confidence before limited-data rows', () => {
  const m = (id, level, score, kickoff) => ({id, confidence:score, kickoff,
    summary:{market:'1',level}});
  const rows=[m('low',1,.4,'2026-10-24T10:00Z'),m('medium',2,.6,'2026-10-24T11:00Z'),
    m('high',3,.8,'2026-10-26T18:00Z'),m('higher',3,.9,'2026-10-27T18:00Z'),m('unknown',0,null,'2026-10-24T09:00Z')];
  assert.deepEqual(Simple.sortMatches(rows).map(m=>m.id),['higher','high','medium','low','unknown']);
  assert.equal(rows[0].id,'low');
});
