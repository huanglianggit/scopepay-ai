import copy
from collections import Counter


CONFIRMED = {'accepted', 'accepted_no_payment', 'paid', 'demo_paid'}
ITEM_FIELDS = ('id', 'title', 'kind', 'selected', 'amount_cents', 'resolution', 'request_quote', 'rate_id')
EDIT_FIELDS = ('title', 'kind', 'amount_cents', 'resolution')


def revision_source(change):
    """Freeze only the previous terms needed for comparison, never access tokens."""
    return {
        'version': change['version'], 'quote_hash': change['quote_hash'],
        'items': [{key: copy.deepcopy(item[key]) for key in ITEM_FIELDS} for item in change['items']],
        'due_date': change['due_date'], 'note': change.get('note', ''),
        'scope': change['project']['scope'], 'payment_mode': change['payment_mode'],
        'response_note': change.get('response', {}).get('note', ''),
    }


def revision_comparison(change):
    previous = change.get('revision_source')
    if not previous:
        return None
    old_items, new_items = previous['items'], change['items']
    old_by_id = {item['id']: item for item in old_items}
    old_counts = Counter((i['request_quote'], i['rate_id']) for i in old_items)
    new_counts = Counter((i['request_quote'], i['rate_id']) for i in new_items)
    old_by_evidence = {(i['request_quote'], i['rate_id']): i for i in old_items}
    used, rows = set(), []

    def terms(item):
        return {key: item[key] for key in ('title', 'kind', 'amount_cents', 'resolution')}

    for item in new_items:
        old = old_by_id.get(item['id'])
        key = (item['request_quote'], item['rate_id'])
        # Reanalysis creates new IDs. Match only unique exact evidence/category;
        # ambiguous matches remain explicit removal/addition, never a fuzzy guess.
        if old is None and old_counts[key] == new_counts[key] == 1:
            old = old_by_evidence[key]
        if old is not None and old['id'] in used:
            old = None
        if old is not None:
            used.add(old['id'])
        if item['selected'] and (old is None or not old['selected']):
            rows.append({'kind': 'added', 'before': None, 'after': terms(item), 'fields': []})
        elif old is not None and old['selected'] and not item['selected']:
            rows.append({'kind': 'removed', 'before': terms(old), 'after': None, 'fields': []})
        elif old is not None and old['selected'] and item['selected']:
            fields = [key for key in EDIT_FIELDS if old[key] != item[key]]
            if fields:
                rows.append({'kind': 'modified', 'before': terms(old), 'after': terms(item), 'fields': fields})
    for old in old_items:
        if old['selected'] and old['id'] not in used:
            rows.append({'kind': 'removed', 'before': terms(old), 'after': None, 'fields': []})
    metadata = []
    for field in ('due_date', 'note'):
        if previous[field] != change.get(field, ''):
            metadata.append({'field': field, 'before': previous[field], 'after': change.get(field, '')})
    if change.get('payment_mode') and previous['payment_mode'] != change['payment_mode']:
        metadata.append({'field': 'payment_mode', 'before': previous['payment_mode'], 'after': change['payment_mode']})
    old_total = sum(i['amount_cents'] for i in old_items if i['selected'])
    new_total = sum(i['amount_cents'] for i in new_items if i['selected'])
    baseline_changed = previous['scope'] != change['project']['scope']
    return {
        'previous_version': previous['version'], 'previous_quote_hash': previous['quote_hash'],
        'previous_total_cents': old_total, 'total_cents': new_total, 'delta_cents': new_total - old_total,
        'items': rows, 'metadata': metadata, 'baseline_changed': baseline_changed,
        'response_note': previous['response_note'],
        'has_changes': bool(rows or metadata or baseline_changed),
    }


def project_ledger(project, changes, stale_ids):
    confirmed = [change for change in changes if change['status'] in CONFIRMED]
    pending = [change for change in changes if change['status'] == 'awaiting' and change['id'] not in stale_ids]
    stale = [change for change in changes if change['status'] == 'awaiting' and change['id'] in stale_ids]

    def total(predicate):
        return sum(c['total_cents'] for c in confirmed if predicate(c))

    additional = total(lambda c: True)
    return {
        'project': {key: project[key] for key in ('id', 'title', 'client_name', 'currency', 'scope', 'base_cents', 'due_date')},
        'totals': {
            'confirmed_additional_cents': additional,
            'agreed_project_cents': project['base_cents'] + additional,
            'sandbox_paid_cents': total(lambda c: c['status'] == 'paid' and c.get('payment_mode') == 'sandbox'),
            'demo_paid_cents': total(lambda c: c['status'] == 'demo_paid' and c.get('payment_mode') == 'demo'),
            'sandbox_unpaid_cents': total(lambda c: c['status'] == 'accepted' and c.get('payment_mode') == 'sandbox'),
            'demo_unpaid_cents': total(lambda c: c['status'] == 'accepted' and c.get('payment_mode') == 'demo'),
            'awaiting_cents': sum(c['total_cents'] for c in pending),
            'awaiting_count': len(pending), 'stale_count': len(stale),
        },
        'confirmed': [{
            'id': c['id'], 'version': c['version'], 'status': c['status'], 'payment_mode': c.get('payment_mode'),
            'total_cents': c['total_cents'], 'due_date': c['due_date'], 'quote_hash': c['quote_hash'],
            'confirmed_at': c['response']['at'], 'confirmed_by': c['response']['name'],
            'items': [{key: i[key] for key in ('title', 'kind', 'resolution', 'amount_cents')} for i in c['items'] if i['selected']],
        } for c in confirmed],
        'notice': 'USD test environment only. The original fee is recorded, not payment-tracked. Simulated and Sandbox payments are separate; neither is live revenue. Unaccepted proposals are excluded from the agreed total.',
    }
