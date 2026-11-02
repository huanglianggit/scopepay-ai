import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from test_workflow import client, draft, quote_payload, published, accepted, completed_order, block_unmocked_external_network


def sandbox_change(client):
    client.app.state.settings.paypal_id = 'test-id'
    client.app.state.settings.paypal_secret = 'test-secret'
    change = accepted(client)
    change.update(order_id='ORDER-OLD', approval_url='https://www.sandbox.paypal.com/checkoutnow?token=ORDER-OLD')
    client.app.state.store.save_change(change)
    return change


def test_no_charge_change_can_be_confirmed_without_payment(client):
    change = draft(client)
    body = quote_payload(change)
    for item in body['items']:
        item['amount_cents'] = 0
    result = client.post(f'/api/changes/{change["id"]}/publish', json=body)
    assert result.status_code == 200, result.text
    assert result.json()['payment_mode'] == 'none'
    token = result.json()['share_token']
    result = client.post(f'/api/review/{token}/respond', json={'action': 'accept', 'name': 'Alex', 'version': 1})
    assert result.json()['status'] == 'accepted_no_payment'
    assert 'paid_at' not in result.json() and 'capture_id' not in result.json()
    for action in ('order', 'demo-payment', 'payment-status'):
        assert client.post(f'/api/review/{token}/{action}', json={}).status_code == 409
    assert 'Previously confirmed additions' in draft(client)['project']['scope']


def test_stale_draft_cannot_be_published_after_scope_changes(client):
    first = published(client)
    stale = draft(client)
    assert client.post(f'/api/review/{first["share_token"]}/respond', json={'action':'accept','name':'Alex','version':1}).status_code == 200
    result = client.post(f'/api/changes/{stale["id"]}/publish', json=quote_payload(stale))
    assert result.status_code == 409
    assert 'scope changed' in result.json()['detail']
    saved = client.post(f'/api/changes/{stale["id"]}/draft', json=quote_payload(stale))
    assert saved.status_code == 200 and saved.json()['scope_changed'] is True
    data = client.get('/api/workspace').json()
    assert next(c for c in data['changes'] if c['id'] == stale['id'])['scope_changed'] is True


def test_stale_client_link_cannot_accept_and_revision_reanalyzes_current_scope(client):
    first, second = published(client), published(client)
    client.post(f'/api/review/{first["share_token"]}/respond', json={'action':'accept','name':'Alex','version':1})
    token = second['share_token']
    assert client.get(f'/api/review/{token}').json()['scope_changed'] is True
    assert client.post(f'/api/review/{token}/respond', json={'action':'accept','name':'Alex','version':1}).status_code == 409
    assert client.post(f'/api/review/{token}/respond', json={'action':'decline','name':'Alex','version':1,'note':'Please refresh the scope.'}).status_code == 200
    revised = client.post(f'/api/changes/{second["id"]}/revise', json={})
    assert revised.status_code == 200, revised.text
    assert revised.json()['version'] == 2
    assert 'Previously confirmed additions' in revised.json()['project']['scope']
    assert all(i['kind'] == 'included' and i['amount_cents'] == 0 for i in revised.json()['items'])
    assert client.get(f'/api/review/{token}').json()['status'] == 'superseded'


def test_two_concurrent_overlapping_acceptances_do_not_both_succeed(client):
    first, second = published(client), published(client)
    def accept(change):
        return client.post(f'/api/review/{change["share_token"]}/respond', json={'action':'accept','name':'Alex','version':1}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(accept, (first, second)))
    assert sorted(results) == [200, 409]


def test_studio_can_correct_classification_with_auditable_reason(client):
    change = draft(client)
    body = quote_payload(change)
    body['items'][0].update(kind='included', amount_cents=0, resolution='')
    assert client.post(f'/api/changes/{change["id"]}/publish', json=body).status_code == 422
    body['items'][0]['resolution'] = 'The client already supplied the translation; this small addition is included at no charge.'
    saved = client.post(f'/api/changes/{change["id"]}/draft', json=body)
    assert saved.status_code == 200
    assert saved.json()['items'][0]['kind'] == 'included'
    assert saved.json()['items'][0]['analysis_kind'] == 'added'
    result = client.post(f'/api/changes/{change["id"]}/publish', json=body)
    assert result.status_code == 200, result.text
    assert result.json()['total_cents'] == 22000
    assert result.json()['items'][0]['resolution']


def test_corrected_included_work_cannot_have_an_unexplained_fee(client):
    change = draft(client)
    body = quote_payload(change)
    body['items'][0].update(kind='included', resolution='Covered by the original agreement.')
    assert client.post(f'/api/changes/{change["id"]}/publish', json=body).status_code == 422


