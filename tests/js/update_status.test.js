const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const U = require('../../static/update-status.js');

test('update response immediately replaces the four-day-old label state', () => {
  const state = {lastUpdate:'2026-10-19T19:55:24+00:00'};
  assert.equal(U.apply(state,{status:'cooldown',last_updated_at:'2026-10-24T18:15:17+00:00'}),true);
  assert.equal(state.lastUpdate,'2026-10-24T18:15:17+00:00');
  assert.equal(U.apply(state,{last_update:'2026-10-19T19:55:24+00:00'}),false);
  assert.equal(state.lastUpdate,'2026-10-24T18:15:17+00:00');
});

test('invalid and missing timestamps cannot destroy a verified timestamp', () => {
  const state = {lastUpdate:'2026-10-24T18:15:17+00:00'};
  for (const r of [{},{last_updated_at:null},{last_update:'invalid'}]) assert.equal(U.apply(state,r),false);
  assert.equal(U.apply(state,{last_update:'2026-10-24T18:16:17Z'}),true);
});

test('fresh metadata requests bypass an existing CDN query cache', () => {
  assert.match(U.freshUrl('/api/leagues'), /^\/api\/leagues\?_fresh=\d+$/);
  assert.match(U.freshUrl('/api/leagues?league=x'), /&_fresh=\d+$/);
  const html=fs.readFileSync('static/index.html','utf8');
  assert.ok(html.indexOf('/static/update-status.js') < html.indexOf('/static/app.js'));
});
