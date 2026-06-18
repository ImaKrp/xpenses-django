import requests
from django.conf import settings
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class SupabaseStorage(Storage):
    def __init__(self, base_url=None, bucket=None, service_key=None):
        self.base_url = (base_url or settings.SUPABASE_URL).rstrip('/')
        self.bucket = bucket or settings.SUPABASE_STORAGE_BUCKET
        self.service_key = service_key or settings.SUPABASE_SERVICE_KEY

    def _object_url(self, name):
        return f'{self.base_url}/storage/v1/object/{self.bucket}/{name}'

    def _headers(self, content_type='application/octet-stream'):
        return {
            'Authorization': f'Bearer {self.service_key}',
            'apikey': self.service_key,
            'Content-Type': content_type,
            'x-upsert': 'true',
        }

    def _save(self, name, content):
        content_type = getattr(content, 'content_type', None) or 'application/octet-stream'
        response = requests.post(
            self._object_url(name),
            headers=self._headers(content_type),
            data=content.read(),
        )
        response.raise_for_status()
        return name

    def get_available_name(self, name, max_length=None):
        return name

    def exists(self, name):
        response = requests.head(self._object_url(name), headers=self._headers())
        return response.status_code == 200

    def delete(self, name):
        requests.delete(self._object_url(name), headers=self._headers())

    def size(self, name):
        response = requests.head(self._object_url(name), headers=self._headers())
        return int(response.headers.get('content-length', 0))

    def url(self, name):
        return f'{self.base_url}/storage/v1/object/public/{self.bucket}/{name}'
