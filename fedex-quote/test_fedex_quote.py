import datetime, json, threading, unittest, urllib.request
from unittest.mock import patch

import fedex_quote as fq

CREDS = {'FEDEX_API_KEY': 'test-key', 'FEDEX_SECRET_KEY': 'test-secret-value', 'FEDEX_ACCOUNT_NUMBER': '123456789', 'FEDEX_ENV': 'test'}
TOKEN = (200, {'access_token': 'tok', 'expires_in': 3600})


def rate_reply(total=359.77, zone='5', service='GROUND_HOME_DELIVERY'):
    return (200, {'output': {'rateReplyDetails': [{
        'serviceType': service, 'serviceName': 'FedEx Home Delivery®',
        'commit': {'dateDetail': {'dayFormat': '2026-09-29T20:00:00'}},
        'ratedShipmentDetails': [
            {'rateType': 'LIST', 'totalNetCharge': 520.10, 'shipmentRateDetail': {'rateZone': zone}},
            {'rateType': 'ACCOUNT', 'totalNetCharge': total, 'totalBaseCharge': 39.07, 'totalDiscounts': 0,
             'ratedPackages': [{'groupNumber': 0, 'packageRateDetail': {'billingWeight': {'units': 'LB', 'value': 116},
                                'baseCharge': 39.07, 'netCharge': total, 'surcharges': [{'type': 'OVERSIZE', 'amount': 240.0}]}}],
             'shipmentRateDetail': {'rateZone': zone, 'fuelSurchargePercent': 28.0, 'totalSurcharges': 320.70,
                                    'totalBillingWeight': {'units': 'LB', 'value': 116},
                                    'surCharges': [{'type': 'OVERSIZE', 'description': 'Oversize charge', 'amount': 240.0},
                                                   {'type': 'RESIDENTIAL_DELIVERY', 'description': 'Residential delivery', 'amount': 2.0},
                                                   {'type': 'FUEL', 'description': 'Fuel', 'amount': 78.70}]}}]}]}})


OVERSIZE_BOX = [{'length': 60, 'width': 40, 'height': 8, 'weight': 45, 'label': 'Custom box'}]


class Estimate(unittest.TestCase):
    def test_matches_stored_bigquery_price(self):
        # MIRCIR3131BLK ships at its item size; BigQuery stores $47.91 for zone 5.
        info = fq.sku_info('MIRCIR3131BLK')
        box = fq.normalize_packages([{'length': info['dims'][0], 'width': info['dims'][1], 'height': info['dims'][2], 'weight': info['weight']}])
        self.assertEqual(fq.estimate(box, 5, True, 28)['total'], info['stored_rates']['5'])

    def test_oversize_replaces_handling(self):
        e = fq.estimate(fq.normalize_packages(OVERSIZE_BOX), 5, True, 28)
        labels = [l['label'] for l in e['packages'][0]['lines']]
        self.assertIn('Oversize charge', labels)
        self.assertFalse(any(l.startswith('Additional handling') for l in labels))
        self.assertEqual(e['packages'][0]['billable'], 116)
        self.assertEqual(e['total'], 359.77)

    def test_only_highest_handling_fee(self):
        e = fq.estimate(fq.normalize_packages([{'length': 50, 'width': 20, 'height': 10, 'weight': 60}]), 2, False, 0)
        fees = [l for l in e['packages'][0]['lines'] if l['label'].startswith('Additional handling')]
        self.assertEqual(fees, [{'label': 'Additional handling · weight', 'amount': 23.0}])

    def test_blocked_package_not_priced(self):
        e = fq.estimate(fq.normalize_packages([{'length': 110, 'width': 10, 'height': 10, 'weight': 20}]), 5, True, 28)
        self.assertFalse(e['complete'])
        self.assertIn('108', e['packages'][0]['note'])

    def test_distance_zone_verified_routes(self):
        self.assertEqual(fq.distance_zone('fontana', '83440'), 5)
        self.assertEqual(fq.distance_zone('edison', '83440'), 8)


