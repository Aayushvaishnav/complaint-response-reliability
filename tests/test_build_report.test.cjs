const test = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const { buildDocuments } = require('../scripts/build_report.cjs');
const documents = buildDocuments();
const parsed = [...documents].map(([name, text]) => [name, JSON.parse(text)]);
const visuals = parsed.filter(([name]) => name.endsWith('/visual.json')).map(([, value]) => value);
const pages = parsed.filter(([name]) => name.endsWith('/page.json')).map(([, value]) => value);
test('exactly the approved pages and every visual stays within its canvas without overlaps', () => {
  assert.deepEqual(pages.map(p => p.displayName), ['Response Overview', 'Review Priorities']);
  for (const page of pages) {
    const group = visuals.filter(v => v.name.startsWith(page.name + '_'));
    assert(group.length >= 15);
    for (const v of group) {
      const a = v.position;
      assert(a.x >= 32 && a.y >= 24 && a.x + a.width <= page.width - 32 && a.y + a.height <= page.height - 24, v.name);
      for (const other of group) if (other !== v) {
        const b = other.position;
        assert(!(a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y), `${v.name} overlaps ${other.name}`);
      }
    }
  }
});
test('shared slicers have matching native sync groups and hidden identity projections', () => {
  for (const name of ['received_period', 'company', 'product', 'state']) {
    const pair = visuals.filter(v => v.name.endsWith('_' + name));
    assert.equal(pair.length, 2);
    assert.deepEqual(pair[0].visual.syncGroup, pair[1].visual.syncGroup);
    assert.equal(pair[0].visual.syncGroup.filterChanges, true);
    assert.deepEqual(pair[0].visual.query.queryState, pair[1].visual.query.queryState);
    if (name !== 'received_period') assert(pair[0].visual.query.queryState.Values.projections.some(p => p.hidden));
  }
});
test('row focus reaches only evidence and sensitivity, preserving headline universe', () => {
  const page = pages[1];
  const interactions = page.visualInteractions;
  assert.equal(interactions.filter(i => i.type === 'DataFilter').length, 2);
  assert(interactions.filter(i => i.target.includes('_kpi_')).every(i => i.type === 'NoFilter'));
  const chart = visuals.find(v => v.name.endsWith('_monthly_comparison'));
  assert.deepEqual(chart.visual.query.queryState.Y.projections.map(p => p.field.Measure.Property), ['Focused Monthly Untimely Share', 'Focused Monthly Peer Untimely Share']);
  const queue = visuals.find(v => v.name.endsWith('_priority_queue'));
  assert.equal(queue.filterConfig, undefined);
  for (const key of ['Selection Key', 'Company Key', 'Product Key', 'Issue Key']) assert(queue.visual.query.queryState.Values.projections.some(p => p.nativeQueryRef === key && p.hidden));
});
test('bindings match the source model contract instead of an offline export', () => {
  const script = `import json
from model_definition import build_definition
from priority_measures import build_priority_measures
from queue_measures import build_queue_measures
m = build_definition('contract-only')
print(json.dumps({'tables': {t['name']: [c['name'] for c in t['columns']] for t in m['tableDefinitions']}, 'measures': [x['name'] for x in m['measureDefinitions'] + build_priority_measures() + build_queue_measures()]}))`;
  const model = JSON.parse(execFileSync(process.env.F1_PYTHON || 'python', [...JSON.parse(process.env.F1_PYTHON_ARGS || '[]'), '-c', script], { cwd: path.resolve(__dirname, '../scripts'), encoding: 'utf8' }));
  for (const v of visuals) for (const role of Object.values(v.visual.query?.queryState || {})) for (const p of role.projections) {
    const kind = p.field.Measure ? 'Measure' : 'Column';
    const binding = p.field[kind];
    const table = binding.Expression.SourceRef.Entity;
    const names = kind === 'Measure' ? model.measures : model.tables[table];
    assert(names.includes(binding.Property), `${table}[${binding.Property}] missing`);
    assert(p.nativeQueryRef && p.queryRef);
  }
});
test('build is deterministic and defaults to the approved minimum', () => {
  assert.deepEqual([...buildDocuments()], [...documents]);
  const minimum = visuals.find(v => v.name.endsWith('_minimum'));
  assert.equal(minimum.visual.objects.general[0].properties.filter.filter.Where[0].Condition.In.Values[0][0].Literal.Value, '100L');
  assert.equal(visuals.filter(v => v.visual.visualType === 'pageNavigator').length, 2);
});
const properties = entries => entries[0].properties;
const value = expression => expression.expr.Literal.Value;
test('KPI units are unscaled, labels concise and automatic subtitles disabled', () => {
  for (const v of visuals) {
    assert.equal(value(properties(v.visual.visualContainerObjects.subTitle).show), 'false');
    if (v.visual.visualType !== 'cardVisual') continue;
    assert.equal(value(properties(v.visual.objects.value).labelDisplayUnits), '1D');
    for (const p of v.visual.query.queryState.Data.projections) {
      assert(p.nativeQueryRef.length <= 20, p.nativeQueryRef);
      assert.equal(p.displayName, p.nativeQueryRef);
      assert.equal(p.queryRef, 'Complaint Cohorts.' + p.field.Measure.Property);
    }
  }
});
test('context and independent checks use native wrapping text with no totals', () => {
  for (const suffix of ['review_context', 'sensitivity']) {
    const v = visuals.find(v => v.name.endsWith('_' + suffix));
    assert.equal(v.visual.visualType, 'tableEx');
    assert.equal(value(properties(v.visual.objects.total).totals), 'false');
    assert.equal(value(properties(v.visual.objects.values).wordWrap), 'true');
  }
  const context = visuals.find(v => v.name.endsWith('_review_context'));
  assert.equal(context.visual.query.queryState.Values.projections[0].field.Measure.Property, 'Review Context');
  const minimum = visuals.find(v => v.name.endsWith('_minimum'));
  assert(minimum.position.height >= 128);
  assert.equal(value(properties(minimum.visual.objects.items).padding), '2D');
});
test('comparison palette and product axis retain readable identities', () => {
  const chart = visuals.find(v => v.name.endsWith('_monthly_comparison'));
  assert.deepEqual(chart.visual.objects.dataPoint.map(p => value(p.properties.fill.solid.color)), ["'#1B365D'", "'#0F766E'"]);
  const products = visuals.find(v => v.name.endsWith('_product_volume'));
  assert.equal(value(properties(products.visual.objects.categoryAxis).maxMarginFactor), '65D');
});

