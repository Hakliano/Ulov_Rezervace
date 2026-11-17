import os
import unittest

from django.test import TestCase

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore

from jadro.sync_lock import SyncAlreadyRunning, sync_file_lock


@unittest.skipUnless(fcntl, 'fcntl not available on this platform')
class SyncLockTests(TestCase):
    def test_druhy_zamek_zablokuje(self):
        lock_dir = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'postak-sync-test-locks')
        os.environ['POSTAK_SYNC_LOCK_DIR'] = lock_dir
        with sync_file_lock('test'):
            with self.assertRaises(SyncAlreadyRunning):
                with sync_file_lock('test'):
                    pass