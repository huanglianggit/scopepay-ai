import copy
import hashlib
import io
import json
import zipfile
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from api.config import Settings
from api.main import create_app, quote_digest
from api.paypal import approval_url, verified_capture
from api.store import SAMPLE_MESSAGE


@pytest.fixture(autouse=True)
def block_unmocked_external_network(monkeypatch):
    import httpx
    async def blocked(self, request):
        raise AssertionError(f'Unit test attempted an unmocked external request: {request.url.host}')
    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', blocked)


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path/'test.sqlite3'), ai_provider='demo', paypal_id='', paypal_secret='', webhook_id='', owner_code=''), seed=True)
    with TestClient(app) as c:
        assert c.post('/api/session', json={'code': ''}).status_code == 200
        yield c


def draft(client, message=SAMPLE_MESSAGE):
    project = client.get('/api/workspace').json()['projects'][0]
    response = client.post(f'/api/projects/{project["id"]}/analyze', json={'message': message})
    assert response.status_code == 200, response.text
    return response.json()


def quote_payload(change):
    return {'items': [{key: item[key] for key in ('id','title','selected','amount_cents','resolution')} | {'resolution': 'Use an embedded scheduling widget; no custom account or payment system.' if item['kind']=='unclear' else ''} for item in change['items']], 'due_date': change['due_date'], 'note': 'Please review these additions.'}


def published(client):
    change = draft(client)
    response = client.post(f'/api/changes/{change["id"]}/publish', json=quote_payload(change))
    assert response.status_code == 200, response.text
    return response.json()


def accepted(client):
    change = published(client)
    response = client.post(f'/api/review/{change["share_token"]}/respond', json={'action':'accept','name':'Alex Morgan','version':change['version']})
    assert response.status_code == 200, response.text
    return client.app.state.store.change(id=change['id'])


def completed_order(change, amount='340.00', status='COMPLETED'):
    return {'id':change['order_id'],'status':status,'purchase_units':[{'reference_id':change['id'],'custom_id':change['quote_hash'],'payments':{'captures':[{'id':'CAPTURE-123','status':'COMPLETED','amount':{'currency_code':'USD','value':amount}}]}}]}


def test_walkthrough_full_flow_and_export(client):
    change = accepted(client)
    assert change['total_cents'] == 34000
    token = change['share_token']
    paid = client.post(f'/api/review/{token}/demo-payment', json={})
    assert paid.status_code == 200
    assert paid.json()['status'] == 'demo_paid'
    assert client.post(f'/api/review/{token}/demo-payment', json={}).status_code == 200
    assert len([e for e in client.app.state.store.events(change['id']) if e['kind']=='demo_paid']) == 1
    assert client.get(f'/api/review/{token}').json()['status'] == 'demo_paid'
    exported = client.get(f'/api/review/{token}/export')
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        record = json.loads(archive.read('record.json'))
        assert record['total_cents'] == 34000
        assert 'share_token' not in record and 'approval_url' not in record
        assert 'simulated' in archive.read('agreement.md').decode()
        for line in archive.read('checksums.sha256').decode().splitlines():
            digest, name = line.split('  ')
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest


def test_unresolved_ambiguity_prevents_publication(client):
    change=draft(client); payload=quote_payload(change)
    for item in payload['items']:
        item['resolution']=''
    result=client.post(f'/api/changes/{change["id"]}/publish',json=payload)
    assert result.status_code==422
    assert client.app.state.store.change(id=change['id'])['status']=='draft'


def test_quote_lock_and_revision_revokes_old_version(client):
    change=published(client); token=change['share_token']
    assert quote_digest(change)==change['quote_hash']
    assert client.post(f'/api/changes/{change["id"]}/publish',json=quote_payload(change)).status_code==409
    revised=client.post(f'/api/changes/{change["id"]}/revise',json={}).json()
    assert revised['version']==2 and 'share_token' not in revised
    assert client.get(f'/api/review/{token}').json()['status']=='superseded'
    assert client.post(f'/api/review/{token}/respond',json={'action':'accept','name':'Alex','version':1}).status_code==409


