"""Offline foundation blueprint; no model writes or priority/window implementation.

Microsoft references: learn.microsoft.com/en-us/power-query/connectors/parquet,
learn.microsoft.com/en-us/powerquery-m/table-transformcolumntypes and
learn.microsoft.com/en-us/dax/removefilters-function-dax.
"""


def _field(source, name, kind='String', hidden=False):
    field = dict(name=name, sourceColumn=source, dataType=kind, isHidden=hidden,
                 summarizeBy='None', description=f'Imported {source}; preserves projection identity and meaning.')
    if kind == 'DateTime':
        field['formatString'] = 'yyyy-MM-dd'
    return field


def _table(name, filename, columns, description):
    types = {'String': 'type text', 'Int64': 'Int64.Type',
             'DateTime': 'type date', 'Boolean': 'type logical'}
    transforms = ', '.join('{"' + c['sourceColumn'] + '", ' + types[c['dataType']] + '}'
                           for c in columns)
    expression = ('let\n    Source = Parquet.Document(File.Contents(#"Source Folder" & "/'
                  + filename + '.parquet")),\n    Typed = Table.TransformColumnTypes(Source, {'
                  + transforms + '})\nin\n    Typed')
    return dict(name=name, description=description, columns=columns,
                partitionName=name, mode='Import', mExpression=expression)


