#!/usr/bin/env python3
"""Live FedEx rate quotes for Americanflat packages, run on the Mac.

Asks FedEx's Rates and Transit Times API for the real price of one or more
boxes from Fontana, Edison or Hardeeville, and sets it next to the estimate
from the January 2026 contract rate book so differences stand out.

Credentials never leave this machine. They are read from environment
variables, or from the macOS Keychain after `python3 fedex_quote.py setup`.

  python3 fedex_quote.py setup                 # store API key, secret, account
  python3 fedex_quote.py check                 # confirm FedEx accepts them
  python3 fedex_quote.py serve                 # page at http://127.0.0.1:8767
  python3 fedex_quote.py quote --from fontana --to 83440 --box 60x40x8@45
"""
import argparse, datetime, getpass, json, math, os, re, ssl, subprocess, sys, threading, time
import urllib.error, urllib.parse, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
HOSTS = {'test': 'https://apis-sandbox.fedex.com', 'production': 'https://apis.fedex.com'}
KEYCHAIN_SERVICE = 'americanflat-fedex-quote'
CRED_FIELDS = [('FEDEX_API_KEY', 'api_key', 'API key'), ('FEDEX_SECRET_KEY', 'secret_key', 'Secret key'),
               ('FEDEX_ACCOUNT_NUMBER', 'account_number', 'Account number')]

WAREHOUSES = {
    'fontana': {'name': 'Fontana', 'zip': '92335', 'lat': 34.0794, 'lon': -117.4551},
    'edison': {'name': 'Edison', 'zip': '08837', 'lat': 40.5325, 'lon': -74.3375},
    'hardeeville': {'name': 'Hardeeville', 'zip': '29927', 'lat': 32.2635, 'lon': -81.0669},
}
WAREHOUSE_ALIASES = {'fon': 'fontana', 'ca': 'fontana', '92335': 'fontana', 'nj': 'edison', 'edi': 'edison', '08837': 'edison',
                     'sc': 'hardeeville', 'hardesville': 'hardeeville', '29927': 'hardeeville'}

# Contract fees, "Other transportation related fees", rate book effective 2026-01-05.
# Index by zone band: zone 2, zones 3-4, zones 5-6, zones 7+.
FEES = {'ahs_dim': [14.75, 16.38, 19.25, 20.38], 'ahs_weight': [23.00, 25.13, 28.13, 29.38],
        'ahs_packaging': [13.25, 15.38, 16.50, 16.88], 'oversize': [191.25, 206.25, 240.00, 247.50], 'residential': 2.00}

_rates = json.loads((DATA / 'rates.json').read_text())
_zip3 = json.loads((DATA / 'zip3.json').read_text())
_skus = {r[0]: r for r in json.loads((DATA / 'skus.json').read_text())['rows']}


# ---------------------------------------------------------------- credentials

def _keychain_read(account):
    if sys.platform != 'darwin':
        return None
    r = subprocess.run(['security', 'find-generic-password', '-s', KEYCHAIN_SERVICE, '-a', account, '-w'],
                       capture_output=True, text=True)
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def credentials():
    """Environment variables win. Otherwise the Keychain entries written by `setup`: test and production are kept
    side by side, and production is used once it has been saved (FEDEX_ENV=test forces the test server)."""
    env = (os.environ.get('FEDEX_ENV') or '').strip().lower()
    if env and env not in HOSTS:
        raise QuoteError('FEDEX_ENV must be "test" or "production".')
    if all(os.environ.get(e) for e, _, _ in CRED_FIELDS):
        out = {a: os.environ[e] for e, a, _ in CRED_FIELDS}
        out['environment'] = env or 'test'
        return out
    for candidate in ([env] if env else ['production', 'test']):
        out = {a: os.environ.get(e) or _keychain_read(candidate + '/' + a) for e, a, _ in CRED_FIELDS}
        if all(out.values()) or env:
            out['environment'] = candidate
            return out
    out = {a: os.environ.get(e) for e, a, _ in CRED_FIELDS}
    out['environment'] = 'test'
    return out


def missing_credentials(c):
    return [label for env, account, label in CRED_FIELDS if not c.get(account)]