def test_accepted_quote_cannot_be_revised_or_overwritten(client):
    change=accepted(client)
    assert client.post(f'/api/changes/{change["id"]}/revise',json={}).status_code==409
    assert client.post(f'/api/review/{change["share_token"]}/respond',json={'action':'decline','name':'Alex','version':1}).status_code==409


def test_decline_allows_new_version(client):
    change=published(client)
    assert client.post(f'/api/review/{change["share_token"]}/respond',json={'action':'decline','name':'Alex','version':1,'note':'Please remove booking.'}).json()['status']=='declined'
    assert client.post(f'/api/changes/{change["id"]}/revise',json={}).json()['version']==2


@pytest.mark.parametrize('mutation', ['negative','float','duplicate','unknown','empty'])
def test_invalid_money_and_items(client,mutation):
    change=draft(client); payload=quote_payload(change)
    if mutation=='negative':payload['items'][0]['amount_cents']=-1
    if mutation=='float':payload['items'][0]['amount_cents']=12.5
    if mutation=='duplicate':payload['items'][1]['id']=payload['items'][0]['id']
    if mutation=='unknown':payload['items'][0]['id']='unknown-item'
    if mutation=='empty':
        for item in payload['items']:item['selected']=False
    assert client.post(f'/api/changes/{change["id"]}/publish',json=payload).status_code==422


def test_unauthorized_and_cross_origin_writes(client):
    assert client.post('/api/projects',json={},headers={'origin':'https://attacker.example'}).status_code==403
    client.cookies.clear()
    assert client.get('/api/workspace').status_code==401
    assert client.get('/api/changes/unknown/export').status_code==401
    assert client.get('/api/status').status_code==200
    assert client.get('/api/review/unknown').status_code==404


def test_owner_access_code(tmp_path):
    app=create_app(Settings(db_path=str(tmp_path/'auth.sqlite3'),owner_code='test-secret'))
    with TestClient(app) as c:
        assert c.post('/api/session',json={'code':'wrong'}).status_code==401
        assert c.post('/api/session',json={'code':'test-secret'}).status_code==200
        assert c.get('/api/workspace').status_code==200


def test_hosted_workspace_requires_owner_code_even_behind_loopback_proxy(tmp_path):
    app=create_app(Settings(db_path=str(tmp_path/'hosted.sqlite3'),owner_code='',public_url='https://studio.example'))
    with TestClient(app) as c:
        assert c.post('/api/session',json={'code':''}).status_code==403


def test_payment_requires_acceptance_and_mode(client):
    change=published(client); token=change['share_token']
    assert client.post(f'/api/review/{token}/order',json={}).status_code==409
    assert client.post(f'/api/review/{token}/demo-payment',json={}).status_code==409
    assert client.post(f'/api/review/{token}/capture',json={'order_id':'FAKE-ORDER'}).status_code==409


def test_sandbox_checkout_uses_server_quote_and_capture_is_idempotent(client):
    settings=client.app.state.settings
    settings.paypal_id='test-id';settings.paypal_secret='test-secret'
    change=accepted(client); token=change['share_token']; payment=client.app.state.paypal
    payment.create_order=AsyncMock(return_value={'id':'ORDER-123','links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER-123'}]})
    payment.get_order=AsyncMock(return_value={'id':'ORDER-123','status':'CREATED','links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER-123'}]})
    result=client.post(f'/api/review/{token}/order',json={})
    assert result.status_code==200
    assert payment.create_order.call_args.args[0]['total_cents']==34000
    assert client.post(f'/api/review/{token}/order',json={}).json()==result.json()
    assert payment.create_order.call_count==1
    change=client.app.state.store.change(id=change['id'])
    payment.get_order=AsyncMock(return_value=completed_order(change))
    payment.capture=AsyncMock()
    result=client.post(f'/api/review/{token}/capture',json={'order_id':'ORDER-123'})
    assert result.status_code==200, result.text
    assert result.json()['status']=='paid'
    assert payment.capture.call_count==0
    assert client.post(f'/api/review/{token}/capture',json={'order_id':'ORDER-123'}).json()['status']=='paid'
    assert len([e for e in client.app.state.store.events(change['id']) if e['kind']=='paid'])==1
    assert client.post(f'/api/review/{token}/demo-payment',json={}).status_code==409


