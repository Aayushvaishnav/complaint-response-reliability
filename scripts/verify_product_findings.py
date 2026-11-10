"""Independently reconcile product headline counts directly from the frozen CSV."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from population_analysis import fingerprint, require

PROJECT = Path(__file__).resolve().parents[1]


def product_counts(handle):
    reader = csv.DictReader(handle)
    require(reader.fieldnames is not None and {'Product', 'Timely response?'} <= set(reader.fieldnames), 'Required product/flag columns missing')
    counts = defaultdict(Counter)
    for row in reader:
        flag = row['Timely response?']
        counts[row['Product']][flag if flag in ('Yes', 'No') else 'Unknown'] += 1
    return {product: dict(complaints=sum(flags.values()), timely=flags['Yes'], untimely=flags['No'],
                          known=flags['Yes']+flags['No'], unknown=flags['Unknown'])
            for product, flags in counts.items()}


def run(project=PROJECT):
    evidence = dict(status='failed', checked_at_utc=datetime.now(timezone.utc).isoformat())
    try:
        accepted = json.loads((project / 'outputs/gate_b_acceptance.json').read_text())
        relative = 'data/processed/complaints_2023_2025.csv'
        require(accepted['status'] == 'passed', 'Gate B not accepted')
        evidence['scoped_csv_sha256'] = fingerprint(project / relative)
        require(evidence['scoped_csv_sha256'] == accepted['artifact_sha256'][relative], 'Scoped CSV identity changed')
        with (project / relative).open(encoding='utf-8-sig', newline='') as handle:
            independent = product_counts(handle)
        with (project / 'outputs/product_overview.csv').open(encoding='utf-8', newline='') as handle:
            actual = {r['product']: {k: int(r[k]) for k in ('complaints', 'timely', 'untimely', 'known', 'unknown')}
                      for r in csv.DictReader(handle)}
        require(independent == actual, 'Independent CSV product metrics disagree')
        evidence.update(products=independent, rows=sum(r['complaints'] for r in independent.values()),
                        product_overview_sha256=fingerprint(project / 'outputs/product_overview.csv'),
                        implementation_sha256=fingerprint(project / 'scripts/verify_product_findings.py'),
                        status='passed')
    except Exception as error:
        evidence['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        (project / 'outputs/product_reference_validation.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    run()
