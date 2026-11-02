import copy
import hashlib
import io
import json
import zipfile
from datetime import date, timedelta

from api.main import quote_digest
from api.records import project_ledger, revision_comparison, revision_source
from test_workflow import client, draft, quote_payload, published, accepted, block_unmocked_external_network


def revision(client):
    old = published(client)
    client.post(f'/api/review/{old["share_token"]}/respond', json={'action': 'decline', 'name': 'Alex', 'version': 1, 'note': 'Remove booking and move delivery by one day.'})
    result = client.post(f'/api/changes/{old["id"]}/revise', json={})
    assert result.status_code == 200, result.text
    return old, result.json()


def changed_revision(client):
    old, new = revision(client)
    body = quote_payload(new)
    body['items'][0]['amount_cents'] = 12550
    body['items'][1]['selected'] = False
    body['due_date'] = (date.fromisoformat(body['due_date']) + timedelta(days=1)).isoformat()
    body['note'] = 'Booking removed as requested.'
    result = client.post(f'/api/changes/{new["id"]}/draft', json=body)
    assert result.status_code == 200, result.text
    return old, result.json(), body


def test_revision_captures_previous_terms_and_client_feedback(client):
    old, new = revision(client)
    comparison = new['revision']
    assert comparison['previous_version'] == 1
    assert comparison['previous_quote_hash'] == old['quote_hash']
    assert comparison['response_note'] == 'Remove booking and move delivery by one day.'
    assert comparison['has_changes'] is False
    assert new['total_cents'] == old['total_cents']
    source = client.app.state.store.change(id=new['id'])['revision_source']
    assert old['share_token'] not in json.dumps(source)
    assert 'order_id' not in source and 'approval_url' not in source


def test_revision_diff_tracks_fee_removal_date_and_note(client):
    old, new, body = changed_revision(client)
    comparison = new['revision']
    assert comparison['total_cents'] == 16550
    assert comparison['delta_cents'] == -17450
    assert comparison['previous_total_cents'] == 34000
    assert [row['kind'] for row in comparison['items']] == ['modified', 'removed']
    assert comparison['items'][0]['fields'] == ['amount_cents']
    assert comparison['items'][1]['before']['title'] == 'Consultation booking'
    assert {m['field'] for m in comparison['metadata']} == {'due_date', 'note'}
    stored_old = client.app.state.store.change(id=old['id'])
    assert stored_old['items'][0]['amount_cents'] == 12000 and stored_old['items'][1]['selected'] is True
    assert stored_old['status'] == 'superseded'


def test_revision_comparison_survives_publish_acceptance_and_export(client):
    old, change, body = changed_revision(client)
    change = client.post(f'/api/changes/{change["id"]}/publish', json=body).json()
    assert quote_digest(client.app.state.store.change(id=change['id'])) == change['quote_hash']
    token = change['share_token']
    result = client.post(f'/api/review/{token}/respond', json={'action': 'accept', 'name': 'Alex', 'version': 2})
    assert result.status_code == 200
    assert result.json()['revision']['delta_cents'] == -17450
    assert client.post(f'/api/review/{old["share_token"]}/respond', json={'action': 'accept', 'name': 'Alex', 'version': 1}).status_code == 409
    with zipfile.ZipFile(io.BytesIO(client.get(f'/api/review/{token}/export').content)) as archive:
        record = json.loads(archive.read('record.json'))
        text = archive.read('agreement.md').decode()
        assert record['revision']['previous_quote_hash'] == old['quote_hash']
        assert 'Changes since version 1' in text and 'USD -174.50' in text
        assert 'Booking removed as requested.' in text and 'removed: Consultation booking' in text
        assert token not in json.dumps(record) and old['share_token'] not in json.dumps(record)
        assert 'revision_source' not in record


def test_revision_history_is_part_of_locked_quote_fingerprint(client):
    old, change, body = changed_revision(client)
    result = client.post(f'/api/changes/{change["id"]}/publish', json=body).json()
    stored = client.app.state.store.change(id=change['id'])
    stored['revision_source']['response_note'] = 'Tampered historical feedback'
    assert quote_digest(stored) != result['quote_hash']


