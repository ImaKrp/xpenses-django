import datetime
from decimal import Decimal

from . import supabase_client as sb


def _to_decimal(value):
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def _to_date(value):
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(value)


def _with_pk(row):
    if row is not None:
        row['pk'] = row.get('id')
    return row


def list_default_categories():
    rows = sb.select('categories', [('type', 'eq.default'), ('order', 'name.asc')], schema='public')
    return [_with_pk(r) for r in rows]


def list_custom_categories(schema):
    rows = sb.select('categories', [('type', 'eq.custom'), ('order', 'id.desc')], schema=schema)
    return [_with_pk(r) for r in rows]


def list_categories(schema):
    return list_default_categories() + list_custom_categories(schema)


def _category_lookup(schema):
    rows = list_default_categories() + list_custom_categories(schema)
    return {row['id']: row for row in rows}


def create_category(schema, data):
    payload = {**data, 'type': 'custom'}
    rows = sb.insert('categories', payload, schema=schema)
    return _with_pk(rows[0])


def get_custom_category(schema, pk):
    rows = sb.select('categories', [('id', f'eq.{pk}'), ('type', 'eq.custom')], schema=schema)
    return _with_pk(rows[0]) if rows else None


def delete_category(schema, pk):
    sb.delete('categories', [('id', f'eq.{pk}'), ('type', 'eq.custom')], schema=schema)


def _hydrate_transaction(row, category_lookup):
    row = dict(row)
    _with_pk(row)
    row['value'] = _to_decimal(row.get('value'))
    row['date'] = _to_date(row.get('date'))
    row['category'] = category_lookup.get(row.get('category_id'))
    return row


def list_transactions(schema, date_from=None, date_to=None, title=None, category_id=None, type=None):
    params = [('order', 'date.desc,title.asc')]
    if date_from:
        params.append(('date', f'gte.{date_from.isoformat()}'))
    if date_to:
        params.append(('date', f'lte.{date_to.isoformat()}'))
    if title:
        params.append(('title', f'ilike.*{title}*'))
    if category_id:
        params.append(('category_id', f'eq.{category_id}'))
    if type:
        params.append(('type', f'eq.{type}'))

    rows = sb.select('transactions', params, schema=schema)
    lookup = _category_lookup(schema)
    return [_hydrate_transaction(r, lookup) for r in rows]


def get_transaction(schema, pk):
    rows = sb.select('transactions', [('id', f'eq.{pk}')], schema=schema)
    if not rows:
        return None
    lookup = _category_lookup(schema)
    return _hydrate_transaction(rows[0], lookup)


def _serialize_transaction(data):
    payload = dict(data)
    if isinstance(payload.get('value'), Decimal):
        payload['value'] = str(payload['value'])
    if isinstance(payload.get('date'), datetime.date):
        payload['date'] = payload['date'].isoformat()
    return payload


def create_transaction(schema, data):
    rows = sb.insert('transactions', _serialize_transaction(data), schema=schema)
    lookup = _category_lookup(schema)
    return _hydrate_transaction(rows[0], lookup)


def update_transaction(schema, pk, data):
    rows = sb.update('transactions', [('id', f'eq.{pk}')], _serialize_transaction(data), schema=schema)
    if not rows:
        return None
    lookup = _category_lookup(schema)
    return _hydrate_transaction(rows[0], lookup)


def delete_transaction(schema, pk):
    sb.delete('transactions', [('id', f'eq.{pk}')], schema=schema)


def get_profile(schema):
    rows = sb.select('profiles', [('limit', '1')], schema=schema)
    return _with_pk(rows[0]) if rows else None


def upsert_profile(schema, data):
    rows = sb.upsert('profiles', data, on_conflict='user_id', schema=schema)
    return _with_pk(rows[0])


def upsert_insight_snapshot(schema, data):
    rows = sb.upsert('insight_snapshots', data, on_conflict='year,month', schema=schema)
    return rows[0] if rows else None


def list_insight_snapshots(schema, exclude_year=None, exclude_month=None):
    rows = sb.select('insight_snapshots', [('order', 'year.desc,month.desc')], schema=schema)
    if exclude_year is not None and exclude_month is not None:
        rows = [r for r in rows if not (r['year'] == exclude_year and r['month'] == exclude_month)]
    return rows
