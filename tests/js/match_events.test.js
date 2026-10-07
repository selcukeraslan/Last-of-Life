const test = require("node:test");
const assert = require("node:assert/strict");
const { bind } = require("../../static/match-events.js");

function fakeDocument() {
  const listeners = new Map();
  return {
    addEventListener(type, handler) { listeners.set(type, handler); },
    dispatch(type, event) { listeners.get(type)(event); },
  };
}

test("delegated click opens a dynamically rendered small-league row with both IDs", () => {
  const doc = fakeDocument(), opened = [], closed = [];
  bind(doc, (...args) => opened.push(args), () => closed.push(true));
  // The row is created after binding, as happens when the selected league is rendered.
  const row = { dataset: { matchId: "iddaa-event-9001", competitionId: "98765" } };
  const target = {
    id: "",
    closest(selector) {
      if (selector === "[data-match-id]") return row;
      return null;
    },
  };

  doc.dispatch("click", { target });

  assert.deepEqual(opened, [["iddaa-event-9001", "98765"]]);
  assert.deepEqual(closed, []);
});

test("delegated click opens a recommendations row carrying event and competition IDs", () => {
  const doc = fakeDocument(), opened = [];
  bind(doc, (...args) => opened.push(args), () => {});
  const row = { dataset: { id: "recommendation-event-1", competitionId: "98765" } };
  const target = {
    id: "",
    closest(selector) { return selector === ".clickable[data-id]" ? row : null; },
  };

  doc.dispatch("click", { target });

  assert.deepEqual(opened, [["recommendation-event-1", "98765"]]);
});

test("clicking nested slip controls does not open the containing match", () => {
  const doc = fakeDocument(), opened = [];
  bind(doc, (...args) => opened.push(args), () => {});
  const row = { dataset: { matchId: "event-1", competitionId: "584" } };
  const control = {};
  const target = {
    id: "",
    closest(selector) {
      if (selector === "[data-match-id]") return row;
      if (selector === ".slip-add, .slip-remove, #slipClear, #slipRefresh") return control;
      return null;
    },
  };

  doc.dispatch("click", { target });

  assert.deepEqual(opened, []);
});

test("Enter and Space activate focused match rows; Escape closes the modal", () => {
  const doc = fakeDocument(), opened = [], closed = [];
  bind(doc, (...args) => opened.push(args), () => closed.push(true));
  const target = {
    dataset: { matchId: "event-2", competitionId: "123" },
    matches(selector) { return selector.includes(".match[data-match-id]"); },
  };
  let prevented = false;

  doc.dispatch("keydown", { key: "Enter", target, preventDefault() {} });
  doc.dispatch("keydown", { key: " ", target, preventDefault() { prevented = true; } });
  doc.dispatch("keydown", { key: "Escape", target, preventDefault() {} });

  assert.deepEqual(opened, [["event-2", "123"], ["event-2", "123"]]);
  assert.equal(prevented, true);
  assert.deepEqual(closed, [true]);
});
