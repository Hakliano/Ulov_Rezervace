from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings

from jadro.bunny_client import BunnyStorageClient, BunnyStorageError


@override_settings(
    POSTAK_BUNNY_ENABLED=True,
    POSTAK_BUNNY_STORAGE_ZONE='wwweb',
    POSTAK_BUNNY_ACCESS_KEY='test-key',
    POSTAK_BUNNY_API_BASE='https://storage.bunnycdn.com',
    POSTAK_BUNNY_ROOT_PREFIX='postak/local',
)
class BunnyClientTests(TestCase):
    def test_object_key_omezí_prefix(self):
        c = BunnyStorageClient(
            zone='wwweb',
            access_key='k',
            api_base='https://storage.bunnycdn.com',
            root_prefix='postak/local',
        )
        self.assertEqual(
            c.object_key('private/dokumentace/sdilene/x.pdf'),
            'postak/local/private/dokumentace/sdilene/x.pdf',
        )
        with self.assertRaises(BunnyStorageError):
            c.object_key('../mimo/x.pdf')

    @patch('jadro.bunny_client.urllib.request.urlopen')
    def test_put_get_delete(self, urlopen):
        store = {}

        def fake_urlopen(req, timeout=60):
            method = req.method
            url = req.full_url
            key = url.split('/wwweb/', 1)[-1].split('?')[0]
            resp = MagicMock()
            if method == 'PUT':
                store[key] = req.data
                resp.read.return_value = b''
                resp.__enter__.return_value = resp
                return resp
            if method == 'GET':
                if key not in store:
                    raise FileNotFoundError
                resp.read.return_value = store[key]
                resp.__enter__.return_value = resp
                return resp
            if method == 'DELETE':
                store.pop(key, None)
                resp.read.return_value = b''
                resp.__enter__.return_value = resp
                return resp
            if method == 'HEAD':
                resp.status = 200 if key in store else 404
                resp.__enter__.return_value = resp
                return resp
            raise AssertionError(method)

        urlopen.side_effect = fake_urlopen
        c = BunnyStorageClient(
            zone='wwweb',
            access_key='k',
            api_base='https://storage.bunnycdn.com',
            root_prefix='postak/local',
        )
        c.put('test/a.txt', b'ahoj')
        self.assertEqual(c.get('test/a.txt'), b'ahoj')
        self.assertTrue(c.exists('test/a.txt'))
        c.delete('test/a.txt')
        self.assertFalse(c.exists('test/a.txt'))


class LocalStorageDefaultTests(TestCase):
    def test_ulozeni_lokalne(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        with override_settings(POSTAK_BUNNY_ENABLED=False, MEDIA_ROOT=tmp):
            name = default_storage.save('private/test.txt', ContentFile(b'loc'))
            self.assertTrue(default_storage.exists(name))
            with default_storage.open(name, 'rb') as f:
                self.assertEqual(f.read(), b'loc')
            default_storage.delete(name)