class Quote(unittest.TestCase):
    def setUp(self):
        fq._token.update(value=None, expires=0, key=None)

    def run_quote(self, replies, **kw):
        with patch.dict(fq.os.environ, CREDS, clear=True), patch.object(fq, '_keychain_read', return_value=None), \
             patch.object(fq, '_post', side_effect=replies) as post:
            return fq.quote('fontana', '83440', OVERSIZE_BOX, **kw), post

    def test_request_and_parse(self):
        r, post = self.run_quote([TOKEN, rate_reply()])
        token_call, rate_call = post.call_args_list
        self.assertTrue(token_call.args[0].startswith('https://apis-sandbox.fedex.com/oauth/token'))
        body = json.loads(rate_call.args[1])
        shipment = body['requestedShipment']
        self.assertEqual(body['accountNumber']['value'], '123456789')
        self.assertEqual(shipment['shipper']['address']['postalCode'], '92335')
        self.assertTrue(shipment['recipient']['address']['residential'])
        self.assertEqual(shipment['serviceType'], 'GROUND_HOME_DELIVERY')
        self.assertEqual(shipment['requestedPackageLineItems'][0]['dimensions'], {'length': 60, 'width': 40, 'height': 8, 'units': 'IN'})
        self.assertEqual(rate_call.args[2]['Authorization'], 'Bearer tok')
        self.assertEqual(r['account']['total'], 359.77)
        self.assertEqual(r['account']['rate_type'], 'ACCOUNT')
        self.assertEqual(r['list']['total'], 520.10)
        self.assertEqual(r['zone_source'], 'FedEx')
        self.assertEqual(r['estimate']['total'], 359.77)
        self.assertNotIn('test-secret-value', json.dumps(r))

    def test_business_uses_ground(self):
        r, post = self.run_quote([TOKEN, rate_reply(service='FEDEX_GROUND')], residential=False)
        shipment = json.loads(post.call_args_list[1].args[1])['requestedShipment']
        self.assertEqual(shipment['serviceType'], 'FEDEX_GROUND')
        self.assertFalse(shipment['recipient']['address']['residential'])

    def test_bad_credentials_message(self):
        with self.assertRaisesRegex(fq.QuoteError, 'did not accept'):
            self.run_quote([(401, {'errors': [{'code': 'NOT.AUTHORIZED.ERROR', 'message': 'bad'}]})])

    def test_fedex_error_is_shown(self):
        with self.assertRaisesRegex(fq.QuoteError, 'POSTALCODE.INVALID'):
            self.run_quote([TOKEN, (400, {'errors': [{'code': 'POSTALCODE.INVALID', 'message': 'no'}]})])

    def test_keychain_prefers_production(self):
        store = {'test/api_key': 'tk', 'test/secret_key': 'ts', 'test/account_number': '1',
                 'production/api_key': 'pk', 'production/secret_key': 'ps', 'production/account_number': '2'}
        with patch.dict(fq.os.environ, {}, clear=True), patch.object(fq, '_keychain_read', side_effect=store.get):
            self.assertEqual(fq.credentials()['environment'], 'production')
            self.assertEqual(fq.credentials()['api_key'], 'pk')
        with patch.dict(fq.os.environ, {'FEDEX_ENV': 'test'}, clear=True), patch.object(fq, '_keychain_read', side_effect=store.get):
            self.assertEqual(fq.credentials()['api_key'], 'tk')
        only_test = {k: v for k, v in store.items() if k.startswith('test/')}
        with patch.dict(fq.os.environ, {}, clear=True), patch.object(fq, '_keychain_read', side_effect=only_test.get):
            self.assertEqual(fq.credentials()['environment'], 'test')

    def test_unexplained_error_gets_account_hint(self):
        creds = dict(CREDS, FEDEX_ENV='production')
        with patch.dict(fq.os.environ, creds, clear=True), patch.object(fq, '_keychain_read', return_value=None), \
             patch.object(fq, '_post', side_effect=[TOKEN, (400, {'_raw': '<html>Bad Request</html>'})]):
            with self.assertRaisesRegex(fq.QuoteError, 'Bad Request.*real Americanflat'):
                fq.quote('fontana', '83440', OVERSIZE_BOX)

    def test_json_helper(self):
        self.assertEqual(fq._json(b''), {})
        self.assertEqual(fq._json('not json')['_raw'], 'not json')
        self.assertEqual(fq._json(b'{"a":1}'), {'a': 1})

    def test_gzip_reply(self):
        import gzip
        self.assertEqual(fq._json(gzip.compress(b'{"errors":[{"code":"ACCOUNT.NUMBER.INVALID","message":"x"}]}'))['errors'][0]['code'],
                         'ACCOUNT.NUMBER.INVALID')

    def test_missing_credentials(self):
        with patch.dict(fq.os.environ, {}, clear=True), patch.object(fq, '_keychain_read', return_value=None):
            with self.assertRaisesRegex(fq.QuoteError, 'setup'):
                fq.quote('fontana', '83440', OVERSIZE_BOX)

    def test_input_validation(self):
        for args in (('nowhere', '83440', OVERSIZE_BOX), ('fontana', '8344', OVERSIZE_BOX), ('fontana', '83440', []),
                     ('fontana', '83440', [{'length': 0, 'width': 1, 'height': 1, 'weight': 1}])):
            with self.assertRaises(fq.QuoteError):
                fq.quote(*args)
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(fq.QuoteError, 'later'):
            fq.quote('fontana', '83440', OVERSIZE_BOX, ship_date=yesterday)

    def test_box_argument(self):
        self.assertEqual(fq.parse_box('60x40x8@45*2')['count'], 2)
        with self.assertRaises(Exception):
            fq.parse_box('60x40@45')