def setup():
    if sys.platform != 'darwin':
        sys.exit('setup stores credentials in the macOS Keychain, so it only runs on a Mac. '
                 'Elsewhere, set FEDEX_API_KEY, FEDEX_SECRET_KEY, FEDEX_ACCOUNT_NUMBER and FEDEX_ENV.')
    print('This saves your FedEx credentials in the Mac Keychain under "%s".' % KEYCHAIN_SERVICE)
    print('Nothing is written to a file, and typing the secret key shows nothing on screen.\n')
    env = input('Which key tab are these from, test or production? [test]: ').strip().lower() or 'test'
    if env not in HOSTS:
        sys.exit('Answer "test" or "production". Nothing was saved.')
    existing = [a for _, a, _ in CRED_FIELDS if _keychain_read(env + '/' + a)]
    if existing:
        sys.exit('%s credentials are already saved, so nothing was changed. The program uses them now.' % env.title())
    values = {'api_key': input('API key: ').strip(), 'secret_key': getpass.getpass('Secret key (hidden): ').strip(),
              'account_number': input('FedEx account number: ').strip()}
    if not all(values.values()):
        sys.exit('All three answers are needed. Nothing was saved.')
    for account, value in values.items():
        # -w with the value as its argument: it is briefly visible to other processes on this Mac,
        # which is acceptable for a single-user machine.
        r = subprocess.run(['security', 'add-generic-password', '-s', KEYCHAIN_SERVICE, '-a', env + '/' + account,
                            '-w', value], capture_output=True, text=True)
        if r.returncode:
            sys.exit('Keychain refused to save %s: %s' % (account, r.stderr.strip()))
    print('\nSaved %s credentials. Next: python3 fedex_quote.py check' % env)
    if env == 'production':
        print('Production is used from now on. To try the test server again: FEDEX_ENV=test python3 fedex_quote.py serve')


# ---------------------------------------------------------------- FedEx calls

class QuoteError(Exception):
    pass


