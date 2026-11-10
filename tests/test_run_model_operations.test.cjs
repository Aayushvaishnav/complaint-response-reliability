const { test } = require('node:test');
const assert = require('node:assert/strict');
const { payloads, checkRow, checkRows } = require('../scripts/run_model_operations.cjs');

test('reads text, embedded resource and structured MCP payloads', () => {
  assert.deepEqual(payloads({ content: [{ type: 'text', text: '{"data":3}' },
    { type: 'resource', resource: { text: '{"rows":[1,2]}' } }] }), [{ data: 3 }, { rows: [1, 2] }]);
  assert.deepEqual(payloads({ structuredContent: { data: 4 } }), [{ data: 4 }]);
});

test('operation and batch failures cannot pass acceptance', () => {
  for (const value of [{ error: 'bad query' }, { success: false }, { status: 'error' },
    { summary: { failureCount: 1 } }]) {
    assert.throws(() => payloads({ content: [{ type: 'text', text: JSON.stringify(value) }] }));
  }
  assert.throws(() => payloads({ isError: true, content: [{ type: 'text', text: 'failure' }] }));
  assert.throws(() => payloads({ content: [] }));
});

test('successful mutating operations may acknowledge without content; require readback separately', () => {
  assert.deepEqual(payloads({ content: [], isError: false,
    _meta: { annotations: { readOnlyHint: false } } }), []);
  assert.throws(() => payloads({ content: [], isError: true,
    _meta: { annotations: { readOnlyHint: false } } }));
});

test('reconciliation rejects count drift, truncated output and undefined rates converted to zero', () => {
  const result = { data: { rowCount: 1, isTruncated: false, rows: [{ '[count]': 100, '[rate]': 0.1, '[undefined]': null }] } };
  assert.equal(checkRow(result, { count: 100, rate: 0.1, undefined: null }).fields, 3);
  assert.throws(() => checkRow(result, { count: 99 }));
  assert.throws(() => checkRow(result, { undefined: 0 }));
  assert.throws(() => checkRow(result, { missing: null }));
  assert.throws(() => checkRow({ data: { ...result.data, isTruncated: true } }, { count: 100 }));
});

test('queue parity compares identity sets and rejects duplicated or missing keys', () => {
  const result = { data: { rowCount: 2, isTruncated: false, rows: [
    { '[key]': 2, '[rank]': 1 }, { '[key]': 1, '[rank]': 1 }] } };
  assert.deepEqual(checkRows(result, [{ key: 1, rank: 1 }, { key: 2, rank: 1 }], ['key']),
    { rows: 2, fields: 4, keyColumns: ['key'] });
  assert.throws(() => checkRows(result, [{ key: 1, rank: 1 }], ['key']));
  assert.throws(() => checkRows(result, [{ key: 1, rank: 1 }, { key: 1, rank: 1 }], ['key']));
  assert.equal(checkRows({ data: { rowCount: 0, rows: [] } }, [], ['key']).rows, 0);
});