def build_definition(source_folder: str) -> dict:
    """Return fresh MCP Create definitions; source_folder is a literal M parameter value."""
    if not isinstance(source_folder, str) or not source_folder.strip():
        raise ValueError('source_folder must be a nonempty folder string')
    f = _field
    cohorts = [f('received_date', 'Received Date', 'DateTime', True)]
    cohorts += [f(x + '_key', x.title() + ' Key', 'Int64', True)
                for x in ('company', 'product', 'issue', 'geography')]
    cohorts += [f('routing_status', 'Routing Status', hidden=True),
                f('routing_days', 'Routing Days', 'Int64', True)]
    cohorts += [f(x + '_rows', x.title() + ' Rows', 'Int64', True)
                for x in ('complaint', 'yes', 'no', 'unknown')]
    tables = [_table('Complaint Cohorts', 'complaint_cohorts', cohorts,
                     'Observed received-day/category/routing-lag bins; counts are frequencies, not complaints per row.')]
    dates = [f('date', 'Date', 'DateTime'), f('year', 'Year', 'Int64'),
             f('month_start', 'Month Start', 'DateTime'), f('month_label', 'Month Label'),
             f('month_order', 'Month Order', 'Int64', True), f('timing_era', 'Timing Era'),
             f('boundary_month', 'Boundary Month', 'Boolean')]
    dates[3]['sortByColumn'] = 'Month Order'
    tables.append(_table('Date', 'date', dates, 'Contiguous received-date calendar, 2023 through 2025.'))
    tables[-1]['dataCategory'] = 'Time'
    for dimension in ('Company', 'Product', 'Issue', 'Geography'):
        label = 'State' if dimension == 'Geography' else dimension
        columns = [f(dimension.lower() + '_key', dimension + ' Key', 'Int64', True),
                   f('raw_value', 'Raw Value', hidden=True),
                   f('is_missing', 'Is Missing', 'Boolean', True),
                   f('missingness', 'Missingness', hidden=True), f('display_label', label)]
        columns[-1]['groupByColumns'] = [dimension + ' Key']
        columns[-1]['description'] = ('Display label grouped by integer identity; VertiPaq may normalize case; '
                                      'SQL raw preservation is authoritative and identities must not merge.')
        if dimension == 'Geography':
            columns[-1]['dataCategory'] = 'StateOrProvince'
        tables.append(_table(dimension, dimension.lower(), columns,
                             'One raw source identity; SQL null, empty and literal labels have distinct keys.'))
    for name in ('Review Minimum', 'Sensitivity Minimum'):
        tables.append(_table(name, name.lower().replace(' ', '_'),
                             [f('minimum', 'Minimum', 'Int64')],
                             'Disconnected analyst minimum choices: 50, 100, 200; foundation has no selection measures.'))
    window = [f('window_end', 'Window End', 'DateTime'), f('window_label', 'Window Label'),
              f('month_order', 'Month Order', 'Int64', True)]
    window[1]['sortByColumn'] = 'Month Order'
    tables.append(_table('Review Window', 'review_window', window,
                         'Disconnected potential ending months; does not filter received dates.'))
    selection = [f(x + '_key', x.title() + ' Key', 'Int64', True)
                 for x in ('selection', 'segment', 'company', 'product', 'issue')]
    selection += [f('window_end', 'Window End', 'DateTime')]
    for x in ('company', 'product', 'issue'):
        selection += [f(x + '_raw', x.title() + ' Raw', hidden=True),
                      f(x, x.title()), f(x + '_missingness', x.title() + ' Missingness', hidden=True)]
        selection[-2]['groupByColumns'] = [x.title() + ' Key']
        selection[-2]['description'] = ('Selector label grouped by tuple key; case-normalized display is not raw identity.')
    tables.append(_table('Review Selection', 'review_selection', selection,
                         'Disconnected observed company/product/issue/month selectors; integer identities never derive from display labels.'))
    relationships = []
    for dimension in ('Date', 'Company', 'Product', 'Issue', 'Geography'):
        relationships.append(dict(name='Complaint Cohorts to ' + dimension,
                                  fromTable='Complaint Cohorts',
                                  fromColumn='Received Date' if dimension == 'Date' else dimension + ' Key',
                                  toTable=dimension,
                                  toColumn='Date' if dimension == 'Date' else dimension + ' Key',
                                  fromCardinality='Many', toCardinality='One',
                                  crossFilteringBehavior='OneDirection', isActive=True))
    measures = []

    def measure(name, expression, description, folder='Counts', format_string='#,##0'):
        measures.append(dict(tableName='Complaint Cohorts', name=name, expression=expression,
                             description=description, displayFolder=folder,
                             formatString=format_string, isHidden=False))

    for name, column in [('Complaint Count', 'Complaint'), ('Timely Yes Count', 'Yes'),
                         ('Untimely No Count', 'No'), ('Unknown Flag Count', 'Unknown')]:
        measure(name, f"COALESCE(SUM('Complaint Cohorts'[{column} Rows]), 0)",
                'Sum imported complaint frequencies in current context; empty is zero.')
    measure('Known Flag Count', '[Timely Yes Count] + [Untimely No Count]',
            'Exact recorded Yes plus No flags; excludes unknown flags.')
    for name, numerator, denominator in [('Timely Response Rate', 'Timely Yes Count', 'Known Flag Count'),
                                         ('Untimely Share', 'Untimely No Count', 'Known Flag Count'),
                                         ('Unknown Flag Rate', 'Unknown Flag Count', 'Complaint Count')]:
        measure(name, f'DIVIDE([{numerator}], [{denominator}])',
                f'{numerator} divided by {denominator}; undefined is BLANK.', 'Rates', '0.00%')
    measure('Valid Routing Count', '''CALCULATE([Complaint Count], KEEPFILTERS('Complaint Cohorts'[Routing Status] = "valid"))''',
            'Frequency of nonnegative valid routing lags.', 'Routing')
    measure('Invalid Routing Count', '[Complaint Count] - [Valid Routing Count]',
            'All complaints minus valid routing frequencies; includes missing and negative lags.', 'Routing')
    measure('Median Routing Days', '''VAR _bins =
    CALCULATETABLE(
        ADDCOLUMNS(VALUES('Complaint Cohorts'[Routing Days]),
            "__frequency", CALCULATE(SUM('Complaint Cohorts'[Complaint Rows]))),
        KEEPFILTERS('Complaint Cohorts'[Routing Status] = "valid"),
        KEEPFILTERS(NOT ISBLANK('Complaint Cohorts'[Routing Days])),
        KEEPFILTERS('Complaint Cohorts'[Routing Days] >= 0))
VAR _total = SUMX(_bins, [__frequency])
VAR _lowerPosition = INT(DIVIDE(_total + 1, 2))
VAR _upperPosition = INT(DIVIDE(_total + 2, 2))
VAR _cumulative = ADDCOLUMNS(_bins, "__cumulative",
    VAR _day = 'Complaint Cohorts'[Routing Days]
    RETURN SUMX(FILTER(_bins, 'Complaint Cohorts'[Routing Days] <= _day), [__frequency]))
VAR _lower = MINX(FILTER(_cumulative, [__cumulative] >= _lowerPosition), 'Complaint Cohorts'[Routing Days])
VAR _upper = MINX(FILTER(_cumulative, [__cumulative] >= _upperPosition), 'Complaint Cohorts'[Routing Days])
RETURN IF(_total > 0, DIVIDE(_lower + _upper, 2), BLANK())''',
            'Frequency-weighted median of valid lags; averages both middle observations; empty is BLANK.',
            'Routing', '#,##0.0')
    measure('Monthly Issue Share', "DIVIDE([Complaint Count], CALCULATE([Complaint Count], REMOVEFILTERS('Issue')))",
            'Issue frequency divided by all issues in current month context; all other filters retained; undefined is BLANK.',
            'Issue Mix', '0.00%')
    for name, base in [('Peer Complaint Count', 'Complaint Count'),
                       ('Peer Known Count', 'Known Flag Count'), ('Peer No Count', 'Untimely No Count')]:
        measure(name, f"CALCULATE([{base}], REMOVEFILTERS('Issue')) - [{base}]",
                'Other issues: all-issue total minus current issue selection; company, product, date and geography retained.', 'Peers')
    measure('Peer Untimely Share', 'DIVIDE([Peer No Count], [Peer Known Count])',
            'Other-issue No flags divided by other-issue known flags; undefined is BLANK.', 'Peers', '0.00%')
    # Escape M escape introducers before inserting control-character escapes
    literal = source_folder.replace('#(', '#(#)(').replace('"', '""').replace('\r', '#(cr)').replace('\n', '#(lf)').replace('\t', '#(tab)')
    return dict(status='foundation_only', tableDefinitions=tables,
                relationshipDefinitions=relationships, measureDefinitions=measures,
                parameterDefinition=dict(name='Source Folder', kind='M',
                    expression='"' + literal + '" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                    description='Single local folder containing validated Parquet projections.'),
                 modelDefinition=dict(name='F1', culture='en-US', sourceQueryCulture='en-US',
                     discourageImplicitMeasures=True, defaultMode='Import',
                     annotations=[dict(key='__PBI_TimeIntelligenceEnabled', value='0')]))


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-folder', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_definition(args.source_folder), indent=2) + '\n', encoding='utf-8')