def _ssl_context():
    try:
        import certifi  # present when installed; python.org Pythons often lack a CA bundle otherwise
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _post(url, body, headers):
    """POST and return (status, parsed JSON). Falls back to the system curl when Python has no CA bundle."""
    req = urllib.request.Request(url, body, headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as r:
            return r.status, _json(r.read())
    except urllib.error.HTTPError as e:
        return e.code, _json(e.read())
    except urllib.error.URLError as e:
        if not isinstance(getattr(e, 'reason', None), ssl.SSLCertVerificationError):
            raise QuoteError('Could not reach FedEx (%s). Check the internet connection.' % e.reason)
    return _curl_post(url, body, headers)


def _curl_post(url, body, headers):
    # curl reads its whole config (headers and body) from stdin, so secrets never appear in the process list.
    def q(s):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    config = ['url = ' + q(url), 'request = "POST"', 'silent', 'show-error', 'max-time = 30',
              'write-out = "\\n%{http_code}"'] + ['header = ' + q('%s: %s' % kv) for kv in headers.items()]
    config.append('data-binary = ' + q(body.decode()))
    r = subprocess.run(['/usr/bin/curl', '--config', '-'], input='\n'.join(config), capture_output=True, text=True)
    if r.returncode:
        raise QuoteError('Could not reach FedEx (%s).' % r.stderr.strip())
    text, _, code = r.stdout.rpartition('\n')
    try:
        status = int(code)
    except ValueError:
        status = 0
    return status, _json(text)


def _json(raw):
    """Parse a FedEx reply; keep the start of anything that isn't JSON so errors can still be explained."""
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', 'replace')
    raw = (raw or '').strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {'_raw': raw[:400]}
    except ValueError:
        return {'_raw': raw[:400]}


def _fedex_errors(payload):
    errs = payload.get('errors') or payload.get('output', {}).get('alerts') or []
    if isinstance(errs, dict):
        errs = [errs]
    text = '; '.join('%s: %s' % (e.get('code', 'ERROR'), e.get('message', '')) for e in errs if isinstance(e, dict))
    if text:
        return text
    if payload.get('message') or payload.get('error'):
        return str(payload.get('message') or payload.get('error'))[:300]
    if payload.get('_raw'):
        return 'FedEx replied: ' + ' '.join(payload['_raw'].split())[:300]
    return 'FedEx sent no explanation'


ACCOUNT_HINT = (' If the account number is the one shown on the Test Key tab, production needs your real Americanflat '
                'FedEx account number instead (it is printed on your FedEx invoices).')


_token = {'value': None, 'expires': 0, 'key': None}
_token_lock = threading.Lock()


def access_token(c):
    host = HOSTS[c['environment']]
    with _token_lock:
        if _token['value'] and _token['key'] == (host, c['api_key']) and time.time() < _token['expires'] - 60:
            return _token['value']
        body = urllib.parse.urlencode({'grant_type': 'client_credentials', 'client_id': c['api_key'],
                                       'client_secret': c['secret_key']}).encode()
        status, payload = _post(host + '/oauth/token', body, {'Content-Type': 'application/x-www-form-urlencoded'})
        if status != 200 or 'access_token' not in payload:
            raise QuoteError('FedEx did not accept the API key and secret key (HTTP %s, %s). Check that both come '
                             'from the same project and the same tab (Test Key or Production Key).'
                             % (status, _fedex_errors(payload)))
        _token.update(value=payload['access_token'], expires=time.time() + int(payload.get('expires_in', 3600)),
                      key=(host, c['api_key']))
        return _token['value']


# ---------------------------------------------------------------- shipment model

def warehouse(name):
    key = str(name).strip().lower()
    key = WAREHOUSE_ALIASES.get(key, key)
    if key not in WAREHOUSES:
        raise QuoteError('Unknown warehouse "%s". Use fontana, edison or hardeeville.' % name)
    return key


def _pos(v, label):
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise QuoteError('%s must be a number.' % label)
    if not math.isfinite(n) or n <= 0:
        raise QuoteError('%s must be more than zero.' % label)
    return n


def normalize_packages(packages):
    """[{length,width,height,weight,count,nonstandard,label}] -> validated list."""
    if not packages:
        raise QuoteError('Add at least one box.')
    out = []
    for i, p in enumerate(packages, 1):
        count = int(p.get('count') or 1)
        if count < 1 or count > 99:
            raise QuoteError('Box %d: the number of boxes must be 1 to 99.' % i)
        out.append({'label': str(p.get('label') or 'Box %d' % i)[:80], 'count': count,
                    'length': _pos(p.get('length'), 'Box %d length' % i), 'width': _pos(p.get('width'), 'Box %d width' % i),
                    'height': _pos(p.get('height'), 'Box %d height' % i), 'weight': _pos(p.get('weight'), 'Box %d weight' % i),
                    'nonstandard': bool(p.get('nonstandard'))})
    if sum(p['count'] for p in out) > 99:
        raise QuoteError('One quote can hold up to 99 boxes.')
    return out


def assess(p):
    l, w, h = sorted((math.ceil(p['length']), math.ceil(p['width']), math.ceil(p['height'])), reverse=True)
    weight = p['weight']
    vol, girth = l * w * h, l + 2 * w + 2 * h
    blocked = [m for c, m in ((l > 108, 'longest side over 108 in'), (girth > 165, 'length + girth over 165 in'),
                              (weight > 150, 'actual weight over 150 lb')) if c]
    oversize = [m for c, m in ((l > 96, 'longest side over 96 in'), (girth > 130, 'length + girth over 130 in'),
                               (vol > 17280, 'volume over 17,280 cu in'), (weight > 110, 'weight over 110 lb')) if c]
    dim = [m for c, m in ((l > 48, 'longest side over 48 in'), (w > 30, 'second-longest side over 30 in'),
                          (girth > 105, 'length + girth over 105 in'), (vol > 10368, 'volume over 10,368 cu in')) if c]
    dim_weight = math.ceil(vol / (166 if vol > 1728 else 999))
    minimum = 90 if oversize else 40 if dim else 0
    return {'dims': [l, w, h], 'volume': vol, 'girth': girth, 'blocked': blocked, 'oversize': oversize, 'dim': dim,
            'heavy': weight > 50, 'nonstandard': p['nonstandard'], 'dim_weight': dim_weight, 'minimum': minimum,
            'billable': max(math.ceil(weight), dim_weight, minimum)}


def zone_band(zone):
    return 0 if zone == 2 else 1 if zone <= 4 else 2 if zone <= 6 else 3


def estimate(packages, zone, residential, fuel_percent):
    """Rate-book estimate for comparison. Returns None when the zone is outside 2-8."""
    if not zone or not 2 <= zone <= 8:
        return None
    table = _rates['hd' if residential else 'gr']
    band, rows, total = zone_band(zone), [], 0.0
    for p in packages:
        a = assess(p)
        row = {'label': p['label'], 'count': p['count'], 'billable': a['billable'], 'assessment': a, 'lines': []}
        if a['blocked'] or a['billable'] > 150:
            row['note'] = 'Not priced: ' + (', '.join(a['blocked']) or 'billable weight over 150 lb')
            rows.append(row)
            continue
        lines = [('Rate · %d lb · zone %d' % (a['billable'], zone), table[a['billable'] - 1][zone - 2])]
        if a['oversize']:
            lines.append(('Oversize charge', FEES['oversize'][band]))
        else:
            options = ([('Additional handling · dimensions', FEES['ahs_dim'][band])] if a['dim'] else []) + \
                      ([('Additional handling · weight', FEES['ahs_weight'][band])] if a['heavy'] else []) + \
                      ([('Additional handling · packaging', FEES['ahs_packaging'][band])] if a['nonstandard'] else [])
            if options:
                lines.append(max(options, key=lambda x: x[1]))
        if residential:
            lines.append(('Residential delivery', FEES['residential']))
        sub = round(sum(v for _, v in lines), 2)
        fuel = round(sub * fuel_percent / 100, 2)
        row.update(lines=[{'label': k, 'amount': v} for k, v in lines], fuel=fuel, per_box=round(sub + fuel, 2))
        total += row['per_box'] * p['count']
        rows.append(row)
    return {'zone': zone, 'fuel_percent': fuel_percent, 'packages': rows, 'total': round(total, 2),
            'complete': all('per_box' in r for r in rows)}


def distance_zone(origin_key, dest_zip):
    z3 = _zip3.get(dest_zip[:3])
    if not z3:
        return None
    o = WAREHOUSES[origin_key]
    r = math.pi / 180
    dl, dn = (z3[0] - o['lat']) * r, (z3[1] - o['lon']) * r
    h = math.sin(dl / 2) ** 2 + math.cos(o['lat'] * r) * math.cos(z3[0] * r) * math.sin(dn / 2) ** 2
    miles = 3958.8 * 2 * math.asin(math.sqrt(h))
    for limit, zone in ((150, 2), (300, 3), (600, 4), (1000, 5), (1400, 6), (1800, 7)):
        if miles <= limit:
            return zone
    return 8


def build_request(c, origin_key, dest_zip, residential, packages, ship_date):
    return {
        'accountNumber': {'value': c['account_number']},
        'rateRequestControlParameters': {'returnTransitTimes': True},
        'requestedShipment': {
            'shipper': {'address': {'postalCode': WAREHOUSES[origin_key]['zip'], 'countryCode': 'US'}},
            'recipient': {'address': {'postalCode': dest_zip, 'countryCode': 'US', 'residential': bool(residential)}},
            'serviceType': 'GROUND_HOME_DELIVERY' if residential else 'FEDEX_GROUND',
            'pickupType': 'USE_SCHEDULED_PICKUP',
            'packagingType': 'YOUR_PACKAGING',
            'rateRequestType': ['ACCOUNT', 'LIST'],
            'shipDateStamp': ship_date,
            'totalPackageCount': sum(p['count'] for p in packages),
            'requestedPackageLineItems': [{
                'groupPackageCount': p['count'],
                'weight': {'units': 'LB', 'value': round(p['weight'], 1)},
                'dimensions': {'length': math.ceil(p['length']), 'width': math.ceil(p['width']),
                               'height': math.ceil(p['height']), 'units': 'IN'},
            } for p in packages],
        },
    }


def _num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _surcharges(items):
    return [{'type': s.get('type'), 'description': s.get('description') or s.get('name') or s.get('type'),
             'amount': _num(s.get('amount'))} for s in items or []]


def parse_response(payload, residential):
    wanted = 'GROUND_HOME_DELIVERY' if residential else 'FEDEX_GROUND'
    replies = (payload.get('output') or {}).get('rateReplyDetails') or []
    reply = next((r for r in replies if r.get('serviceType') == wanted), None)
    if not reply:
        found = ', '.join(sorted({r.get('serviceType', '?') for r in replies})) or 'none'
        raise QuoteError('FedEx returned no %s rate (services returned: %s).'
                         % ('Home Delivery' if residential else 'Ground', found))
    details = reply.get('ratedShipmentDetails') or []

    def pick(kinds):
        return next((d for d in details if any(k == (d.get('rateType') or '') for k in kinds)), None)
    account = pick(('ACCOUNT', 'PREFERRED_ACCOUNT', 'INCENTIVE', 'PREFERRED_INCENTIVE', 'ACTUAL')) or (details[0] if details else None)
    listed = pick(('LIST', 'PREFERRED_LIST'))
    if not account:
        raise QuoteError('FedEx returned the service but no price.')

    def summarize(d):
        if not d:
            return None
        srd = d.get('shipmentRateDetail') or {}
        bw = srd.get('totalBillingWeight') or {}
        return {
            'rate_type': d.get('rateType'), 'total': _num(d.get('totalNetCharge') if d.get('totalNetCharge') is not None else d.get('totalNetFedExCharge')),
            'base': _num(d.get('totalBaseCharge')), 'discounts': _num(d.get('totalDiscounts')),
            'surcharge_total': _num(srd.get('totalSurcharges')), 'fuel_percent': _num(srd.get('fuelSurchargePercent')),
            'zone': srd.get('rateZone'), 'billing_weight': _num(bw.get('value')), 'dim_divisor': srd.get('dimDivisor'),
            'rated_weight_method': d.get('ratedWeightMethod'), 'surcharges': _surcharges(srd.get('surCharges')),
            'packages': [{
                'group': rp.get('groupNumber'),
                'rated_weight_method': (rp.get('packageRateDetail') or {}).get('ratedWeightMethod'),
                'billing_weight': _num(((rp.get('packageRateDetail') or {}).get('billingWeight') or {}).get('value')),
                'base': _num((rp.get('packageRateDetail') or {}).get('baseCharge')),
                'discounts': _num((rp.get('packageRateDetail') or {}).get('totalFreightDiscounts')),
                'surcharges': _surcharges((rp.get('packageRateDetail') or {}).get('surcharges')),
                'total': _num((rp.get('packageRateDetail') or {}).get('netCharge')),
            } for rp in d.get('ratedPackages') or []],
        }
    commit_info = reply.get('commit') or {}
    commit = commit_info.get('dateDetail') or {}
    transit = (reply.get('operationalDetail') or {}).get('transitTime')
    if not transit and isinstance(commit_info.get('transitDays'), dict):
        transit = commit_info['transitDays'].get('description')
    return {'service': reply.get('serviceName') or wanted, 'service_type': wanted, 'account': summarize(account),
            'list': summarize(listed), 'delivery': commit.get('dayFormat') or commit.get('dayOfWeek'),
            'transit': transit, 'messages': [m.get('message') for m in reply.get('customerMessages') or [] if m.get('message')]}


def quote(origin, dest_zip, packages, residential=True, ship_date=None, fuel_percent=None):
    origin_key = warehouse(origin)
    dest_zip = str(dest_zip).strip()
    if not re.fullmatch(r'\d{5}', dest_zip):
        raise QuoteError('Enter a five-digit destination ZIP.')
    packages = normalize_packages(packages)
    ship_date = ship_date or datetime.date.today().isoformat()
    try:
        if datetime.date.fromisoformat(ship_date) < datetime.date.today():
            raise QuoteError('Pick today or a later ship date.')
    except ValueError:
        raise QuoteError('Ship date must look like 2026-09-24.')
    c = credentials()
    missing = missing_credentials(c)
    if missing:
        raise QuoteError('Missing %s. Run: python3 fedex_quote.py setup' % ', '.join(missing))
    token = access_token(c)
    body = json.dumps(build_request(c, origin_key, dest_zip, residential, packages, ship_date)).encode()
    status, payload = _post(HOSTS[c['environment']] + '/rate/v1/rates/quotes', body,
                            {'Content-Type': 'application/json', 'X-locale': 'en_US', 'Authorization': 'Bearer ' + token})
    if status != 200:
        detail = _fedex_errors(payload)
        print('FedEx rate request failed: HTTP %s, %s' % (status, detail), file=sys.stderr, flush=True)
        hint = ACCOUNT_HINT if c['environment'] == 'production' and ('ACCOUNT' in detail.upper() or not payload.get('errors')) else ''
        raise QuoteError('FedEx could not rate this shipment (HTTP %s, %s).%s' % (status, detail, hint))
    result = parse_response(payload, residential)
    try:
        fedex_zone = int(str(result['account'].get('zone') or '').strip())
    except ValueError:
        fedex_zone = None
    fuel = fuel_percent if fuel_percent is not None else (result['account'].get('fuel_percent') or 28.0)
    zone = fedex_zone or distance_zone(origin_key, dest_zip)
    result.update(environment=c['environment'], origin=WAREHOUSES[origin_key], destination=dest_zip,
                  residential=bool(residential), ship_date=ship_date, requested=packages,
                  estimate=estimate(packages, zone, residential, fuel),
                  zone_source='FedEx' if fedex_zone else 'distance estimate',
                  quoted_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'))
    return result


def check():
    c = credentials()
    missing = missing_credentials(c)
    if missing:
        sys.exit('Missing %s. Run: python3 fedex_quote.py setup' % ', '.join(missing))
    access_token(c)
    print('FedEx accepted the API key and secret key (%s server).' % c['environment'])
    try:
        r = quote('fontana', '83440', [{'length': 12, 'width': 10, 'height': 4, 'weight': 5, 'label': 'check'}])
    except QuoteError as e:
        sys.exit('But a sample quote with account ending %s failed: %s' % (c['account_number'][-4:], e))
    print('A sample quote worked with account ending %s: 12 x 10 x 4 in, 5 lb, Fontana to 83440 = $%s.'
          % (c['account_number'][-4:], r['account'].get('total')))
    if c['environment'] == 'test':
        print('This is the test server: quotes will be sample prices, not your contract rates.')


# ---------------------------------------------------------------- SKUs

def sku_info(sku):
    r = _skus.get(str(sku).strip().upper())
    if not r:
        return None
    return {'sku': r[0], 'dims': [r[1] or None, r[2] or None, r[3] or None], 'weight': r[4] or None,
            'stored_rates': {str(z): r[3 + z] or None for z in range(2, 9)}}


def sku_search(q, limit=30):
    q = str(q).strip().upper()
    if len(q) < 2:
        return []
    starts = [s for s in _skus if s.startswith(q)]
    rest = [s for s in _skus if q in s and not s.startswith(q)]
    return [sku_info(s) for s in (sorted(starts) + sorted(rest))[:limit]]


# ---------------------------------------------------------------- local page

class Handler(BaseHTTPRequestHandler):
    server_version = 'fedex-quote'

    def log_message(self, *args):
        pass

    def _send(self, status, body, ctype='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(url.query)
        if url.path in ('/', '/index.html'):
            return self._send(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        if url.path == '/api/status':
            try:
                c = credentials()
                return self._send(200, {'environment': c['environment'], 'missing': missing_credentials(c),
                                        'account_hint': (c['account_number'] or '')[-4:]})
            except QuoteError as e:
                return self._send(200, {'environment': None, 'missing': [str(e)]})
        if url.path == '/api/skus':
            return self._send(200, sku_search(params.get('q', [''])[0]))
        if url.path == '/api/sku':
            info = sku_info(params.get('sku', [''])[0])
            return self._send(200 if info else 404, info or {'error': 'SKU not found in the saved list.'})
        self._send(404, {'error': 'Not found'})

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != '/api/quote':
            return self._send(404, {'error': 'Not found'})
        port = self.server.server_address[1]
        if self.headers.get('Origin') not in ('http://127.0.0.1:%d' % port, 'http://localhost:%d' % port):
            return self._send(403, {'error': 'Requests are only accepted from this computer’s page.'})
        try:
            size = int(self.headers.get('Content-Length') or 0)
            if not 0 < size <= 32768:
                raise QuoteError('Request is empty or too large.')
            req = json.loads(self.rfile.read(size))
            self._send(200, quote(req.get('origin'), req.get('destination'), req.get('packages'),
                                  residential=req.get('residential', True), ship_date=req.get('shipDate') or None,
                                  fuel_percent=None))
        except QuoteError as e:
            self._send(400, {'error': str(e)})
        except (ValueError, TypeError, AttributeError):
            self._send(400, {'error': 'The request could not be read.'})
        except Exception:
            self._send(502, {'error': 'Something went wrong reaching FedEx. Try again.'})


def serve(port):
    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print('FedEx quotes: http://127.0.0.1:%d  (Ctrl+C to stop)' % port, flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')


# ---------------------------------------------------------------- command line

def parse_box(text):
    m = re.fullmatch(r'\s*([\d.]+)\s*[x×]\s*([\d.]+)\s*[x×]\s*([\d.]+)\s*@\s*([\d.]+)\s*(?:\*\s*(\d+))?\s*', text)
    if not m:
        raise argparse.ArgumentTypeError('box must look like 60x40x8@45 (inches @ pounds), optionally *3 for three boxes')
    l, w, h, lb, n = m.groups()
    return {'length': l, 'width': w, 'height': h, 'weight': lb, 'count': int(n or 1), 'label': text.strip()}


def print_quote(r):
    money = lambda v: '—' if v is None else '$%.2f' % v
    a = r['account']
    print('\n%s · %s %s → %s · %s server%s' % (r['service'], r['origin']['name'], r['origin']['zip'], r['destination'],
                                               r['environment'], ' (sample prices)' if r['environment'] == 'test' else ''))
    print('Zone %s · billed %s lb · fuel %s%%' % (a.get('zone') or '?', a.get('billing_weight') or '?', a.get('fuel_percent') or '?'))
    print('  Base transportation   %10s' % money(a.get('base')))
    if a.get('discounts'):
        print('  Discounts             %10s' % money(-abs(a['discounts'])))
    for s in a['surcharges']:
        print('  %-22s%10s' % ((s['description'] or s['type'] or 'Surcharge')[:22], money(s['amount'])))
    print('  FedEx total           %10s' % money(a.get('total')))
    e = r.get('estimate')
    if e:
        diff = None if a.get('total') is None else round(a['total'] - e['total'], 2)
        print('  Rate-book estimate    %10s%s' % (money(e['total']), '' if diff is None else '  (FedEx %s%s)' % ('+' if diff >= 0 else '', money(diff))))
    if r.get('delivery') or r.get('transit'):
        print('  Delivery: %s' % (r.get('delivery') or r.get('transit')))


def main(argv=None):
    ap = argparse.ArgumentParser(description='Live FedEx rate quotes for Americanflat packages.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('setup', help='save API key, secret key and account number in the Mac Keychain')
    sub.add_parser('check', help='confirm FedEx accepts the saved credentials')
    s = sub.add_parser('serve', help='open the quote page on this computer')
    s.add_argument('--port', type=int, default=8767)
    q = sub.add_parser('quote', help='quote from the command line')
    q.add_argument('--from', dest='origin', required=True, help='fontana, edison or hardeeville')
    q.add_argument('--to', dest='dest', required=True, help='destination ZIP')
    q.add_argument('--box', action='append', type=parse_box, default=[], help='LxWxH@LB, e.g. 60x40x8@45 or 60x40x8@45*2')
    q.add_argument('--sku', action='append', default=[], help='SKU from the saved list (item size, no packaging)')
    q.add_argument('--business', action='store_true', help='business address (FedEx Ground) instead of residential')
    q.add_argument('--date', help='ship date, YYYY-MM-DD (default today)')
    q.add_argument('--json', action='store_true', help='print the full result as JSON')
    args = ap.parse_args(argv)
    try:
        if args.cmd == 'setup':
            return setup()
        if args.cmd == 'check':
            return check()
        if args.cmd == 'serve':
            return serve(args.port)
        packages = list(args.box)
        for s in args.sku:
            info = sku_info(s)
            if not info or not all(info['dims']) or not info['weight']:
                raise QuoteError('No saved size for SKU %s. Use --box with the carton size instead.' % s)
            packages.append({'length': info['dims'][0], 'width': info['dims'][1], 'height': info['dims'][2],
                             'weight': info['weight'], 'label': info['sku']})
        r = quote(args.origin, args.dest, packages, residential=not args.business, ship_date=args.date)
        print(json.dumps(r, indent=2)) if args.json else print_quote(r)
    except QuoteError as e:
        sys.exit(str(e))


if __name__ == '__main__':
    main()
