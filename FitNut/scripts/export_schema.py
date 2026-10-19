"""Export table metadata only, using the same MySQL connection as the app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from db import fetch_all

TABLES = ('users', 'sessions', 'user_profiles', 'meal_types', 'eating_events',
          'units_of_measure', 'food_catalog', 'food_entries', 'activity_types', 'activity_events', 'sleep_logs')


def metadata(sql, values):
    return [{key.lower(): value for key, value in row.items()} for row in fetch_all(sql, values)]


def export():
    lines = ['# Database tables', '',
        'Tables used by the app. Refresh with `scripts/export_schema.py` after running setup.', '',
        'PK = primary key; FK = foreign key. Dates are stored in UTC. NULL means no value was entered.', '']
    with app.app_context():
        for table in TABLES:
            columns = metadata('''SELECT column_name,column_type,is_nullable,column_default,column_key,extra
                FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position''', (table,))
            if not columns:
                raise RuntimeError('Initialize the database first. Missing table: ' + table)
            foreign = metadata('''SELECT k.column_name,k.referenced_table_name,k.referenced_column_name,r.delete_rule
                FROM information_schema.key_column_usage k JOIN information_schema.referential_constraints r
                ON r.constraint_schema=k.constraint_schema AND r.constraint_name=k.constraint_name
                WHERE k.table_schema=DATABASE() AND k.table_name=%s AND k.referenced_table_name IS NOT NULL''', (table,))
            fks = {row['column_name']: row for row in foreign}
            lines.extend(['## ' + table, '', '| Column | MySQL type | Nullable | Key / relationship | Default / extra |',
                          '| --- | --- | --- | --- | --- |'])
            for column in columns:
                name = column['column_name']
                keys = {'PRI': 'PK', 'UNI': 'UNIQUE'}.get(column['column_key'], '')
                if name in fks:
                    fk = fks[name]
                    keys += ('; ' if keys else '') + f"FK → `{fk['referenced_table_name']}.{fk['referenced_column_name']}`; delete {fk['delete_rule']}"
                default = column['column_default']
                default = 'NULL' if default is None and column['is_nullable'] == 'YES' else '—' if default is None else str(default)
                if column['extra']:
                    default += '; ' + column['extra']
                lines.append(f"| `{name}` | `{column['column_type']}` | {column['is_nullable']} | {keys or '—'} | {default} |")
            indexes = metadata('''SELECT index_name,GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns_list,
                MIN(non_unique) AS non_unique FROM information_schema.statistics
                WHERE table_schema=DATABASE() AND table_name=%s GROUP BY index_name ORDER BY index_name''', (table,))
            lines.extend(['', 'Indexes: ' + '; '.join('`' + row['index_name'] + '` (' + row['columns_list'] + ')' +
                (' UNIQUE' if not row['non_unique'] else '') for row in indexes) + '.', ''])
            checks = metadata('''SELECT c.constraint_name,c.check_clause FROM information_schema.check_constraints c
                JOIN information_schema.table_constraints t ON t.constraint_schema=c.constraint_schema
                AND t.constraint_name=c.constraint_name WHERE t.table_schema=DATABASE() AND t.table_name=%s
                ORDER BY c.constraint_name''', (table,))
            for check in checks:
                lines.append('- `' + check['constraint_name'] + '`: ``' + check['check_clause'] + '``')
            if checks:
                lines.append('')
    target = Path(__file__).resolve().parents[1] / 'database' / 'SCHEMA.md'
    target.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    print('Updated database/SCHEMA.md (metadata only).')


if __name__ == '__main__':
    export()
