const test = require("node:test");
const assert = require("node:assert/strict");
const Share = require("../../static/coupon-share.js");

test("share preparation keeps all picks and renders absent odds as a dash", () => {
  const picks = Array.from({ length: 30 }, (_, i) => ({ home: `Ev ${i}`, away: `Dep ${i}`, market: "1", odds: i ? 1.5 : null }));
  const square = Share.prepare({ picks, totalOdds: 2.25 }, "square");
  const story = Share.prepare({ picks, totalOdds: 2.25 }, "story");
  assert.equal(square.picks.length, 30);
  assert.equal(square.picks[0].oddsText, "-");
  assert.equal(square.picks[1].oddsText, "1.50");
  assert.ok(square.rowH > 0);
  assert.ok(square.top + square.picks.length * (square.rowH + square.gap) + square.totalHeight <= square.footerTop + 1e-9);
  assert.ok(story.rowH > square.rowH);
  assert.equal(story.totalOddsText, "2.25");
});
