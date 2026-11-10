const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const report = path.join(root, 'reports/powerbi/F1.Report');
const read = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const literal = Value => ({ expr: { Literal: { Value } } });
const str = v => literal(`'${v.replaceAll("'", "''")}'`);
const num = v => literal(`${v}D`);
const bool = v => literal(String(v));
const fill = v => ({ solid: { color: str(v) } });
const entry = (properties, selector) => [{ properties, ...(selector ? { selector } : {}) }];
const selected = p => entry(p, { id: 'default' });
const field = (table, property, kind = 'Measure') => ({ [kind]: { Expression: { SourceRef: { Entity: table } }, Property: property } });
const projection = (t, p, k = 'Measure', hidden = false) => ({ field: field(t, p, k), queryRef: `${t}.${p}`, nativeQueryRef: p, ...(hidden ? { hidden: true } : {}) });
const measureLabels = {
  'Complaint Count': 'Complaints', 'Timely Response Rate': 'Timely rate',
  'Known Flag Count': 'Known flags', 'Untimely No Count': 'Recorded No',
  'Unknown Flag Count': 'Unknown flags', 'Unknown Flag Rate': 'Unknown rate',
  'Median Routing Days': 'Median days', 'Valid Routing Count': 'Valid routes',
  'Eligible Window Count': 'Eligible windows', 'Qualifying Window Count': 'Qualifying windows',
  'Qualifying Segment Count': 'Qualifying segments', 'Stable Window Count': 'Pass all minima',
  'Focused Monthly Untimely Share': 'Segment', 'Focused Monthly Peer Untimely Share': 'Other issues',
  'Queue Elevated Months': 'Elevated months', 'Queue Window No Count': 'No',
  'Queue Window Known Count': 'Known', 'Queue Window Peer No Count': 'Peer No',
  'Queue Window Peer Known Count': 'Peer known', 'Queue Pooled Gap pp': 'Gap pp',
  'Queue Passing Minima': 'Passing minima', 'Queue Review Reason': 'Review reason'
};
const m = p => ({ ...projection('Complaint Cohorts', p), nativeQueryRef: measureLabels[p] || p, displayName: measureLabels[p] || p });
const c = (t, p, hidden = false) => projection(t, p, 'Column', hidden);
const role = projections => ({ projections });
const navy = '#1B365D', teal = '#0F766E';
function buildDocuments() {
  const docs = new Map();
  const put = (p, v) => docs.set(p, `${JSON.stringify(v, null, 2)}\n`);
  const pagesFile = 'definition/pages/pages.json';
  const metadata = read(path.join(report, pagesFile));
  const overview = metadata.pageOrder[0];
  const priorities = 'review_priorities';
  metadata.pageOrder = [overview, priorities]; metadata.activePageName = overview;
  put(pagesFile, metadata);
  const template = read(path.join(report, 'definition/pages', overview, 'page.json'));
  function page(id, displayName) {
    const pageDoc = { ...template, name: id, displayName, width: 1920, height: 1080,
      objects: { background: entry({ color: fill('#F7F9FC'), transparency: num(0) }) }, visualInteractions: [] };
    const visuals = [];
    function visual(name, type, x, y, width, height, title = '') {
      const v = { $schema: 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json', name: `${id}_${name}`,
        position: { x, y, width, height, z: visuals.length, tabOrder: visuals.length }, visual: { visualType: type, objects: {}, visualContainerObjects: {
          background: entry({ show: bool(true), color: fill('#FFFFFF'), transparency: num(0) }),
          title: entry({ show: bool(Boolean(title)), text: str(title), fontFamily: str('Segoe UI'), fontSize: num(13), fontColor: fill(navy) }),
          subTitle: entry({ show: bool(false) }),
          general: entry({ altText: str(title || name.replaceAll('_', ' ')) }),
          padding: selected({ top: num(8), bottom: num(8), left: num(8), right: num(8) })
        } } };
      visuals.push(v); return v;
    }
    const query = (v, state, sort) => { v.visual.query = { queryState: state, ...(sort ? { sortDefinition: { sort, isDefaultSort: false } } : {}) }; };
    function text(name, x, y, w, h, value, size = 15) {
      const v = visual(name, 'textbox', x, y, w, h);
      v.visual.objects.general = entry({ paragraphs: [{ textRuns: [{ value, textStyle: { fontFamily: 'Segoe UI', fontSize: `${size}px`, color: navy } }] }] });
      v.visual.visualContainerObjects.background = entry({ show: bool(false) }); return v;
    }
    function card(name, x, width, measures, title, y = 128, height = 144) {
      const v = visual(name, 'cardVisual', x, y, width, height, title);
      query(v, { Data: role(measures.map(m)) });
      const color = measures[0] === 'Untimely No Count' ? '#B42318' : measures[0] === 'Unknown Flag Count' ? '#64748B' : measures[0] === 'Stable Window Count' ? teal : measures[0].startsWith('Qualifying') ? '#B45309' : navy;
      v.visual.objects = { value: selected({ labelDisplayUnits: num(1), fontSize: num(measures.length > 1 ? 16 : 28), fontColor: fill(color), fontFamily: str('Segoe UI') }), label: selected({ show: bool(true), fontSize: num(12), fontColor: fill(navy) }) };
      if (measures.length > 1) v.visual.objects.layout = selected({ autoGrid: bool(false), columnCount: num(1), rowCount: num(2), cellPadding: num(0), paddingUniform: num(0) });
      return v;
    }
    function slicer(name, y, table, property, mode = 'Dropdown', key) {
      const v = visual(name, 'slicer', 32, y, 264, mode === 'Between' ? 144 : 112);
      query(v, { Values: role([c(table, property), ...(key ? [c(table, key, true)] : [])]) });
      v.visual.objects = { data: entry({ mode: str(mode) }), header: entry({ show: bool(true), text: str(name === 'received_period' ? 'Received period' : property), textSize: num(12), fontColor: fill(navy) }) };
      if (['received_period', 'company', 'product', 'state'].includes(name)) v.visual.syncGroup = { groupName: `F1_${name}`, fieldChanges: true, filterChanges: true };
      if (mode === 'Dropdown') v.visual.objects.general = entry({ selfFilterEnabled: bool(true) });
      return v;
    }
    function chart(name, type, x, y, w, h, category, measures, title, tooltips = []) {
      const v = visual(name, type, x, y, w, h, title);
      query(v, { Category: role(category), Y: role(measures.map(m)), ...(tooltips.length ? { Tooltips: role(tooltips.map(m)) } : {}) }, [{ field: type === 'barChart' ? m(measures[0]).field : category[0].field, direction: type === 'barChart' ? 'Descending' : 'Ascending' }]);
      v.visual.objects.dataPoint = measures.length === 1
        ? entry({ defaultColor: fill(navy) })
        : measures.map((measure, i) => ({ properties: { fill: fill(i ? teal : navy) }, selector: { metadata: `Complaint Cohorts.${measure}` } }));
      if (type === 'barChart') v.visual.objects.categoryAxis = entry({ maxMarginFactor: num(65), fontSize: num(11), showAxisTitle: bool(false) });
      return v;
    }
    function table(name, x, y, w, h, dimensions, measures, title, widths) {
      const v = visual(name, 'pivotTable', x, y, w, h, title);
      query(v, { Rows: role(dimensions), Values: role(measures.map(m)) });
      v.visual.objects = { rowHeaders: entry({ stepped: bool(false), wordWrap: bool(true), fontSize: num(12), repeatRowHeaders: bool(true), autoExpand: bool(true) }),
        values: entry({ fontSize: num(12), wordWrap: bool(true) }),
        columnHeaders: entry({ autoSizeColumnWidth: bool(false), columnAdjustment: str('fixedWidth'), wordWrap: bool(true), fontSize: num(12), fontColor: fill(navy) }),
        columnWidth: [...dimensions, ...measures.map(m)].filter(p => !p.hidden).map((p, i) => ({ selector: { metadata: p.queryRef }, properties: { value: num(widths[i] || 100) } })),
        subTotals: [{ selector: { id: 'Row' }, properties: { rowSubtotals: bool(false) } }, { selector: { id: 'Column' }, properties: { columnSubtotals: bool(false) } }] };
      return v;
    }
    function textTable(name, x, y, w, h, projections, title, widths) {
      const v = visual(name, 'tableEx', x, y, w, h, title);
      query(v, { Values: role(projections) });
      v.visual.objects = {
        total: entry({ totals: bool(false) }),
        values: entry({ fontSize: num(12), wordWrap: bool(true), fontColor: fill(navy) }),
        columnHeaders: entry({ fontSize: num(12), wordWrap: bool(true), autoSizeColumnWidth: bool(false), columnAdjustment: str('fixedWidth') }),
        columnWidth: projections.filter(p => !p.hidden).map((p, i) => ({ selector: { metadata: p.queryRef }, properties: { value: num(widths[i]) } }))
      };
      return v;
    }
    text('title', 32, 24, 1320, 80, displayName === 'Response Overview' ? 'Complaint cohorts show recorded timeliness, not resolution time.' : 'Investigate persistent gaps against same-company other issues.', 29);
    const navigation = visual('navigation', 'pageNavigator', 1392, 32, 496, 64);
    navigation.visual.objects.text = selected({ show: bool(true), fontSize: num(12), fontFamily: str('Segoe UI'), fontColor: fill(navy) });
    slicer('received_period', 128, 'Date', 'Date', 'Between');
    slicer('company', 296, 'Company', 'Company', 'Dropdown', 'Company Key');
    slicer('product', 432, 'Product', 'Product', 'Dropdown', 'Product Key');
    slicer('state', 568, 'Geography', 'State', 'Dropdown', 'Geography Key');
    const api = { pageDoc, visuals, visual, query, text, card, slicer, chart, table, textTable };
    api.finish = () => {
      put(`definition/pages/${id}/page.json`, pageDoc);
      for (const v of visuals) put(`definition/pages/${id}/visuals/${v.name}/visual.json`, v);
    };
    return api;
  }
  const o = page(overview, 'Response Overview');
  [['Complaint Count'], ['Timely Response Rate', 'Known Flag Count'], ['Untimely No Count'], ['Unknown Flag Count', 'Unknown Flag Rate'], ['Median Routing Days', 'Valid Routing Count']].forEach((ms, i) => o.card(`kpi_${i}`, 320 + i * 316, 304, ms, ['Complaints', 'Timely / known', 'Recorded No', 'Unknown flags', 'Routing days / valid'][i]));
  o.chart('monthly_timely', 'lineChart', 320, 296, 936, 360, [c('Date', 'Month Label')], ['Timely Response Rate'], 'Timely response by received month', ['Known Flag Count', 'Untimely No Count', 'Unknown Flag Count']);
  o.chart('product_volume', 'barChart', 1280, 296, 608, 360, [c('Product', 'Product'), c('Product', 'Product Key', true)], ['Complaint Count'], 'Complaint volume by raw product', ['Known Flag Count', 'Untimely No Count', 'Unknown Flag Count']);
  o.table('monthly_audit', 320, 680, 1568, 280, [c('Date', 'Month Label')], ['Complaint Count', 'Known Flag Count', 'Untimely No Count', 'Unknown Flag Count', 'Timely Response Rate', 'Valid Routing Count', 'Median Routing Days'], 'Monthly audit | received cohorts', [160, 180, 170, 170, 170, 190, 190, 190]);
  o.text('metric_notes', 320, 984, 1568, 72, 'Timely = Yes / (Yes + No). Unknown flags stay visible. Routing = sent minus received days. August 2023 breaks longitudinal comparisons. Historical CFPB snapshot; live-export agreement unverified.', 15);
  o.pageDoc.visualInteractions = o.visuals.filter(v => ['lineChart', 'barChart'].includes(v.visual.visualType)).map(v => ({ source: v.name, target: `${overview}_monthly_audit`, type: 'DataFilter' }));
  o.finish();
  const p = page(priorities, 'Review Priorities');
  const minimum = p.slicer('minimum', 704, 'Review Minimum', 'Minimum', 'Basic');
  minimum.position.height = 128;
  minimum.visual.objects.items = entry({ textSize: num(11), padding: num(2) });
  minimum.visual.objects.selection = entry({ strictSingleSelect: bool(true) });
  minimum.visual.objects.general = entry({ filter: { filter: { Version: 2, From: [{ Name: 'm', Entity: 'Review Minimum', Type: 0 }], Where: [{ Condition: { In: { Expressions: [{ Column: { Expression: { SourceRef: { Source: 'm' } }, Property: 'Minimum' } }], Values: [[{ Literal: { Value: '100L' } }]] } } }] } } });
  p.slicer('window_end', 840, 'Review Window', 'Window End');
  ['Eligible Window Count', 'Qualifying Window Count', 'Qualifying Segment Count', 'Stable Window Count'].forEach((ms, i) => p.card(`kpi_${i}`, 320 + i * 396, 380, [ms], ['Eligible windows', 'Qualifying windows', 'Qualifying segments', 'Pass all minima'][i]));
  const evidence = p.chart('monthly_comparison', 'lineChart', 320, 296, 936, 232, [c('Date', 'Month Label')], ['Focused Monthly Untimely Share', 'Focused Monthly Peer Untimely Share'], 'Focused window | segment and same-company other issues', ['Focused Monthly Complaint Count', 'Focused Monthly No Count', 'Focused Monthly Known Count', 'Focused Monthly Peer No Count', 'Focused Monthly Peer Known Count']);
  p.text('focus_instruction', 320, 536, 936, 40, 'Select one queue row to inspect its three months. Clear the selection to reset.', 15);
  const sensitivity = p.textTable('sensitivity', 1280, 296, 608, 280, [c('Sensitivity Minimum', 'Minimum'), m('Sensitivity Result'), m('Sensitivity Reason')], 'Focused window | independent minimum checks', [80, 120, 360]);
  const queue = p.textTable('priority_queue', 320, 600, 1568, 336,
    [c('Review Selection', 'Window End'), c('Review Selection', 'Company'), c('Review Selection', 'Product'), c('Review Selection', 'Issue'), ...['Selection Key', 'Company Key', 'Product Key', 'Issue Key'].map(k => c('Review Selection', k, true)),
    ...['Priority Rank', 'Queue Elevated Months', 'Queue Window No Count', 'Queue Window Known Count', 'Queue Window Peer No Count', 'Queue Window Peer Known Count', 'Queue Pooled Gap pp', 'Queue Passing Minima', 'Queue Review Reason'].map(m)],
    'Review queue | ranks are separate within each ending month; scroll for supporting fields', [105, 250, 240, 300, 75, 85, 90, 100, 100, 110, 100, 120, 300]);
  queue.visual.query.sortDefinition = { sort: [{ field: c('Review Selection', 'Window End').field, direction: 'Ascending' }, { field: m('Priority Rank').field, direction: 'Ascending' }], isDefaultSort: false };
  p.text('empty_queue_note', 32, 976, 264, 80, 'An empty queue means no window passes this screen, instead of proven reliable service.', 14);
  p.textTable('review_context', 320, 960, 1568, 96, [m('Review Context')], '', [1520]);
  p.pageDoc.visualInteractions = p.visuals.filter(v => v.name !== queue.name).map(v => ({ source: queue.name, target: v.name, type: [evidence.name, sensitivity.name].includes(v.name) ? 'DataFilter' : 'NoFilter' }));
  p.finish();
  return docs;
}
function build() {
  const docs = buildDocuments();
  const manifestPath = path.join(report, 'build-manifest.json');
  const previous = fs.existsSync(manifestPath) ? read(manifestPath).files : {};
  const hash = text => crypto.createHash('sha256').update(text).digest('hex');
  for (const [name, content] of docs) {
    const target = path.join(report, name);
    if (fs.existsSync(target) && previous[name] && hash(fs.readFileSync(target)) !== previous[name] && fs.readFileSync(target, 'utf8') !== content) throw new Error(`Manual edit preserved: ${name}`);
    if (fs.existsSync(target) && !previous[name] && !['definition/pages/pages.json'].includes(name) && !name.endsWith('/page.json') && fs.readFileSync(target, 'utf8') !== content) throw new Error(`Unowned file preserved: ${name}`);
  }
  for (const [name, content] of docs) { const target = path.join(report, name); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, content); }
  fs.writeFileSync(manifestPath, JSON.stringify({ files: Object.fromEntries([...docs].map(([name, content]) => [name, hash(content)])) }, null, 2) + '\n');
  console.log(`Built ${docs.size} report definitions; Desktop acceptance pending`);
}
module.exports = { buildDocuments, build };
if (require.main === module) build();