@pytest.mark.parametrize('fault',['amount','currency','version','pending','order'])
def test_payment_verification_rejects_mismatches(client,fault):
    change=accepted(client);change['order_id']='ORDER-123'
    data=completed_order(change)
    if fault=='amount':data['purchase_units'][0]['payments']['captures'][0]['amount']['value']='0.01'
    if fault=='currency':data['purchase_units'][0]['payments']['captures'][0]['amount']['currency_code']='EUR'
    if fault=='version':data['purchase_units'][0]['custom_id']='wrong-version'
    if fault=='pending':data['purchase_units'][0]['payments']['captures'][0]['status']='PENDING'
    if fault=='order':data['id']='OTHER-ORDER'
    with pytest.raises(HTTPException):verified_capture(data,change)


def test_webhook_deduplicates_verified_payment(client):
    settings=client.app.state.settings;settings.paypal_id='id';settings.paypal_secret='secret'
    change=accepted(client);change['order_id']='ORDER-123';client.app.state.store.save_change(change)
    payment=client.app.state.paypal;payment.verify_webhook=AsyncMock(return_value=None);payment.get_order=AsyncMock(return_value=completed_order(change))
    event={'id':'EVENT-1','event_type':'PAYMENT.CAPTURE.COMPLETED','resource':{'supplementary_data':{'related_ids':{'order_id':'ORDER-123'}}}}
    assert client.post('/api/paypal/webhook',json=event).status_code==200
    assert client.post('/api/paypal/webhook',json=event).json()['duplicate'] is True
    assert client.app.state.store.change(id=change['id'])['status']=='paid'
    assert payment.get_order.call_count==1


def test_unsigned_webhook_cannot_mark_quote_paid(client):
    change=accepted(client)
    result=client.post('/api/paypal/webhook',json={'id':'fake-event','event_type':'PAYMENT.CAPTURE.COMPLETED','resource':{}})
    assert result.status_code==503
    assert client.app.state.store.change(id=change['id'])['status']=='accepted'


def test_demo_unknown_request_remains_explicitly_unclear(client):
    change=draft(client,'Please add a complex inventory management system with warehouse sync.')
    assert change['provider']=='demo-rules'
    assert change['items'][0]['kind']=='unclear'
    assert change['items'][0]['amount_cents']==0


def test_chinese_walkthrough_keeps_exact_message_evidence(client):
    message='页面看起来不错！能不能顺便增加中文版本，再加一个在线预约咨询的功能？另外想再多一轮修改。新增预算可以商量。'
    change=draft(client,message)
    assert len(change['items'])==3
    assert all(item['request_quote'] in message for item in change['items'])
    assert any(item['kind']=='unclear' for item in change['items'])


def test_ai_missing_config_is_not_silently_replaced_by_demo(client):
    client.app.state.settings.ai_provider='openai';client.app.state.settings.ai_model=''
    project=client.get('/api/workspace').json()['projects'][0]
    result=client.post(f'/api/projects/{project["id"]}/analyze',json={'message':SAMPLE_MESSAGE})
    assert result.status_code==503
    assert client.get('/api/workspace').json()['changes']==[]


def test_unsafe_approval_url_is_rejected():
    with pytest.raises(HTTPException):approval_url({'links':[{'rel':'approve','href':'https://evil.example/pay'}]})