def test_revision_add_and_remove_selection_are_explicit(client):
    old, change = revision(client)
    source = revision_source(old)
    source['items'][0]['selected'] = False
    change['revision_source'] = source
    result = revision_comparison(change)
    assert result['items'][0]['kind'] == 'added'
    assert result['items'][0]['before'] is None


def test_reanalysis_matches_unique_exact_evidence_not_generated_ids(client):
    old, change = revision(client)
    change['revision_source'] = revision_source(old)
    for item in change['items']:
        item['id'] += '-reanalyzed'
    assert revision_comparison(change)['has_changes'] is False
    change['items'][0]['resolution'] = 'Translation is supplied by the client.'
    result = revision_comparison(change)
    assert len(result['items']) == 1 and result['items'][0]['kind'] == 'modified'
    assert result['items'][0]['fields'] == ['resolution']


def test_ambiguous_evidence_matches_are_shown_as_addition_and_removal(client):
    old, change = revision(client)
    old['items'][1]['request_quote'] = old['items'][0]['request_quote']
    old['items'][1]['rate_id'] = old['items'][0]['rate_id']
    change['items'] = copy.deepcopy(old['items'])
    change['revision_source'] = revision_source(old)
    for item in change['items']:
        item['id'] += '-new'
    result = revision_comparison(change)
    assert [row['kind'] for row in result['items']].count('added') == 2
    assert [row['kind'] for row in result['items']].count('removed') == 2


def test_stale_revision_flags_new_baseline(client):
    first, old = published(client), published(client)
    client.post(f'/api/review/{first["share_token"]}/respond', json={'action': 'accept', 'name': 'Alex', 'version': 1})
    new = client.post(f'/api/changes/{old["id"]}/revise', json={}).json()
    assert new['revision']['baseline_changed'] is True
    assert new['revision']['total_cents'] == 0
    assert new['revision']['has_changes'] is True


def test_ledger_separates_confirmed_unpaid_simulated_and_unaccepted_quotes(client):
    first, stale = published(client), published(client)
    client.post(f'/api/review/{first["share_token"]}/respond', json={'action': 'accept', 'name': 'Alex', 'version': 1})
    pending = draft(client, 'Could we add another page for the team?')
    client.post(f'/api/changes/{pending["id"]}/publish', json=quote_payload(pending))
    url = f'/api/projects/{first["project_id"]}/ledger'
    result = client.get(url)
    assert result.status_code == 200, result.text
    data = result.json()
    totals = data['totals']
    assert totals['agreed_project_cents'] == 84000
    assert totals['confirmed_additional_cents'] == totals['demo_unpaid_cents'] == 34000
    assert totals['awaiting_cents'] == 8000 and totals['awaiting_count'] == 1 and totals['stale_count'] == 1
    assert totals['sandbox_paid_cents'] == totals['demo_paid_cents'] == totals['sandbox_unpaid_cents'] == 0
    assert len(data['confirmed']) == 1 and data['confirmed'][0]['confirmed_by'] == 'Alex'
    assert first['share_token'] not in json.dumps(data) and stale['share_token'] not in json.dumps(data)
    client.post(f'/api/review/{first["share_token"]}/demo-payment', json={})
    totals = client.get(url).json()['totals']
    assert totals['demo_paid_cents'] == 34000 and totals['demo_unpaid_cents'] == totals['sandbox_paid_cents'] == 0


def test_ledger_math_never_treats_proposals_or_simulations_as_verified_revenue(client):
    base = accepted(client)
    rows = []
    for index, (status, mode, cents) in enumerate([('paid', 'sandbox', 10000), ('demo_paid', 'demo', 20000), ('accepted', 'sandbox', 30000), ('accepted', 'demo', 40000), ('accepted_no_payment', 'none', 0), ('draft', 'demo', 90000), ('declined', 'demo', 90000), ('superseded', 'demo', 90000), ('awaiting', 'sandbox', 50000)]):
        row = copy.deepcopy(base)
        row.update(id=f'change-{index}', status=status, payment_mode=mode, total_cents=cents)
        rows.append(row)
    record = project_ledger(base['project'], rows, set())
    assert record['totals']['agreed_project_cents'] == base['project']['base_cents'] + 100000
    assert record['totals']['sandbox_paid_cents'] == 10000
    assert record['totals']['demo_paid_cents'] == 20000
    assert record['totals']['sandbox_unpaid_cents'] == 30000
    assert record['totals']['demo_unpaid_cents'] == 40000
    assert len(record['confirmed']) == 5