class Page(unittest.TestCase):
    def test_server_routes(self):
        httpd = fq.ThreadingHTTPServer(('127.0.0.1', 0), fq.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = 'http://127.0.0.1:%d' % port
        try:
            self.assertIn(b'FedEx Live Quote', urllib.request.urlopen(base + '/').read())
            hits = json.loads(urllib.request.urlopen(base + '/api/skus?q=MIRCIR3131').read())
            self.assertEqual(hits[0]['sku'], 'MIRCIR3131BLK')
            req = urllib.request.Request(base + '/api/quote', b'{}', {'Content-Type': 'application/json', 'Origin': 'http://evil.example'})
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req)
            self.assertEqual(e.exception.code, 403)
            fq._token.update(value=None, expires=0, key=None)
            with patch.dict(fq.os.environ, CREDS, clear=True), patch.object(fq, '_keychain_read', return_value=None), \
                 patch.object(fq, '_post', side_effect=[TOKEN, rate_reply()]):
                body = json.dumps({'origin': 'fontana', 'destination': '83440', 'residential': True, 'packages': OVERSIZE_BOX}).encode()
                req = urllib.request.Request(base + '/api/quote', body, {'Content-Type': 'application/json', 'Origin': base})
                r = json.loads(urllib.request.urlopen(req).read())
            self.assertEqual(r['account']['total'], 359.77)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_curl_fallback(self):
        seen = {}

        class Echo(fq.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                seen['auth'] = self.headers.get('Authorization')
                seen['body'] = self.rfile.read(int(self.headers['Content-Length']))
                import gzip
                data = gzip.compress(b'{"ok": "yes \\"quoted\\""}')
                self.send_response(201); self.send_header('Content-Encoding', 'gzip'); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        httpd = fq.ThreadingHTTPServer(('127.0.0.1', 0), Echo)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            body = json.dumps({'note': 'has "quotes" and \\ backslash'}).encode()
            status, payload = fq._curl_post('http://127.0.0.1:%d/x' % httpd.server_address[1], body, {'Authorization': 'Bearer a"b', 'Content-Type': 'application/json'})
        finally:
            httpd.shutdown(); httpd.server_close()
        self.assertEqual(status, 201)
        self.assertEqual(payload, {'ok': 'yes "quoted"'})
        self.assertEqual(seen['body'], body)
        self.assertEqual(seen['auth'], 'Bearer a"b')


if __name__ == '__main__':
    unittest.main()
