const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { build, connect } = require('../scripts/build_model.cjs');

const fakeServer = `
const fs = require('node:fs');
const path = require('node:path');
require('node:readline').createInterface({ input: process.stdin }).on('line', line => {
  const message = JSON.parse(line);
  if (!message.id) return;
  let result;
  if (message.method === 'initialize') result = { serverInfo: { name: 'test-only-mcp' } };
  else if (message.method === 'echo') result = message.params;
  else if (message.method === 'fail') {
    process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: message.id, error: { code: -1, message: 'test failure' } }) + '\\n');
    return;
  } else if (message.method === 'tools/call') {
    const req = message.params.arguments.request;
    if (req.operation === 'ExportToTmdlFolder') {
      fs.mkdirSync(req.tmdlFolderPath, { recursive: true });
      fs.writeFileSync(path.join(req.tmdlFolderPath, 'model.tmdl'), 'test fixture only');
    }
    if (message.params.name === 'table_operations' && req.operation === 'Create' && req.definitions[0]?.name === 'Fail') {
      result = { isError: true, content: [{ type: 'text', text: JSON.stringify({ error: 'rejected table' }) }] };
    } else if (message.params.name === 'table_operations' && req.operation === 'Create' && req.definitions[0]?.name === 'Partial') {
      result = { isError: false, content: [{ type: 'text', text: JSON.stringify({ summary: { failureCount: 1 } }) }] };
    } else result = { isError: false, content: [{ type: 'text', text: JSON.stringify({ data: [], operation: req.operation }) }] };
  }
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: message.id, result }) + '\\n');
});
`;

function fixture(t, tableName = 'Test') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'f1-model-test-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const serverPath = path.join(root, 'server.cjs');
  const blueprintPath = path.join(root, 'blueprint.json');
  fs.writeFileSync(serverPath, fakeServer);
  fs.writeFileSync(blueprintPath, JSON.stringify({ modelDefinition: {}, parameterDefinition: {},
    tableDefinitions: [{ name: tableName }], relationshipDefinitions: [], measureDefinitions: [] }));
  return { serverPath, blueprintPath, exportPath: path.join(root, 'export'),
    evidencePath: path.join(root, 'evidence.json') };
}

test('CLI requires the installed platform-specific MCP entry instead of launching an unverified wrapper', () => {
  const result = spawnSync(process.execPath, [path.resolve(__dirname, '../scripts/build_model.cjs')], { encoding: 'utf8' });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /--server-entry/);
  assert.doesNotMatch(result.stderr, /Installing missing platform package/);
});

test('MCP request IDs preserve concurrent responses and propagate RPC errors', async t => {
  const options = fixture(t);
  const client = connect(options.serverPath);
  t.after(() => client.close());
  assert.deepEqual(await Promise.all([client.request('echo', { value: 1 }),
    client.request('echo', { value: 2 })]), [{ value: 1 }, { value: 2 }]);
  await assert.rejects(client.request('fail', {}), /test failure/);
});

test('offline build exports through MCP and records validation limits', async t => {
  const options = fixture(t);
  const evidence = await build(options);
  assert.equal(evidence.status, 'passed');
  assert.equal(evidence.live_dax_refresh_rendering, 'not_performed');
  assert.equal(fs.existsSync(path.join(options.exportPath, 'model.tmdl')), true);
  assert.equal(evidence.operations.at(-1).operation, 'ExportToTmdlFolder');
  assert.equal(JSON.parse(fs.readFileSync(options.evidencePath)).status, 'passed');
});

test('MCP application error prevents export and persists failure evidence', async t => {
  const options = fixture(t, 'Fail');
  await assert.rejects(build(options), /rejected table/);
  assert.equal(fs.existsSync(options.exportPath), false);
  const evidence = JSON.parse(fs.readFileSync(options.evidencePath));
  assert.equal(evidence.status, 'failed');
  assert.equal(evidence.operations.some(op => op.operation === 'ExportToTmdlFolder'), false);
});

test('batch item failure stops the build even when the MCP transport succeeds', async t => {
  const options = fixture(t, 'Partial');
  await assert.rejects(build(options), /failureCount/);
  assert.equal(fs.existsSync(options.exportPath), false);
  assert.equal(JSON.parse(fs.readFileSync(options.evidencePath)).status, 'failed');
});

test('existing model export is preserved instead of overwritten', async t => {
  const options = fixture(t);
  fs.mkdirSync(options.exportPath);
  const manualFile = path.join(options.exportPath, 'owner-file');
  fs.writeFileSync(manualFile, 'preserve');
  await assert.rejects(build(options), /already exists/);
  assert.equal(fs.readFileSync(manualFile, 'utf8'), 'preserve');
  assert.equal(fs.existsSync(options.evidencePath), false);
});