def test_ledger_exports_confirmed_scope_and_valid_checksums(client):
    change = accepted(client)
    result = client.get(f'/api/projects/{change["project_id"]}/ledger/export')
    assert result.status_code == 200
    with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
        assert set(archive.namelist()) == {'project-summary.md', 'ledger.json', 'checksums.sha256'}
        text = archive.read('project-summary.md').decode()
        assert 'Agreed project value (not revenue): USD 840.00' in text
        assert 'Confirmed by: Alex Morgan' in text and 'neither is live revenue' in text
        assert change['share_token'] not in archive.read('ledger.json').decode()
        for line in archive.read('checksums.sha256').decode().splitlines():
            digest, name = line.split('  ')
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest


def test_ledger_requires_owner_and_handles_missing_project(client):
    assert client.get('/api/projects/missing/ledger').status_code == 404
    assert client.get('/api/projects/missing/ledger/export').status_code == 404
    project = client.get('/api/workspace').json()['projects'][0]
    client.cookies.clear()
    assert client.get(f'/api/projects/{project["id"]}/ledger').status_code == 401
    assert client.get(f'/api/projects/{project["id"]}/ledger/export').status_code == 401


def test_empty_ledger_and_project_isolation(client):
    change = accepted(client)
    body = {key: change['project'][key] for key in ('title', 'client_name', 'scope', 'base_cents', 'due_date')}
    other = client.post('/api/projects', json=body).json()
    data = client.get(f'/api/projects/{other["id"]}/ledger').json()
    assert data['totals']['agreed_project_cents'] == body['base_cents']
    assert data['totals']['confirmed_additional_cents'] == 0 and data['confirmed'] == []


def test_first_version_needs_no_comparison_and_legacy_hash_stays_valid(client):
    change = published(client)
    assert change['revision'] is None
    assert quote_digest(change) == change['quote_hash']


def test_payment_environment_change_is_visible_in_revision(client):
    old, new = revision(client)
    client.app.state.settings.paypal_id = 'sandbox-id'
    client.app.state.settings.paypal_secret = 'sandbox-secret'
    result = client.post(f'/api/changes/{new["id"]}/publish', json=quote_payload(new))
    assert result.status_code == 200
    assert result.json()['payment_mode'] == 'sandbox'
    assert result.json()['revision']['metadata'] == [{'field': 'payment_mode', 'before': 'demo', 'after': 'sandbox'}]
    third = client.post(f'/api/changes/{new["id"]}/revise', json={}).json()
    assert third['revision']['previous_version'] == 2
    assert third['revision']['previous_quote_hash'] == result.json()['quote_hash']


def test_zero_fee_confirmation_in_ledger_does_not_invent_payments(client):
    change = draft(client)
    body = quote_payload(change)
    for item in body['items']:
        item['amount_cents'] = 0
    change = client.post(f'/api/changes/{change["id"]}/publish', json=body).json()
    client.post(f'/api/review/{change["share_token"]}/respond', json={'action': 'accept', 'name': 'Alex', 'version': 1})
    record = client.get(f'/api/projects/{change["project_id"]}/ledger').json()
    assert len(record['confirmed']) == 1
    assert record['confirmed'][0]['status'] == 'accepted_no_payment'
    assert record['totals']['agreed_project_cents'] == change['project']['base_cents']
    assert all(record['totals'][key] == 0 for key in ('sandbox_paid_cents', 'demo_paid_cents', 'sandbox_unpaid_cents', 'demo_unpaid_cents'))
