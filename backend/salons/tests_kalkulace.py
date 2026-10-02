from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase, RequestFactory

from rest_framework.exceptions import Throttled as DrfThrottled

from rezervace.throttles import KalkulaceRateThrottle, PoptavkaRateThrottle
from salons.kalkulace import compute_price, format_email_body, parse_and_compute, web_monthly
from salons.views import KalkulaceView


class KalkulaceAlgorithmTests(SimpleTestCase):
    def test_web_monthly_examples(self):
        self.assertEqual(web_monthly(3), 0)
        self.assertEqual(web_monthly(4), 0)
        self.assertEqual(web_monthly(5), 30)
        self.assertEqual(web_monthly(7), 30)
        self.assertEqual(web_monthly(8), 60)
        self.assertEqual(web_monthly(10), 60)
        self.assertEqual(web_monthly(11), 90)
        self.assertEqual(web_monthly(110), 1080)

    def test_example_7187(self):
        result = compute_price(pages=3, period_months=12, materialnik=True, growth=False)
        self.assertEqual(result['total'], 7187)
        self.assertEqual(result['monthly'], 599)
        self.assertEqual(result['growth_label'], 'ZDARMA')
        self.assertEqual(result['period_phrase'], 'první rok')

    def test_five_pages_yearly_adds_360(self):
        base = compute_price(pages=3, period_months=12, materialnik=True, growth=False)
        extra = compute_price(pages=5, period_months=12, materialnik=True, growth=False)
        self.assertEqual(extra['web_monthly'], 30)
        self.assertEqual(extra['total'] - base['total'], 360)

    def test_six_months_materialnik_growth(self):
        result = compute_price(pages=0, period_months=6, materialnik=True, growth=True)
        self.assertEqual(result['total'], 3999 + 99 * 6 + 999)
        self.assertEqual(result['growth_label'], 'ANO +999 Kč')

    def test_twelve_months_ignores_paid_growth(self):
        with_flag = compute_price(pages=0, period_months=12, materialnik=False, growth=True)
        without_flag = compute_price(pages=0, period_months=12, materialnik=False, growth=False)
        self.assertEqual(with_flag['total'], without_flag['total'])
        self.assertEqual(with_flag['growth_fee'], 0)
        self.assertEqual(with_flag['growth_label'], 'ZDARMA')


class KalkulaceParseTests(SimpleTestCase):
    def test_valid_payload(self):
        data = parse_and_compute({
            'email': 'zakaznik@example.com',
            'telefon': '+420 777 123 456',
            'typ': 'kaderictvi',
            'pages': 3,
            'materialnik': True,
            'period': 12,
            'growth': False,
            'poznamka': '',
        })
        self.assertEqual(data['total'], 7187)
        self.assertEqual(data['typ_label'], 'Kadeřnictví / beauty')
        self.assertFalse(data['honeypot'])

    def test_rejects_bad_email_and_empty_phone(self):
        with self.assertRaises(ValueError):
            parse_and_compute({
                'email': 'neplatny',
                'telefon': '777',
                'typ': 'kaderictvi',
                'pages': 0,
                'period': 12,
            })
        with self.assertRaises(ValueError):
            parse_and_compute({
                'email': 'ok@example.com',
                'telefon': '',
                'typ': 'kaderictvi',
                'pages': 0,
                'period': 12,
            })

    def test_caps_pages_and_note(self):
        with self.assertRaises(ValueError):
            parse_and_compute({
                'email': 'ok@example.com',
                'telefon': '777',
                'typ': 'kaderictvi',
                'pages': 1001,
                'period': 12,
            })
        with self.assertRaises(ValueError):
            parse_and_compute({
                'email': 'ok@example.com',
                'telefon': '777',
                'typ': 'jina',
                'pages': 0,
                'period': 6,
                'poznamka': 'x' * 2001,
            })

    def test_email_body_structure(self):
        data = parse_and_compute({
            'email': 'zakaznik@example.com',
            'telefon': '777111222',
            'typ': 'kaderictvi',
            'pages': 3,
            'materialnik': True,
            'period': 12,
            'growth': False,
            'poznamka': '',
        })
        body = format_email_body(data)
        self.assertIn('Potenciální zákazník si spočítal Moderníka.', body)
        self.assertIn('E-mail: zakaznik@example.com', body)
        self.assertIn('Telefon: 777111222', body)
        self.assertIn('Typ provozovny: Kadeřnictví / beauty', body)
        self.assertIn('Web: hlavní + 3 podstránek', body)
        self.assertIn('Materiálník: ANO', body)
        self.assertIn('Partnerství: 12 měsíců', body)
        self.assertIn('Program růstu: ZDARMA', body)
        self.assertIn('Bez speciálních požadavků.', body)
        self.assertIn('7187 Kč / první rok', body)
        self.assertIn('cca 599 Kč / měsíc', body)


class KalkulaceViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.url = '/api/kalkulace/'
        self.payload = {
            'email': 'zakaznik@example.com',
            'telefon': '777111222',
            'typ': 'kaderictvi',
            'pages': 3,
            'materialnik': True,
            'period': 12,
            'growth': False,
            'poznamka': '',
        }

    def test_validation_errors(self):
        res = self.client.post(self.url, data={**self.payload, 'email': ''}, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post(self.url, data={**self.payload, 'telefon': ''}, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post(self.url, data={**self.payload, 'typ': 'neexistuje'}, content_type='application/json')
        self.assertEqual(res.status_code, 400)

    @patch('salons.views.odeslat_kalkulaci')
    def test_success_recomputes_server_side(self, mock_send):
        mock_send.return_value = 'hakl@modernik.cz'
        res = self.client.post(
            self.url,
            data={**self.payload, 'total': 1},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['total'], 7187)
        self.assertEqual(body['monthly'], 599)
        mock_send.assert_called_once()
        sent = mock_send.call_args[0][0]
        self.assertEqual(sent['total'], 7187)

    def test_throttled_hides_wait_seconds(self):
        view = KalkulaceView()
        with self.assertRaises(DrfThrottled) as ctx:
            view.throttled(None, wait=1688)
        detail = str(ctx.exception.detail)
        self.assertNotIn('1688', detail)
        self.assertNotIn('Expected available', detail)
        self.assertIn('později', detail)

    def test_throttle_is_ten_per_ten_minutes_and_post_only(self):
        throttle = KalkulaceRateThrottle()
        self.assertEqual(throttle.scope, 'kalkulace')
        self.assertEqual(throttle.parse_rate(throttle.rate), (10, 600))
        poptavka = PoptavkaRateThrottle()
        self.assertNotEqual(throttle.scope, poptavka.scope)
        factory = RequestFactory()
        view = KalkulaceView()
        get = factory.get('/api/kalkulace/')
        self.assertTrue(throttle.allow_request(get, view))

    @patch('salons.views.odeslat_kalkulaci')
    def test_eleventh_post_is_blocked_with_friendly_message(self, mock_send):
        mock_send.return_value = 'hakl@modernik.cz'
        cache.clear()
        last = None
        statuses = []
        for i in range(11):
            payload = {**self.payload, 'email': f'zakaznik{i}@example.com'}
            last = self.client.post(self.url, data=payload, content_type='application/json')
            statuses.append(last.status_code)
        self.assertEqual(statuses[:10], [200] * 10)
        self.assertEqual(statuses[10], 429)
        self.assertEqual(mock_send.call_count, 10)
        detail = last.json().get('detail', '')
        self.assertNotIn('Expected available', str(detail))
        self.assertNotIn('1688', str(detail))
        self.assertIn('později', str(detail))
