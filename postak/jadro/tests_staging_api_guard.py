from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from jadro.staging_api_guard import assert_staging_crm_targets, block_live_crm_write


class StagingApiGuardTests(SimpleTestCase):
    @override_settings(
        POSTAK_STAGING_MODE=True,
        MODERNIK_API_BASE='https://api-staging.ulovklienty.cz/partner-admin/api/postak/v1',
        HYA_API_BASE='https://staging.hereyouare.cz/internal/postak/v1',
    )
    def test_staging_urls_ok(self):
        assert_staging_crm_targets()

    @override_settings(
        POSTAK_STAGING_MODE=True,
        MODERNIK_API_BASE='https://api.ulovklienty.cz/partner-admin/api/postak/v1',
        HYA_API_BASE='https://staging.hereyouare.cz/internal/postak/v1',
    )
    def test_live_modernik_base_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            assert_staging_crm_targets()

    @override_settings(POSTAK_STAGING_MODE=True)
    def test_block_write_before_http(self):
        with self.assertRaises(ImproperlyConfigured):
            block_live_crm_write(
                'POST',
                'https://api.ulovklienty.cz/partner-admin/api/postak/v1',
                kind='modernik',
            )
        block_live_crm_write(
            'GET',
            'https://api.ulovklienty.cz/partner-admin/api/postak/v1',
            kind='modernik',
        )

    @override_settings(POSTAK_STAGING_MODE=False)
    def test_live_write_allowed_when_not_staging_mode(self):
        block_live_crm_write(
            'POST',
            'https://api.ulovklienty.cz/partner-admin/api/postak/v1',
            kind='modernik',
        )