def test_saved_draft_survives_reload_and_lock_blocks_edits(client):
    change=draft(client);payload=quote_payload(change);payload['items'][0]['amount_cents']=12550
    result=client.post(f'/api/changes/{change["id"]}/draft',json=payload)
    assert result.status_code==200
    restored=client.get('/api/workspace').json()['changes'][0]
    assert restored['items'][0]['amount_cents']==12550
    assert restored['items'][1]['resolution']
    assert client.post(f'/api/changes/{change["id"]}/publish',json=payload).status_code==200
    assert client.post(f'/api/changes/{change["id"]}/draft',json=payload).status_code==409


def test_previously_accepted_additions_inform_next_comparison(client):
    accepted(client)
    repeat=draft(client)
    assert 'Previously confirmed additions' in repeat['project']['scope']
    assert all(i['kind']=='included' and i['amount_cents']==0 and not i['selected'] for i in repeat['items'])


@pytest.mark.parametrize('fault',[None,'request_quote','scope_quote','json','http'])
def test_model_adapter_checks_sources_and_never_silently_falls_back(client,monkeypatch,fault):
    import httpx
    original_client=httpx.AsyncClient
    settings=client.app.state.settings
    settings.ai_provider='openai';settings.ai_model='test-model';settings.ai_url='https://model.test/v1'
    project=client.get('/api/workspace').json()['projects'][0]
    item={'title':'Chinese language version','kind':'added','request_quote':'a Chinese version','scope_quote':'Additional languages, appointment booking, and extra pages are outside the agreed scope.','explanation':'The requested language is outside the agreed scope.','rate_id':'language','question':''}
    if fault=='request_quote':item['request_quote']='invented client message'
    if fault=='scope_quote':item['scope_quote']='invented agreement clause'
    def handler(request):
        assert request.url.path=='/v1/chat/completions'
        payload=json.loads(request.content)
        assert payload['model']=='test-model'
        if fault=='http':return httpx.Response(429,json={'error':'rate limited'})
        content='invalid json' if fault=='json' else json.dumps({'summary':'An additional language is requested.','items':[item]})
        return httpx.Response(200,json={'choices':[{'message':{'content':content}}]})
    transport=httpx.MockTransport(handler)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original_client(transport=transport,**kwargs))
    result=client.post(f'/api/projects/{project["id"]}/analyze',json={'message':SAMPLE_MESSAGE})
    if fault:
        assert result.status_code==502
        assert client.get('/api/workspace').json()['changes']==[]
    else:
        assert result.status_code==200,result.text
        assert result.json()['provider']=='openai:test-model'
        assert result.json()['items'][0]['amount_cents']==12000


def test_paypal_http_adapter_payload_and_token_reuse(client,monkeypatch):
    import asyncio
    import httpx
    original_client=httpx.AsyncClient
    settings=client.app.state.settings;settings.paypal_id='test-client';settings.paypal_secret='test-secret'
    change=accepted(client);payment=client.app.state.paypal;calls=[]
    def handler(request):
        calls.append(request.url.path)
        assert request.url.host=='api-m.sandbox.paypal.com'
        if request.url.path=='/v1/oauth2/token':
            assert request.headers['authorization'].startswith('Basic ')
            return httpx.Response(200,json={'access_token':'test-access-token','expires_in':3600})
        assert request.headers['authorization']=='Bearer test-access-token'
        payload=json.loads(request.content)
        assert payload['purchase_units'][0]['amount']=={'currency_code':'USD','value':'340.00'}
        assert payload['purchase_units'][0]['custom_id']==change['quote_hash']
        assert payload['payment_source']['paypal']['experience_context']['shipping_preference']=='NO_SHIPPING'
        assert request.headers['paypal-request-id']==f"sp-{change['id']}-v1"
        return httpx.Response(201,json={'id':'ORDER-123','links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER-123'}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original_client(transport=httpx.MockTransport(handler),**kwargs))
    asyncio.run(payment.create_order(change));asyncio.run(payment.create_order(change))
    assert calls.count('/v1/oauth2/token')==1