test('single-series charts use an unselected default color', () => {
  for (const chart of visuals.filter(v => ['lineChart', 'barChart'].includes(v.visual.visualType) && v.visual.query.queryState.Y.projections.length === 1)) {
    assert.equal(chart.visual.objects.dataPoint.length, 1);
    const entry = chart.visual.objects.dataPoint[0];
    assert.equal(entry.selector, undefined);
    assert.equal(entry.properties.fill, undefined);
    assert.equal(value(entry.properties.defaultColor.solid.color), "'#1B365D'");
  }
});

test('priority queue is flat, retains all bindings and excludes hierarchy operations', () => {
  const queue = visuals.find(v => v.name.endsWith('_priority_queue'));
  assert.equal(queue.visual.visualType, 'tableEx');
  assert.deepEqual(Object.keys(queue.visual.query.queryState), ['Values']);
  const projections = queue.visual.query.queryState.Values.projections;
  assert.deepEqual(projections.map(p => p.nativeQueryRef), [
    'Window End', 'Company', 'Product', 'Issue', 'Selection Key', 'Company Key', 'Product Key', 'Issue Key',
    'Priority Rank', 'Elevated months', 'No', 'Known', 'Peer No',
    'Peer known', 'Gap pp', 'Passing minima', 'Review reason'
  ]);
  assert.equal(value(properties(queue.visual.objects.total).totals), 'false');
  assert.equal(queue.visual.objects.rowHeaders, undefined);
  assert.equal(queue.visual.objects.subTotals, undefined);
  assert.equal(queue.visual.objects.columnWidth.length, 13);
  assert.equal(queue.filterConfig, undefined);
  assert(projections.filter(p => p.field.Measure).every(p => p.field.Measure.Property === 'Priority Rank' || p.field.Measure.Property.startsWith('Queue ')));
  assert.deepEqual(queue.visual.query.sortDefinition.sort.map(s => s.direction), ['Ascending', 'Ascending']);
});
test('paired KPIs reserve full-width vertical rows for exact denominator counts', () => {
  const pairs = visuals.filter(v => v.visual.visualType === 'cardVisual' && v.visual.query.queryState.Data.projections.length === 2);
  assert.equal(pairs.length, 3);
  for (const v of pairs) {
    const layout = properties(v.visual.objects.layout);
    assert.equal(value(layout.autoGrid), 'false');
    assert.equal(value(layout.columnCount), '1D');
    assert.equal(value(layout.rowCount), '2D');
    assert.equal(value(properties(v.visual.objects.value).fontSize), '16D');
    assert.equal(value(properties(v.visual.objects.label).show), 'true');
  }
});
