const fs = require('node:fs');
const { parseArgs } = require('node:util');
const { connect } = require('./build_model.cjs');

function checkRow(payload, expected) {
  const data = payload.data;
  if (data?.rowCount !== 1 || data.isTruncated || data.rows?.length !== 1) {
    throw new Error('Reconciliation requires exactly one complete row');
  }
  const actual = data.rows[0];
  for (const [field, value] of Object.entries(expected)) {
    if (!Object.hasOwn(actual, `[${field}]`)) throw new Error(`Reconciliation field missing: ${field}`);
    const observed = actual[`[${field}]`];
    const equal = value === null ? observed == null : typeof value === 'number' && !Number.isInteger(value)
      ? typeof observed === 'number' && Math.abs(observed - value) <= 1e-12
      : observed === value;
    if (!equal) throw new Error(`Reconciliation ${field}: expected ${value}, got ${observed}`);
  }
  return { fields: Object.keys(expected).length, actual };
}

function checkRows(payload, expected, keyColumns) {
  const data = payload.data;
  if (!keyColumns?.length || data?.isTruncated || data?.rows?.length !== expected.length || data.rowCount !== expected.length) {
    throw new Error('Queue reconciliation requires explicit keys and a complete matching row count');
  }
  const observed = new Map();
  for (const row of data.rows) {
    const key = JSON.stringify(keyColumns.map(field => row[`[${field}]`]));
    if (observed.has(key)) throw new Error(`Duplicate actual row identity: ${key}`);
    observed.set(key, row);
  }
  let fields = 0;
  for (const row of expected) {
    const key = JSON.stringify(keyColumns.map(field => row[field]));
    if (!observed.has(key)) throw new Error(`Expected row identity absent: ${key}`);
    fields += checkRow({ data: { rowCount: 1, rows: [observed.get(key)] } }, row).fields;
    observed.delete(key);
  }
  return { rows: expected.length, fields, keyColumns };
}

function payloads(response) {
  const values = [];
  for (const item of response.content || []) {
    const text = item.type === 'text' ? item.text : item.type === 'resource' ? item.resource?.text : undefined;
    if (typeof text !== 'string') continue;
    try { values.push(JSON.parse(text)); } catch { values.push({ text }); }
  }
  if (response.structuredContent) values.push(response.structuredContent);
  if (response.isError || values.some(value => value.error || value.success === false ||
      value.status === 'error' || value.summary?.failureCount > 0)) {
    throw new Error(JSON.stringify(response));
  }
  if (values.length === 0 && response._meta?.annotations?.readOnlyHint !== false) {
    throw new Error(`MCP returned no inspectable payload: ${JSON.stringify(response)}`);
  }
  return values;
}

async function run({ serverPath, plan, outputPath }) {
  const mcp = connect(serverPath);
  const evidence = { status: 'running', started_at_utc: new Date().toISOString(), operations: [] };
  try {
    const init = await mcp.request('initialize', { protocolVersion: '2025-03-26', capabilities: {},
      clientInfo: { name: 'f1-model-acceptance-runner', version: '1.0.0' } });
    mcp.notify('notifications/initialized');
    evidence.server = init.serverInfo;
    let connectionName;
    for (const step of plan.operations) {
      const request = { ...step.request };
      if (step.useConnection) {
        if (!connectionName) throw new Error('Plan requires connection before one was captured');
        request.connectionName = connectionName;
      }
      const record = { id: step.id, tool: step.tool, operation: request.operation, status: 'running' };
      evidence.operations.push(record);
      const start = performance.now();
      const response = await mcp.request('tools/call', { name: step.tool, arguments: { request } });
      record.raw = response;
      const data = payloads(response);
      record.payloads = data;
      record.duration_ms = performance.now() - start;
      if (step.expectedRow) record.reconciliation = checkRow(data[0], step.expectedRow);
      if (step.expectedRows) record.reconciliation = checkRows(data[0], step.expectedRows, step.keyColumns);
      if (step.requireReadyMeasures) {
        const results = data[0].results;
        if (!Array.isArray(results) || results.some(result => result.data?.state !== 'Ready')) {
          throw new Error('Measure readback contains an unavailable or invalid expression');
        }
      }
      if (step.captureConnection) {
        connectionName = data.map(value => typeof value.data === 'string' ? value.data : value.data?.connectionName)
          .find(value => typeof value === 'string');
        if (!connectionName) throw new Error('Connection response omitted its name');
      }
      record.status = 'passed';
      console.log(`${step.id}: passed (${Math.round(record.duration_ms)} ms)`);
      fs.writeFileSync(outputPath, JSON.stringify(evidence, null, 2) + '\n');
    }
    evidence.status = 'passed';
    return evidence;
  } catch (error) {
    evidence.status = 'failed';
    evidence.error = error.message;
    throw error;
  } finally {
    evidence.finished_at_utc = new Date().toISOString();
    fs.writeFileSync(outputPath, JSON.stringify(evidence, null, 2) + '\n');
    mcp.close();
  }
}

if (require.main === module) {
  const { values } = parseArgs({ options: { 'server-entry': { type: 'string' },
    plan: { type: 'string' }, output: { type: 'string' } } });
  if (!values['server-entry'] || !values.plan || !values.output) {
    throw new Error('Required: --server-entry <existing MCP index.js> --plan <json> --output <json>');
  }
  run({ serverPath: values['server-entry'], plan: JSON.parse(fs.readFileSync(values.plan, 'utf8')),
    outputPath: values.output }).catch(error => { console.error(error.message); process.exitCode = 1; });
}

module.exports = { payloads, checkRow, checkRows, run };
