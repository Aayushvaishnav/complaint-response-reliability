"""Record publisher documentation, user-confirmed provenance and live-access limits."""

import argparse
import ast
import hashlib
import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from validate_source import COLUMNS, PROJECT, fingerprint


COMMIT = '9bf8c3e8b013d846394dd285bb49470a23ead628'
REPOSITORY = f'https://raw.githubusercontent.com/cfpb/ccdb5-api/{COMMIT}/'
REFERENCES = {
    'publisher_headers': REPOSITORY + 'complaint_search/defaults.py',
    'publisher_readme': REPOSITORY + 'README.md',
    'field_dictionary': 'https://cfpb.github.io/api/ccdb/fields.html',
    'database_overview': 'https://cfpb.github.io/api/ccdb/',
    'publisher_release_notes': 'https://raw.githubusercontent.com/cfpb/api/gh-pages/ccdb/release-notes.md',
    'reuse_statement': 'https://files.consumerfinance.gov/f/documents/cfpb_finex-consumer-complaints-webinar_slides_2022-11.pdf',
    'category_options': 'https://files.consumerfinance.gov/f/documents/cfpb_consumer_complaint_form_product_issue_options_August_2023_FINAL.pdf',
    'database_landing': 'https://www.consumerfinance.gov/data-research/consumer-complaints/',
    'live_record': 'https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/8317937',
}


def publisher_headers(text):
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == 'CSV_ORDERED_HEADERS'
                for target in node.targets):
            value = node.value
            if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id == 'OrderedDict' and len(value.args) == 1
                    and not value.keywords):
                raise ValueError('Unexpected publisher header declaration')
            pairs = ast.literal_eval(value.args[0])
            if not isinstance(pairs, list) or not all(
                    isinstance(pair, tuple) and len(pair) == 2
                    and all(isinstance(item, str) for item in pair) for pair in pairs):
                raise ValueError('Publisher headers are not literal string pairs')
            return [label for _, label in pairs]
    raise ValueError('Publisher CSV header declaration not found')


def fetch_reference(name, url, directory):
    request = Request(url, headers={'User-Agent': 'F1-portfolio-source-verification/1.0'})
    try:
        with urlopen(request) as response:
            body = response.read()
            status = response.status
    except HTTPError as error:
        return {'url': url, 'status': 'http_error', 'http_status': error.code}
    suffix = '.pdf' if url.endswith('.pdf') else '.txt'
    destination = directory / (name + suffix)
    destination.write_bytes(body)
    return {'url': url, 'status': 'retrieved', 'http_status': status,
            'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
            'saved_name': destination.name}


def pdf_text(path):
    destination = path.with_suffix('.extracted.txt')
    subprocess.run(['pdftotext', '-layout', str(path), str(destination)], check=True)
    return ' '.join(destination.read_text(encoding='utf-8').split())


def validate_reviewed_excerpt(evidence, source_url, expected_text):
    if evidence['evidence_type'] != 'reviewed_official_domain_search_excerpt':
        raise ValueError('Unsupported reviewed publisher-evidence type')
    date.fromisoformat(evidence['reviewed_on'])
    if evidence['source_url'] != source_url or expected_text not in evidence['quote']:
        raise ValueError('Reviewed excerpt does not substantiate the required publisher statement')
    return {'method': 'manually_reviewed_official_search_excerpt', **evidence}


def run(project):
    config = json.loads((project / 'config/source.json').read_text(encoding='utf-8'))
    reviewed = json.loads((project / 'config/publisher_evidence.json').read_text(encoding='utf-8'))
    directory = project / 'data/raw/verification'
    directory.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, url in REFERENCES.items():
        print(f'Checking {name}', flush=True)
        results[name] = fetch_reference(name, url, directory)
    checks = {
        'user_confirmed_official_origin': config['provenance']['origin_state']
            == 'user_confirmed_official_cfpb_download',
        'raw_hash_matches_frozen_identity': fingerprint(project / config['raw_snapshot'])
            == config['source_sha256'],
        'publisher_header_matches_supplied_schema': False,
        'publisher_field_dictionary_accessible': results['field_dictionary']['status'] == 'retrieved',
        'publisher_public_reuse_statement_supported': False,
        'historical_category_boundary_supported': False,
    }
    if results['publisher_headers']['status'] == 'retrieved':
        text = (directory / results['publisher_headers']['saved_name']).read_text(encoding='utf-8')
        checks['publisher_header_matches_supplied_schema'] = publisher_headers(text) == COLUMNS
    statement_evidence = {}
    for name, reviewed_key, check_name, phrase in [
        ('reuse_statement', 'public_reuse', 'publisher_public_reuse_statement_supported',
         'All complaint data we publish is freely available for anyone to use, analyze, and build on.'),
        ('category_options', 'taxonomy_boundary', 'historical_category_boundary_supported', 'August 24, 2023'),
    ]:
        if results[name]['status'] == 'retrieved':
            text = pdf_text(directory / results[name]['saved_name'])
            checks[check_name] = phrase in text
            statement_evidence[name] = {'method': 'retrieved_pdf_text', 'statement_found': checks[check_name]}
        else:
            print(f'{name}: direct retrieval blocked; checking explicitly recorded, reviewed publisher-search evidence', flush=True)
            statement_evidence[name] = validate_reviewed_excerpt(reviewed[reviewed_key], REFERENCES[name], phrase)
            checks[check_name] = True
    passed = all(checks.values())
    report = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'passed_with_documented_limits' if passed else 'blocked',
        'required_checks': checks, 'references': results,
        'publisher_statement_evidence': statement_evidence,
        'publisher_source_commit': COMMIT,
        'local_snapshot_sha256': config['source_sha256'],
        'provenance': config['provenance'],
        'acceptance_basis': 'User-mediated official download, frozen local identity, publisher schema/dictionary and explicit public-reuse statement',
        'live_record_comparison': 'not_performed',
        'limits': [
            'Original download URL and date were not recorded; official origin is user-confirmed',
            'No byte comparison with a newly downloaded complete official export',
            'GitHub Pages field documentation is corroborated by pinned publisher CSV headers; API README warns older documentation is not updated',
            'Published timely-response flag is used as recorded; no operational deadline or resolution duration is inferred',
            'Public-reuse and August-2023 effective-date statements may use explicitly recorded official search excerpts; blocked PDFs are not claimed as downloaded or read',
            'No current data-use-policy page was retrieved; API software CC0 terms are not asserted as a dataset-wide licence',
        ],
    }
    outputs = project / 'outputs'
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / 'source_access_verification.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)
    if not passed:
        raise ValueError('Required publisher/source verification checks failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=PROJECT)
    run(parser.parse_args().project.resolve())
