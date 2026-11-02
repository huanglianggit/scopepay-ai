import time
from decimal import Decimal
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException

SANDBOX = 'https://api-m.sandbox.paypal.com'


class PayPal:
    def __init__(self, settings):
        self.settings = settings
        self.access_token = ''
        self.expires = 0

    async def token(self):
        if not self.settings.paypal_ready:
            raise HTTPException(503, 'PayPal Sandbox credentials are not configured.')
        if self.access_token and self.expires > time.time():
            return self.access_token
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(f'{SANDBOX}/v1/oauth2/token', auth=(self.settings.paypal_id, self.settings.paypal_secret), data={'grant_type': 'client_credentials'})
            response.raise_for_status()
            data = response.json()
            self.access_token = data['access_token']
            self.expires = time.time() + data.get('expires_in', 300) - 30
            return self.access_token
        except (httpx.HTTPError, ValueError, KeyError):
            raise HTTPException(502, 'PayPal Sandbox authentication failed. Check the Sandbox client ID and secret.')

    async def request(self, method, path, body=None, request_id=None):
        headers = {'Authorization': f'Bearer {await self.token()}', 'Content-Type': 'application/json', 'Prefer': 'return=representation'}
        if request_id:
            headers['PayPal-Request-Id'] = request_id
        try:
            async with httpx.AsyncClient(timeout=35) as client:
                response = await client.request(method, f'{SANDBOX}{path}', json=body, headers=headers)
            if response.status_code >= 400:
                if method == 'GET' and path.startswith('/v2/checkout/orders/') and response.status_code == 404:
                    raise HTTPException(410, 'This Sandbox order is no longer available.')
                try:
                    code = response.json().get('details', [{}])[0].get('issue', 'PAYPAL_ERROR')
                    code = str(code)[:100]
                except (ValueError, IndexError, AttributeError):
                    code = 'PAYPAL_ERROR'
                raise HTTPException(502, f'PayPal Sandbox: {code}. Your quote is preserved; try again or check the Sandbox account.')
            return response.json()
        except httpx.HTTPError:
            raise HTTPException(502, 'PayPal Sandbox could not be reached. Retry to recover the same order.')

    async def create_order(self, change):
        token = change['share_token']
        base = f'{self.settings.public_url}/review/{token}'
        return await self.request('POST', '/v2/checkout/orders', {
            'intent': 'CAPTURE',
            'purchase_units': [{'reference_id': change['id'], 'custom_id': change['quote_hash'], 'description': f"ScopePay change v{change['version']} · {change['project']['title']}"[:127], 'amount': {'currency_code': 'USD', 'value': f"{Decimal(change['total_cents']) / 100:.2f}"}}],
            'payment_source': {'paypal': {'experience_context': {'brand_name': 'ScopePay', 'shipping_preference': 'NO_SHIPPING', 'user_action': 'PAY_NOW', 'return_url': base + '?checkout=return', 'cancel_url': base + '?checkout=cancel'}}},
        }, request_id=f"sp-{change['id']}-v{change['version']}" + (f"-a{change['order_attempt']}" if change.get('order_attempt', 1) > 1 else ''))

    async def capture(self, order_id, change):
        return await self.request('POST', f'/v2/checkout/orders/{order_id}/capture', {}, request_id=f"capture-{change['id']}" + (f"-a{change['order_attempt']}" if change.get('order_attempt', 1) > 1 else ''))

    async def get_order(self, order_id):
        return await self.request('GET', f'/v2/checkout/orders/{order_id}')

    async def verify_webhook(self, headers, event):
        if not self.settings.webhook_id:
            raise HTTPException(503, 'PAYPAL_WEBHOOK_ID is not configured.')
        result = await self.request('POST', '/v1/notifications/verify-webhook-signature', {
            'auth_algo': headers.get('paypal-auth-algo'), 'cert_url': headers.get('paypal-cert-url'),
            'transmission_id': headers.get('paypal-transmission-id'), 'transmission_sig': headers.get('paypal-transmission-sig'),
            'transmission_time': headers.get('paypal-transmission-time'), 'webhook_id': self.settings.webhook_id, 'webhook_event': event,
        })
        if result.get('verification_status') != 'SUCCESS':
            raise HTTPException(400, 'Webhook signature verification failed.')


def approval_url(order):
    for link in order.get('links', []):
        if link.get('rel') in ('approve', 'payer-action'):
            parsed = urlparse(link['href'])
            if parsed.scheme == 'https' and parsed.hostname in ('www.sandbox.paypal.com', 'sandbox.paypal.com'):
                return link['href']
    raise HTTPException(502, 'PayPal did not return a Sandbox approval URL.')


def verified_capture(order, change):
    if order.get('id') != change.get('order_id') or order.get('status') != 'COMPLETED':
        raise HTTPException(409, 'This Sandbox order is not completed. Approval alone does not confirm payment.')
    units = order.get('purchase_units', [])
    if len(units) != 1:
        raise HTTPException(409, 'Unexpected purchase units in the payment.')
    unit = units[0]
    if unit.get('custom_id') != change['quote_hash'] or unit.get('reference_id') != change['id']:
        raise HTTPException(409, 'Payment does not match the confirmed quote version.')
    captures = unit.get('payments', {}).get('captures', [])
    valid = [c for c in captures if c.get('status') == 'COMPLETED']
    if len(valid) != 1:
        raise HTTPException(409, 'A completed capture is required before marking this quote paid.')
    capture = valid[0]
    try:
        cents = Decimal(capture['amount']['value']) * 100
        matches = cents == change['total_cents'] and capture['amount']['currency_code'] == 'USD'
    except (KeyError, ValueError, ArithmeticError):
        matches = False
    if not matches:
        raise HTTPException(409, 'The captured amount or currency does not match the quote.')
    return capture['id']