def test_export_draft_and_declined_records_do_not_claim_acceptance(client):
    change = draft(client)
    response = client.get(f'/api/changes/{change["id"]}/export')
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        text = archive.read('agreement.md').decode()
        assert 'Proposed changes — not accepted' in text
        assert 'No client response has been recorded' in text
    second = published(client)
    token = second['share_token']
    client.post(f'/api/review/{token}/respond', json={'action':'decline','name':'Alex','version':1,'note':'Remove booking please.'})
    with zipfile.ZipFile(io.BytesIO(client.get(f'/api/review/{token}/export').content)) as archive:
        text = archive.read('agreement.md').decode()
        assert 'Proposed changes — not accepted' in text
        assert 'Recorded name: Alex' in text and 'Remove booking please.' in text
        assert 'Response status: declined' in text


def test_export_paid_record_contains_confirmation_and_capture(client):
    change = accepted(client)
    token = change['share_token']
    client.post(f'/api/review/{token}/demo-payment', json={})
    with zipfile.ZipFile(io.BytesIO(client.get(f'/api/review/{token}/export').content)) as archive:
        text = archive.read('agreement.md').decode()
        assert '## Confirmed changes' in text and 'Recorded name: Alex Morgan' in text
        assert change['quote_hash'] in text
        assert f'Capture: DEMO-{change["id"]}' in text
        assert '## Activity' in text


@pytest.mark.parametrize('unavailable', [False, True])
def test_unavailable_sandbox_order_can_start_a_fresh_checkout_attempt(client, unavailable):
    change = sandbox_change(client)
    payment = client.app.state.paypal
    payment.get_order = AsyncMock(side_effect=HTTPException(410, 'Unavailable')) if unavailable else AsyncMock(return_value={'id':'ORDER-OLD','status':'VOIDED'})
    payment.create_order = AsyncMock(return_value={'id':'ORDER-NEW','links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER-NEW'}]})
    result = client.post(f'/api/review/{change["share_token"]}/order', json={})
    assert result.status_code == 200, result.text
    assert result.json()['order_id'] == 'ORDER-NEW'
    latest = client.app.state.store.change(id=change['id'])
    assert latest['order_attempt'] == 2 and latest['quote_hash'] == change['quote_hash']
    assert latest['total_cents'] == 34000 and latest['status'] == 'accepted'


def test_network_error_does_not_replace_an_existing_order(client):
    change = sandbox_change(client)
    payment = client.app.state.paypal
    payment.get_order = AsyncMock(side_effect=HTTPException(502, 'Temporary network error'))
    payment.create_order = AsyncMock()
    result = client.post(f'/api/review/{change["share_token"]}/order', json={})
    assert result.status_code == 502
    assert payment.create_order.call_count == 0
    assert client.app.state.store.change(id=change['id'])['order_id'] == 'ORDER-OLD'


def test_completed_order_is_recovered_without_creating_or_capturing_again(client):
    change = sandbox_change(client)
    payment = client.app.state.paypal
    payment.get_order = AsyncMock(return_value=completed_order(change))
    payment.create_order = AsyncMock(); payment.capture = AsyncMock()
    result = client.post(f'/api/review/{change["share_token"]}/order', json={})
    assert result.status_code == 200, result.text
    assert result.json()['payment']['status'] == 'paid'
    assert payment.create_order.call_count == 0 and payment.capture.call_count == 0


def test_payment_status_refresh_does_not_capture_an_approved_order(client):
    change = sandbox_change(client)
    payment = client.app.state.paypal
    payment.get_order = AsyncMock(return_value={'id':'ORDER-OLD','status':'APPROVED'})
    payment.capture = AsyncMock()
    result = client.post(f'/api/review/{change["share_token"]}/payment-status', json={})
    assert result.json()['status'] == 'accepted'
    assert payment.capture.call_count == 0
    payment.get_order = AsyncMock(return_value=completed_order(change))
    result = client.post(f'/api/review/{change["share_token"]}/payment-status', json={})
    assert result.json()['status'] == 'paid'


def test_explicit_checkout_can_complete_a_previously_approved_order(client):
    change = sandbox_change(client)
    payment = client.app.state.paypal
    payment.get_order = AsyncMock(side_effect=[{'id':'ORDER-OLD','status':'APPROVED'}, completed_order(change)])
    payment.capture = AsyncMock(return_value={'status':'COMPLETED'})
    payment.create_order = AsyncMock()
    result = client.post(f'/api/review/{change["share_token"]}/order', json={})
    assert result.status_code == 200, result.text
    assert result.json()['payment']['status'] == 'paid'
    assert payment.capture.call_count == 1 and payment.create_order.call_count == 0


def test_pending_capture_cannot_trigger_another_checkout(client):
    change = sandbox_change(client)
    pending = completed_order(change)
    pending['purchase_units'][0]['payments']['captures'][0]['status'] = 'PENDING'
    payment = client.app.state.paypal
    payment.get_order = AsyncMock(return_value=pending)
    payment.create_order = AsyncMock(); payment.capture = AsyncMock()
    assert client.post(f'/api/review/{change["share_token"]}/order', json={}).status_code == 409
    assert payment.create_order.call_count == 0 and payment.capture.call_count == 0
    assert client.app.state.store.change(id=change['id'])['status'] == 'accepted'
