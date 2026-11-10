const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');
const fs = require('node:fs');
const path = require('node:path');
const { parseArgs } = require('node:util');

function connect(server) {
  const child = spawn(process.execPath, [server, '--start', '--accepteula'], {
    stdio: ['pipe', 'pipe', 'inherit'],
  });
  const pending = new Map();
  let nextId = 0;
  function fail(error) {
    for (const waiter of pending.values()) waiter.reject(error);
    pending.clear();
  }
  createInterface({ input: child.stdout }).on('line', line => {
    let response;
    try { response = JSON.parse(line); } catch { return; }
    const waiter = pending.get(response.id);
    if (!waiter) return;
    pending.delete(response.id);
    if (response.error) waiter.reject(new Error(JSON.stringify(response.error)));
    else waiter.resolve(response.result);
  });
  child.on('error', fail);
  child.on('exit', code => fail(new Error(`Modeling MCP exited: ${code}`)));
  function request(method, params) {
    const id = ++nextId;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
    });
  }
  return {
    request,
    notify(method) { child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method }) + '\n'); },
    close() { child.stdin.end(); child.kill(); },
  };
}

async function build({ blueprintPath, exportPath, evidencePath, serverPath }) {
  const blueprint = JSON.parse(fs.readFileSync(blueprintPath, 'utf8'));
  if (fs.existsSync(exportPath)) throw new Error(`Export target already exists; choose a fresh target: ${exportPath}`);
  const evidence = {
    status: 'running', started_at_utc: new Date().toISOString(),
    scope: 'offline_model_foundation', live_dax_refresh_rendering: 'not_performed',
    blueprint: path.relative(process.cwd(), blueprintPath), operations: [],
  };
  const mcp = connect(serverPath);
  const connectionName = 'F1-Foundation-Builder';
  async function call(name, request) {
    const response = await mcp.request('tools/call', { name, arguments: { request } });
    const texts = (response.content || []).filter(item => item.type === 'text').map(item => item.text);
    const payloads = texts.map(text => { try { return JSON.parse(text); } catch { return { text }; } });
    evidence.operations.push({ tool: name, operation: request.operation, response: payloads });
    if (response.isError || payloads.some(value => value.success === false || value.error ||
      value.status === 'error' || value.summary?.failureCount > 0)) {
      throw new Error(`${name} ${request.operation}: ${JSON.stringify(payloads)}`);
    }
    return payloads;
  }
  try {
    const init = await mcp.request('initialize', {
      protocolVersion: '2025-03-26', capabilities: {},
      clientInfo: { name: 'f1-offline-model-builder', version: '1.0.0' },
    });
    mcp.notify('notifications/initialized');
    evidence.server = init.serverInfo;
    await call('database_operations', { operation: 'Create', connectionName,
      createDefinition: { name: 'F1', modelName: 'F1', isOffline: true, compatibilityLevel: 1702,
        description: 'F1 local Import foundation; priority model and Gate D acceptance pending' } });
    await call('model_operations', { operation: 'Update', connectionName, definition: blueprint.modelDefinition });
    await call('named_expression_operations', { operation: 'CreateParameter', connectionName,
      definitions: [blueprint.parameterDefinition] });
    await call('table_operations', { operation: 'Create', connectionName,
      definitions: blueprint.tableDefinitions, options: { continueOnError: false, useTransaction: true } });
    await call('relationship_operations', { operation: 'Create', connectionName,
      definitions: blueprint.relationshipDefinitions, options: { continueOnError: false, useTransaction: true } });
    await call('table_operations', { operation: 'MarkAsDateTable', connectionName,
      markAsDateTableDefinitions: [{ tableName: 'Date', dateColumnName: 'Date' }] });
    await call('measure_operations', { operation: 'Create', connectionName,
      definitions: blueprint.measureDefinitions, options: { continueOnError: false, useTransaction: true } });
    evidence.inventory = {};
    for (const [key, tool] of [['tables', 'table_operations'], ['relationships', 'relationship_operations'],
      ['measures', 'measure_operations'], ['parameters', 'named_expression_operations']]) {
      evidence.inventory[key] = await call(tool, { operation: 'List', connectionName });
    }
    await call('database_operations', { operation: 'ExportToTmdlFolder', connectionName, tmdlFolderPath: exportPath });
    if (!fs.existsSync(path.join(exportPath, 'model.tmdl'))) throw new Error('MCP export did not produce model.tmdl');
    evidence.status = 'passed';
    evidence.export_path = path.relative(process.cwd(), exportPath);
    evidence.expected_counts = { tables: blueprint.tableDefinitions.length,
      relationships: blueprint.relationshipDefinitions.length, measures: blueprint.measureDefinitions.length };
    return evidence;
  } catch (error) {
    evidence.status = 'failed';
    evidence.error = error.message;
    throw error;
  } finally {
    evidence.finished_at_utc = new Date().toISOString();
    fs.mkdirSync(path.dirname(evidencePath), { recursive: true });
    fs.writeFileSync(evidencePath, JSON.stringify(evidence, null, 2) + '\n');
    mcp.close();
  }
}

if (require.main === module) {
  const { values } = parseArgs({ options: { 'server-entry': { type: 'string' } } });
  if (!values['server-entry']) {
    console.error('Provide --server-entry for an existing Windows modeling MCP installation with its matching platform package');
    process.exit(1);
  }
  const project = path.resolve(__dirname, '..');
  build({
    blueprintPath: path.join(project, 'outputs', 'model_definition.json'),
    exportPath: path.join(project, 'reports', 'powerbi', 'F1.SemanticModel', 'definition'),
    evidencePath: path.join(project, 'outputs', 'model_foundation_validation.json'),
    serverPath: path.resolve(values['server-entry']),
  }).then(result => console.log(JSON.stringify({ status: result.status, counts: result.expected_counts })))
    .catch(error => { console.error(error.message); process.exitCode = 1; });
}

module.exports = { build, connect };
