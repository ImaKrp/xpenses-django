import requests
from django.conf import settings


class SupabaseError(Exception):
    pass


def _url(table):
    return f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"


def _headers(schema=None, prefer=None):
    headers = {
        'apikey': settings.SUPABASE_SERVICE_KEY,
        'Authorization': f'Bearer {settings.SUPABASE_SERVICE_KEY}',
        'Content-Type': 'application/json',
    }
    if schema:
        headers['Accept-Profile'] = schema
        headers['Content-Profile'] = schema
    if prefer:
        headers['Prefer'] = prefer
    return headers


def _raise_for_status(response):
    if not response.ok:
        raise SupabaseError(f'{response.status_code} {response.text}')


def select(table, params=None, schema=None):
    response = requests.get(_url(table), headers=_headers(schema), params=params or [])
    _raise_for_status(response)
    return response.json()


def insert(table, data, schema=None):
    response = requests.post(
        _url(table), headers=_headers(schema, prefer='return=representation'), json=data,
    )
    _raise_for_status(response)
    return response.json()


def update(table, params, data, schema=None):
    response = requests.patch(
        _url(table), headers=_headers(schema, prefer='return=representation'), params=params, json=data,
    )
    _raise_for_status(response)
    return response.json()


def delete(table, params, schema=None):
    response = requests.delete(
        _url(table), headers=_headers(schema, prefer='return=representation'), params=params,
    )
    _raise_for_status(response)
    return response.json() if response.content else []


def upsert(table, data, on_conflict, schema=None):
    headers = _headers(schema, prefer='resolution=merge-duplicates,return=representation')
    response = requests.post(f'{_url(table)}?on_conflict={on_conflict}', headers=headers, json=data)
    _raise_for_status(response)
    return response.json()


def rpc(function_name, payload=None):
    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/rpc/{function_name}"
    response = requests.post(url, headers=_headers(), json=payload or {})
    _raise_for_status(response)
    return response.json() if response.content else None


def user_schema(user_id):
    return f'user_{user_id}'
