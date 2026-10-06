from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase, RequestFactory

from rest_framework.exceptions import Throttled as DrfThrottled

from rezervace.throttles import KalkulaceRateThrottle, PoptavkaRateThrottle
from salons.kalkulace import compute_price, format_email_body, growth_is_free, parse_and_compute, web_monthly
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
        result = compute_price(pages=3, period_months=12, materialnik=True, growth=False, plan='pro')
        self.assertEqual(result['total'], 7187)
        self.assertEqual(result['monthly'], 599)
        self.assertEqual(result['growth_label'], 'ZDARMA')
        self.assertEqual(result['period_phrase'], 'první rok')

    def test_five_pages_yearly_adds_360(self):
        base = compute_price(pages=3, period_months=12, materialnik=True, growth=False, plan='pro')
        extra = compute_price(pages=5, period_months=12, materialnik=True, growth=False, plan='pro')
        self.assertEqual(extra['web_monthly'], 30)
        self.assertEqual(extra['total'] - base['total'], 360)

    def test_six_months_materialnik_growth(self):
        result = compute_price(pages=0, period_months=6, materialnik=True, growth=True, plan='pro')
        self.assertEqual(result['total'], 3600 + 99 * 6 + 999)
        self.assertEqual(result['monthly'], 866)
        self.assertEqual(result['growth_label'], 'ANO +999 Kč')

    def test_twelve_months_ignores_paid_growth_only_for_pro(self):
        with_flag = compute_price(pages=0, period_months=12, materialnik=False, growth=True, plan='pro')
        without_flag = compute_price(pages=0, period_months=12, materialnik=False, growth=False, plan='pro')
        self.assertEqual(with_flag['total'], without_flag['total'])
        self.assertEqual(with_flag['total'], 5999)
        self.assertEqual(with_flag['growth_fee'], 0)
        self.assertEqual(with_flag['growth_label'], 'ZDARMA')
        self.assertTrue(with_flag['growth'])
        self.assertTrue(without_flag['growth'])

    def test_growth_is_free_only_for_pro_12(self):
        self.assertTrue(growth_is_free('pro', 12))
        self.assertFalse(growth_is_free('start', 12))
        self.assertFalse(growth_is_free('pro', 6))
        self.assertFalse(growth_is_free('start', 6))

    def test_growth_fee_matrix(self):
        """Program Růstu zdarma ⇔ PRO + 12 měsíců."""
        cases = [
            ('start', 6, False, 1800, 300, 0, 'NE', False),
            ('start', 6, True, 2799, 467, 999, 'ANO +999 Kč', True),
            ('start', 12, False, 3000, 250, 0, 'NE', False),
            ('start', 12, True, 3999, 333, 999, 'ANO +999 Kč', True),
            ('pro', 6, False, 3600, 600, 0, 'NE', False),
            ('pro', 6, True, 4599, 767, 999, 'ANO +999 Kč', True),
            ('pro', 12, False, 5999, 500, 0, 'ZDARMA', True),
            ('pro', 12, True, 5999, 500, 0, 'ZDARMA', True),
        ]
        for plan, months, growth, total, monthly, fee, label, included in cases:
            with self.subTest(plan=plan, months=months, growth=growth):
                result = compute_price(0, months, False, growth, plan)
                self.assertEqual(result['total'], total)
                self.assertEqual(result['monthly'], monthly)
                self.assertEqual(result['growth_fee'], fee)
                self.assertEqual(result['growth_label'], label)
                self.assertEqual(result['growth'], included)

    def test_start_and_pro_base_prices(self):
        cases = [
            ('start', 6, False, False, 1800, 300),
            ('start', 12, False, False, 3000, 250),
            ('pro', 6, False, False, 3600, 600),
            ('pro', 12, False, False, 5999, 500),
            ('start', 6, True, False, 1800 + 99 * 6, 399),
            ('start', 12, True, False, 3000 + 99 * 12, 349),
            ('pro', 6, True, False, 3600 + 99 * 6, 699),
            ('pro', 12, True, False, 5999 + 99 * 12, 599),
            ('start', 6, False, True, 1800 + 999, 467),
            ('pro', 6, False, True, 3600 + 999, 767),
            ('start', 12, False, True, 3000 + 999, 333),
            ('pro', 12, False, True, 5999, 500),
        ]
        for plan, months, materialnik, growth, total, monthly in cases:
            with self.subTest(plan=plan, months=months, materialnik=materialnik, growth=growth):
                result = compute_price(0, months, materialnik, growth, plan)
                self.assertEqual(result['total'], total)
                self.assertEqual(result['monthly'], monthly)
                self.assertEqual(result['plan_label'], 'Moderník START' if plan == 'start' else 'Moderník PRO')

    def test_unknown_plan_is_rejected(self):
        with self.assertRaises(ValueError):
            compute_price(0, 12, False, False, plan='enterprise')
        with self.assertRaises(ValueError):
            compute_price(0, 12, False, False, plan='')


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
            'plan': 'pro',
            'poznamka': '',
        })
        self.assertEqual(data['total'], 7187)
        self.assertEqual(data['plan'], 'pro')
        self.assertEqual(data['plan_label'], 'Moderník PRO')
        self.assertEqual(data['typ_label'], 'Kadeřnictví / beauty')
        self.assertFalse(data['honeypot'])

    def test_missing_or_unknown_plan_is_rejected(self):
        base = {
            'email': 'zakaznik@example.com',
            'telefon': '+420 777 123 456',
            'typ': 'kaderictvi',
            'pages': 0,
            'period': 12,
        }
        with self.assertRaises(ValueError):
            parse_and_compute(base)
        with self.assertRaises(ValueError):
            parse_and_compute({**base, 'plan': 'enterprise'})
        start = parse_and_compute({**base, 'plan': 'start'})
        self.assertEqual(start['total'], 3000)
        self.assertEqual(start['plan_label'], 'Moderník START')

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
            'plan': 'pro',
            'poznamka': '',
        })
        body = format_email_body(data)
        self.assertIn('Potenciální zákazník si spočítal Moderníka.', body)
        self.assertIn('E-mail: zakaznik@example.com', body)
        self.assertIn('Telefon: 777111222', body)
        self.assertIn('Typ provozovny: Kadeřnictví / beauty', body)
        self.assertIn('Produkt: Moderník PRO', body)
        self.assertIn('Web: hlavní + 3 podstránek', body)
        self.assertIn('Materiálník: ANO', body)
        self.assertIn('Partnerství: 12 měsíců', body)
        self.assertIn('Program růstu: ZDARMA', body)
        self.assertIn('Bez speciálních požadavků.', body)
        self.assertIn('7187 Kč / první rok', body)
        self.assertIn('cca 599 Kč / měsíc', body)

    def test_start_email_body_and_price(self):
        data = parse_and_compute({
            'email': 'zakaznik@example.com',
            'telefon': '777111222',
            'typ': 'kaderictvi',
            'pages': 0,
            'materialnik': False,
            'period': 6,
            'growth': True,
            'plan': 'start',
            'poznamka': 'Chci začít s webem.',
            'total': 1,
        })
        self.assertEqual(data['total'], 1800 + 999)
        body = format_email_body(data)
        self.assertIn('Produkt: Moderník START', body)
        self.assertIn('Partnerství: 6 měsíců', body)
        self.assertIn('Program růstu: ANO +999 Kč', body)
        self.assertIn('2799 Kč / prvních 6 měsíců', body)
        self.assertIn('Chci začít s webem.', body)
        self.assertNotIn('Produkt: Moderník PRO', body)

    def test_start_12_growth_email_is_paid(self):
        data = parse_and_compute({
            'email': 'zakaznik@example.com',
            'telefon': '777111222',
            'typ': 'kaderictvi',
            'pages': 0,
            'materialnik': False,
            'period': 12,
            'growth': True,
            'plan': 'start',
            'poznamka': '',
        })
        self.assertEqual(data['total'], 3999)
        self.assertEqual(data['monthly'], 333)
        self.assertEqual(data['growth_label'], 'ANO +999 Kč')
        self.assertEqual(data['growth_fee'], 999)
        body = format_email_body(data)
        self.assertIn('Produkt: Moderník START', body)
        self.assertIn('Partnerství: 12 měsíců', body)
        self.assertIn('Program růstu: ANO +999 Kč', body)
        self.assertIn('3999 Kč / první rok', body)
        self.assertNotIn('Program růstu: ZDARMA', body)

    def test_pro_12_email_growth_is_free(self):
        data = parse_and_compute({
            'email': 'zakaznik@example.com',
            'telefon': '777111222',
            'typ': 'kaderictvi',
            'pages': 0,
            'materialnik': False,
            'period': 12,
            'growth': False,
            'plan': 'pro',
            'poznamka': '',
        })
        self.assertEqual(data['total'], 5999)
        self.assertEqual(data['growth_label'], 'ZDARMA')
        body = format_email_body(data)
        self.assertIn('Produkt: Moderník PRO', body)
        self.assertIn('Program růstu: ZDARMA', body)
        self.assertIn('5999 Kč / první rok', body)


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
            'plan': 'pro',
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
        self.assertEqual(sent['plan'], 'pro')
        self.assertEqual(sent['plan_label'], 'Moderník PRO')

    @patch('salons.views.odeslat_kalkulaci')
    def test_start_plan_ignores_client_total(self, mock_send):
        mock_send.return_value = 'hakl@modernik.cz'
        res = self.client.post(
            self.url,
            data={**self.payload, 'plan': 'start', 'pages': 0, 'materialnik': False, 'total': 1},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['total'], 3000)
        self.assertEqual(body['monthly'], 250)
        self.assertEqual(body['plan'], 'start')
        sent = mock_send.call_args[0][0]
        self.assertEqual(sent['total'], 3000)
        self.assertEqual(sent['plan_label'], 'Moderník START')
        self.assertIn('Produkt: Moderník START', format_email_body(sent))

    def test_unknown_plan_is_400(self):
        res = self.client.post(
            self.url,
            data={**self.payload, 'plan': 'enterprise'},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        res = self.client.post(
            self.url,
            data={k: v for k, v in self.payload.items() if k != 'plan'},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

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
