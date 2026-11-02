"""Explicitly scoped public API regression. Never initiates checkout or capture."""
import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile
import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/regression-2026-11-02'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'https://47.79.243.86:18080'
code = dotenv_values(ROOT / '.env')['OWNER_ACCESS_CODE']
results = []
private = {}


def check(name, condition):
    results.append({'check': name, 'passed': bool(condition)})
    (OUT / 'api-regression.json').write_text(json.dumps({'base': BASE, 'checks': results, 'checkout_or_capture_initiated': False}, indent=2))
    if not condition:
        raise RuntimeError('Regression failed: ' + name)
    print('PASS ' + name, flush=True)


def payload(change, cents):
    items = copy.deepcopy(change['items'])
    selected = next((item for item in items if item['kind'] != 'included'), items[0])
    for item in items:
        item['selected'] = item['id'] == selected['id']
        item['amount_cents'] = cents if item['selected'] else 0
        item['resolution'] = 'One Spanish landing-page variant using client-supplied copy. No booking, custom accounts, or payment backend.'
    return {'items': [{k: i[k] for k in ('id', 'title', 'selected', 'amount_cents', 'resolution')} for i in items], 'due_date': change['due_date'], 'note': 'Synthetic hosted regression only; PayPal Sandbox test funds.'}


def verify_zip(response):
    if response.status_code != 200:
        return False
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        for row in z.read('checksums.sha256').decode().splitlines():
            digest, name = row.split('  ', 1)
            if hashlib.sha256(z.read(name)).hexdigest() != digest:
                return False
        record_name = 'record.json' if 'record.json' in z.namelist() else 'ledger.json'
        record = z.read(record_name)
        return b'share_token' not in record and code.encode() not in record


with httpx.Client(base_url=BASE, timeout=130, follow_redirects=False) as client:
    check('anonymous workspace denied', client.get('/api/workspace').status_code == 401)
    login = client.post('/api/session', json={'code': code}, headers={'Origin': BASE})
    check('owner HTTPS login', login.status_code == 200)
    cookie_headers = login.headers.get_list('set-cookie')
    check('owner cookie is secure and httponly', bool(cookie_headers) and all('Secure' in h and 'HttpOnly' in h for h in cookie_headers))
    check('authenticated workspace', client.get('/api/workspace').status_code == 200)
    check('untrusted origin denied', client.post('/api/projects', json={}, headers={'Origin': 'https://untrusted.example'}).status_code == 403)
    check('oversized request denied', client.post('/api/projects', content=b'x' * 128001, headers={'Content-Type': 'application/json'}).status_code == 413)
    for case, cents in [('payment', 1200), ('no-charge', 0)]:
        response = client.post('/api/projects', json={'title': 'Harbor ' + case + ' public regression 2026-11-02', 'client_name': 'Jordan Demo', 'client_email': 'jordan@example.com', 'scope': 'One responsive English landing page, including a contact form and two revision rounds. Spanish translation, extra pages and booking are excluded.', 'base_cents': 50000, 'due_date': '2026-11-20'})
        check(case + ': create synthetic project', response.status_code == 200)
        project = response.json()
        response = client.post('/api/projects/' + project['id'] + '/analyze', json={'message': 'Please add a Spanish version of the landing page. I will provide the translated copy.'})
        check(case + ': real model and source validation', response.status_code == 200 and response.json().get('provider', '').startswith('openai:'))
        change = response.json()
        body = payload(change, cents)
        check(case + ': draft saved', client.post('/api/changes/' + change['id'] + '/draft', json=body).status_code == 200)
        check(case + ': draft persisted', any(c['id'] == change['id'] and c['total_cents'] == cents for c in client.get('/api/workspace').json()['changes']))
        response = client.post('/api/changes/' + change['id'] + '/publish', json=body)
        check(case + ': publish locked quote', response.status_code == 200)
        locked = response.json()
        token = locked['share_token']
        check(case + ': published draft immutable', client.post('/api/changes/' + change['id'] + '/draft', json=body).status_code == 409)
        check(case + ': payment before acceptance blocked', client.post('/api/review/' + token + '/order', json={}).status_code == 409)
        if case == 'payment':
            check('payment: client revision feedback', client.post('/api/review/' + token + '/respond', json={'action': 'decline', 'name': 'Jordan Demo', 'version': locked['version'], 'note': 'Please clarify that only one landing page is translated.'}).status_code == 200)
            response = client.post('/api/changes/' + locked['id'] + '/revise', json={})
            check('payment: new revision created', response.status_code == 200)
            revision = response.json()
            check('payment: replaced client link cannot accept', client.post('/api/review/' + token + '/respond', json={'action': 'accept', 'name': 'Jordan Demo', 'version': locked['version']}).status_code == 409)
            body = payload(revision, cents)
            body['note'] = 'Version 2: exactly one Spanish landing page; supplied copy; Sandbox regression only.'
            response = client.post('/api/changes/' + revision['id'] + '/publish', json=body)
            check('payment: republish revised quote', response.status_code == 200)
            locked = response.json()
            token = locked['share_token']
        response = client.post('/api/review/' + token + '/respond', json={'action': 'accept', 'name': 'Jordan Demo', 'version': locked['version'], 'note': 'Synthetic regression acceptance only.'})
        expected = 'accepted' if cents else 'accepted_no_payment'
        check(case + ': exact version accepted', response.status_code == 200 and response.json()['status'] == expected)
        check(case + ': duplicate acceptance rejected', client.post('/api/review/' + token + '/respond', json={'action': 'accept', 'name': 'Jordan Demo', 'version': locked['version']}).status_code == 409)
        check(case + ': client export checksums and secret exclusion', verify_zip(client.get('/api/review/' + token + '/export')))
        check(case + ': owner ledger export', verify_zip(client.get('/api/projects/' + project['id'] + '/ledger/export')))
        if cents:
            check('payment: no fake paid state', client.get('/api/review/' + token).json()['status'] == 'accepted')
            private['review_url'] = BASE + '/review/' + token
            private['change_id'] = locked['id']
            private['project_id'] = project['id']
            private['amount_usd'] = '12.00'
        else:
            check('no-charge: checkout refused', client.post('/api/review/' + token + '/order', json={}).status_code == 409)
    (OUT / 'private-payment-handoff.json').write_text(json.dumps(private, indent=2))
print('HOSTED_API_REGRESSION_COMPLETE; buyer checkout remains manual', flush=True)
