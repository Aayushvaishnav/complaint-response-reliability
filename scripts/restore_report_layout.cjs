const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { buildDocuments } = require('./build_report.cjs');

function restoreApprovedLayout(backupFolder) {
  const project = path.resolve(__dirname, '..');
  const report = path.join(project, 'reports/powerbi/F1.Report');
  if (fs.existsSync(backupFolder)) throw new Error('Choose a fresh backup folder');
  const documents = buildDocuments();
  const metadata = [
    ['F1.pbip', 'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json'],
    ['F1.Report/definition.pbir', 'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json'],
  ];
  const evidence = { approved_operation: 'Back up the Desktop-saved report and restore the authored layout',
    created_at_utc: new Date().toISOString(), backup_folder: backupFolder, files: [] };
  const backup = (source, relative) => {
    if (!fs.existsSync(source)) return;
    const target = path.join(backupFolder, relative);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(source, target);
    evidence.files.push(relative);
  };
  for (const [name] of documents) backup(path.join(report, name), path.join('F1.Report', name));
  backup(path.join(report, 'build-manifest.json'), 'F1.Report/build-manifest.json');
  for (const [name] of metadata) backup(path.join(project, 'reports/powerbi', name), name);
  for (const [name, content] of documents) fs.writeFileSync(path.join(report, name), content);
  const hashes = Object.fromEntries([...documents].map(([name, content]) =>
    [name, crypto.createHash('sha256').update(content).digest('hex')]));
  fs.writeFileSync(path.join(report, 'build-manifest.json'), JSON.stringify({ files: hashes }, null, 2) + '\n');
  for (const [name, schema] of metadata) {
    const target = path.join(project, 'reports/powerbi', name);
    const value = JSON.parse(fs.readFileSync(target, 'utf8'));
    value.$schema = schema;
    fs.writeFileSync(target, JSON.stringify(value, null, 2) + '\n');
  }
  fs.writeFileSync(path.join(project, 'outputs/report_layout_restore.json'), JSON.stringify(evidence, null, 2) + '\n');
  return evidence;
}

if (require.main === module) {
  if (process.argv[2] !== '--approved' || !process.argv[3]) {
    throw new Error('User approval required; use --approved <fresh-backup-folder>');
  }
  const evidence = restoreApprovedLayout(path.resolve(process.argv[3]));
  console.log(`Preserved ${evidence.files.length} files and restored authored layout`);
}

module.exports = { restoreApprovedLayout };
