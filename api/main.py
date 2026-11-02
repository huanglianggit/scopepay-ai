import asyncio
import copy
import hashlib
import hmac
import io
import json
import secrets
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import FileResponse, JSONResponse, Response
from .analysis import analyze
from .config import Settings, ROOT
from .models import ProjectInput, AnalyzeInput, PublishInput, RespondInput, CaptureInput, LoginInput
from .paypal import PayPal, approval_url, verified_capture
from .store import Store, now, uid, RATES, SAMPLE_MESSAGE
from .records import project_ledger, revision_source, revision_comparison


def quote_digest(change):
    payload = {key: change[key] for key in ('id', 'version', 'project', 'items', 'total_cents', 'due_date', 'note', 'payment_mode')}
    if change.get('revision_source'):
        payload['revision_source'] = change['revision_source']
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def public_record(change, events):
    keys = ('id', 'version', 'project', 'message', 'summary', 'provider', 'items', 'total_cents', 'due_date', 'note', 'status', 'payment_mode', 'quote_hash', 'created_at', 'published_at', 'response', 'paid_at', 'capture_id')
    return {**{key: change[key] for key in keys if key in change}, 'events': events, 'revision': revision_comparison(change)}


def zip_response(entries, filename):
    entries['checksums.sha256'] = '\n'.join(f'{hashlib.sha256(value).hexdigest()}  {name}' for name, value in entries.items()).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return Response(buffer.getvalue(), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


def create_app(settings=None, seed=True):
    settings = settings or Settings()
    store = Store(settings.db_path)
    if seed:
        store.seed()
    paypal = PayPal(settings)
    app = FastAPI(title='ScopePay AI', version='0.1.0', docs_url='/api/docs')
    app.state.store, app.state.paypal, app.state.settings = store, paypal, settings
    locks = {}

    def lock(id):
        return locks.setdefault(id, asyncio.Lock())

    @app.middleware('http')
    async def boundary(request, call_next):
        allowed = {settings.public_url, 'http://127.0.0.1:5191', 'http://localhost:5191'}
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.url.path != '/api/paypal/webhook':
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') not in allowed:
                return JSONResponse({'detail': 'This origin is not allowed.'}, status_code=403)
        try:
            too_large = int(request.headers.get('content-length', '0')) > 128000
        except ValueError:
            too_large = True
        if too_large:
            return JSONResponse({'detail': 'Request is too large.'}, status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.url.path.startswith('/api') or request.url.path.startswith('/review'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def owner(request: Request):
        if not store.authenticated(request.cookies.get('scopepay_owner', '')):
            raise HTTPException(401, 'Sign in to your studio workspace.')

    def change_by_id(id):
        change = store.change(id=id)
        if not change:
            raise HTTPException(404, 'Change request not found.')
        return change

    def change_by_token(token):
        change = store.change(token=token)
        if not change or change['status'] == 'draft':
            raise HTTPException(404, 'This review link is unavailable.')
        return change

    def baseline_project(project):
        snapshot = copy.deepcopy(project)
        accepted = [c for c in reversed(store.changes(project['id'])) if c['status'] in ('accepted', 'paid', 'demo_paid', 'accepted_no_payment')]
        if accepted:
            additions = []
            for change in accepted:
                for item in change['items']:
                    if item['selected']:
                        additions.append(f"Confirmed addition: {item['title']}. {item['resolution']} [Change {change['id']}, version {change['version']}]")
            snapshot['scope'] += '\n\nPreviously confirmed additions:\n' + '\n'.join(additions)
        return snapshot

    def scope_changed(change):
        project = store.project(change['project_id'])
        return project is None or baseline_project(project)['scope'] != change['project']['scope']

    def editable_items(change, body, publishing=False):
        try:
            date.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(422, 'Enter a valid delivery date.')
        original = {item['id']: item for item in change['items']}
        if len(body.items) != len(original) or {i.id for i in body.items} != set(original):
            raise HTTPException(422, 'Quote items must match the analysis, with no duplicates.')
        items = []
        for edited in body.items:
            previous = original[edited.id]
            item = {**previous, 'analysis_kind': previous.get('analysis_kind', previous['kind']), **edited.model_dump(exclude_none=True)}
            if publishing and item['selected']:
                if item['kind'] == 'unclear' and not item['resolution']:
                    raise HTTPException(422, f"Resolve the question for: {item['title']}")
                if item['kind'] != item['analysis_kind'] and not item['resolution']:
                    raise HTTPException(422, f"Explain the classification correction for: {item['title']}")
                if item['kind'] == 'included' and item['amount_cents']:
                    raise HTTPException(422, 'Already-included work must remain free. Classify genuinely new work and explain the correction before quoting a fee.')
            items.append(item)
        return items

    @app.get('/api/status')
    def status():
        return {'paypal_ready': settings.paypal_ready, 'ai_ready': settings.ai_ready, 'ai_provider': settings.ai_provider, 'ai_model': settings.ai_model if settings.ai_ready else '', 'webhook_ready': bool(settings.webhook_id), 'payment_environment': 'sandbox', 'sample_message': SAMPLE_MESSAGE}

    @app.post('/api/session')
    def login(body: LoginInput, request: Request):
        local = request.client and request.client.host in ('127.0.0.1', '::1', 'testclient') and urlparse(settings.public_url).hostname in ('127.0.0.1', 'localhost', '::1')
        if settings.owner_code:
            if not hmac.compare_digest(body.code, settings.owner_code):
                raise HTTPException(401, 'Enter the studio access code configured on the server.')
        elif not local:
            raise HTTPException(403, 'Set OWNER_ACCESS_CODE on the server before opening a hosted studio.')
        response = JSONResponse({'ok': True})
        response.set_cookie('scopepay_owner', store.session(), httponly=True, samesite='strict', secure=settings.public_url.startswith('https://'), max_age=604800)
        return response

    @app.get('/api/workspace', dependencies=[Depends(owner)])
    def workspace():
        changes = store.changes()
        for change in changes:
            change['scope_changed'] = change['status'] in ('draft', 'awaiting', 'declined') and scope_changed(change)
            change['revision'] = revision_comparison(change)
        return {'projects': store.projects(), 'changes': changes}

    def ledger(project_id):
        project = store.project(project_id)
        if not project:
            raise HTTPException(404, 'Project not found.')
        changes = store.changes(project_id)
        stale = {c['id'] for c in changes if c['status'] == 'awaiting' and scope_changed(c)}
        return {**project_ledger(project, changes, stale), 'generated_at': now()}

    @app.get('/api/projects/{project_id}/ledger', dependencies=[Depends(owner)])
    def get_ledger(project_id: str):
        return ledger(project_id)

    @app.get('/api/projects/{project_id}/ledger/export', dependencies=[Depends(owner)])
    def export_ledger(project_id: str):
        record = ledger(project_id)
        totals, project = record['totals'], record['project']
        lines = ['# ScopePay project scope and fees', '', f"Project: {project['title']}", f"Client: {project['client_name']}", f"Generated: {record['generated_at']}", '', record['notice'], '', '## Recorded fees']
        labels = {'agreed_project_cents': 'Agreed project value (not revenue)', 'confirmed_additional_cents': 'Confirmed additional fees', 'sandbox_paid_cents': 'Verified Sandbox captures (test money)', 'sandbox_unpaid_cents': 'Accepted Sandbox fees, unpaid', 'demo_paid_cents': 'Simulated payments (not money)', 'demo_unpaid_cents': 'Accepted demo fees, unpaid', 'awaiting_cents': 'Unaccepted current proposals (not agreed)'}
        lines.append(f"Original fee (not payment-tracked): USD {project['base_cents'] / 100:.2f}")
        lines += [f"{label}: USD {totals[key] / 100:.2f}" for key, label in labels.items()]
        lines += [f"Stale unaccepted quotes excluded: {totals['stale_count']}", '', '## Original scope', project['scope'], '', '## Confirmed changes']
        if not record['confirmed']:
            lines.append('No changes have been confirmed. Proposals are not agreements.')
        for change in record['confirmed']:
            lines += ['', f"### {change['id']} — version {change['version']}", f"Status: {change['status']} / {change['payment_mode']}", f"Confirmed by: {change['confirmed_by']} at {change['confirmed_at']}", f"Fee: USD {change['total_cents'] / 100:.2f}", f"Delivery for this change: {change['due_date']}", f"Quote SHA-256: {change['quote_hash']}"]
            lines += [f"- {i['title']}: USD {i['amount_cents'] / 100:.2f}. {i['resolution']}" for i in change['items']]
        return zip_response({'project-summary.md': '\n'.join(lines).encode(), 'ledger.json': json.dumps(record, ensure_ascii=False, indent=2).encode()}, f'scopepay-{project_id}-summary.zip')

    @app.post('/api/projects', dependencies=[Depends(owner)])
    def create_project(body: ProjectInput):
        try:
            date.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(422, 'Enter a valid delivery date.')
        project = {**body.model_dump(), 'id': uid('project'), 'currency': 'USD', 'rates': copy.deepcopy(RATES), 'created_at': now()}
        store.save_project(project)
        return project

    @app.post('/api/projects/{project_id}/analyze', dependencies=[Depends(owner)])
    async def analyze_request(project_id: str, body: AnalyzeInput):
        project = store.project(project_id)
        if not project:
            raise HTTPException(404, 'Project not found.')
        project = baseline_project(project)
        analysis = await analyze(settings, project, body.message)
        change = {'id': uid('change'), 'project_id': project_id, 'project': copy.deepcopy(project), 'message': body.message, **analysis, 'version': 1, 'status': 'draft', 'total_cents': 0, 'due_date': project['due_date'], 'note': '', 'created_at': now()}
        store.save_change(change)
        store.event(change['id'], 'draft', 'Change analysis prepared; studio review required.')
        return change

    @app.post('/api/changes/{id}/draft', dependencies=[Depends(owner)])
    async def save_draft(id: str, body: PublishInput):
        async with lock(id):
            change = change_by_id(id)
            if change['status'] != 'draft':
                raise HTTPException(409, 'This version is locked and can no longer be edited.')
            change['items'] = editable_items(change, body)
            change.update(due_date=body.due_date, note=body.note, total_cents=sum(i['amount_cents'] for i in change['items'] if i['selected']))
            store.save_change(change)
            return {**change, 'scope_changed': scope_changed(change), 'revision': revision_comparison(change)}

    @app.post('/api/changes/{id}/publish', dependencies=[Depends(owner)])
    async def publish(id: str, body: PublishInput):
        initial = change_by_id(id)
        async with lock('project:' + initial['project_id']):
            change = change_by_id(id)
            if change['status'] != 'draft':
                raise HTTPException(409, 'This version is already locked. Create a revision to change it.')
            if scope_changed(change):
                raise HTTPException(409, 'The agreed scope changed since this analysis. Run a new analysis before sharing this quote.')
            items = editable_items(change, body, publishing=True)
            selected = [i for i in items if i['selected']]
            total = sum(i['amount_cents'] for i in selected)
            if not selected:
                raise HTTPException(422, 'Include at least one change to confirm with your client.')
            if total > 10000000:
                raise HTTPException(422, 'The quote exceeds the prototype limit of USD 100,000.')
            change.update(items=items, total_cents=total, due_date=body.due_date, note=body.note, status='awaiting', published_at=now(), share_token=secrets.token_urlsafe(24), payment_mode='none' if total == 0 else 'sandbox' if settings.paypal_ready else 'demo')
            change['quote_hash'] = quote_digest(change)
            store.save_change(change)
            store.event(id, 'published', f"Version {change['version']} locked and ready for client review.")
            return {**change, 'revision': revision_comparison(change)}

    @app.post('/api/changes/{id}/revise', dependencies=[Depends(owner)])
    async def revise(id: str):
        initial = change_by_id(id)
        async with lock('project:' + initial['project_id']):
            old = change_by_id(id)
            if old['status'] not in ('awaiting', 'declined'):
                raise HTTPException(409, 'Only an unanswered or declined quote can be revised. Accepted versions are immutable.')
            revised = {key: copy.deepcopy(old[key]) for key in ('project_id', 'project', 'message', 'summary', 'provider', 'items', 'due_date', 'note')}
            if scope_changed(old):
                project = baseline_project(store.project(old['project_id']))
                fresh = await analyze(settings, project, old['message'])
                revised.update(project=project, **fresh)
            revised.update(id=uid('change'), version=old['version'] + 1, status='draft', total_cents=sum(i['amount_cents'] for i in revised['items'] if i['selected']), created_at=now(), previous_id=old['id'], revision_source=revision_source(old))
            old['status'] = 'superseded'
            store.save_change(old)
            store.save_change(revised)
            store.event(old['id'], 'superseded', 'The studio replaced this quote with a new version.')
            store.event(revised['id'], 'draft', f"Revision of version {old['version']}; requires a new client confirmation.")
            return {**revised, 'revision': revision_comparison(revised)}

    @app.get('/api/changes/{id}/events', dependencies=[Depends(owner)])
    def events(id: str):
        change_by_id(id)
        return store.events(id)

    @app.get('/api/review/{token}')
    def review(token: str):
        change = change_by_token(token)
        result = public_record(change, store.events(change['id']))
        result['scope_changed'] = change['status'] == 'awaiting' and scope_changed(change)
        return result

    @app.post('/api/review/{token}/respond')
    async def respond(token: str, body: RespondInput):
        initial = change_by_token(token)
        async with lock('project:' + initial['project_id']):
            change = change_by_token(token)
            if change['status'] != 'awaiting' or body.version != change['version']:
                raise HTTPException(409, 'This version has already been answered or replaced. Refresh the review page.')
            if body.action == 'accept' and scope_changed(change):
                raise HTTPException(409, 'The agreed project scope changed after this quote was issued. Ask the studio for a refreshed version.')
            change['status'] = ('accepted_no_payment' if change['total_cents'] == 0 else 'accepted') if body.action == 'accept' else 'declined'
            change['response'] = {'name': body.name, 'note': body.note, 'at': now(), 'version': body.version, 'quote_hash': change['quote_hash']}
            store.save_change(change)
            store.event(change['id'], change['status'], f"{body.name} {'accepted' if body.action == 'accept' else 'requested a revision of'} version {body.version}.")
            return public_record(change, store.events(change['id']))

    @app.post('/api/review/{token}/order')
    async def order(token: str):
        initial = change_by_token(token)
        async with lock(initial['id']):
            change = change_by_token(token)
            if change['status'] != 'accepted':
                raise HTTPException(409, 'Accept this quote before starting payment.')
            if change['payment_mode'] != 'sandbox':
                raise HTTPException(409, 'This is a walkthrough quote. Use its explicitly simulated payment action.')
            if change.get('order_id'):
                try:
                    current = await paypal.get_order(change['order_id'])
                except HTTPException as exc:
                    if exc.status_code != 410:
                        raise
                    current = {'status': 'VOIDED'}
                state = current.get('status')
                if state == 'COMPLETED':
                    change = await reconcile(change, current)
                    return {'payment': public_record(change, store.events(change['id']))}
                if state == 'APPROVED':
                    await paypal.capture(change['order_id'], change)
                    change = await reconcile(change, await paypal.get_order(change['order_id']))
                    return {'payment': public_record(change, store.events(change['id']))}
                if state in ('CREATED', 'PAYER_ACTION_REQUIRED'):
                    return {'approval_url': approval_url(current), 'order_id': change['order_id']}
                if state != 'VOIDED':
                    raise HTTPException(409, 'This Sandbox order cannot be retried yet. Refresh its payment status before trying again.')
                change['order_attempt'] = change.get('order_attempt', 1) + 1
                change.pop('order_id', None)
                change.pop('approval_url', None)
                store.save_change(change)
                store.event(change['id'], 'checkout_retry', 'The prior Sandbox order is unavailable or voided. A new checkout attempt is being prepared.')
            data = await paypal.create_order(change)
            url = approval_url(data)
            change.update(order_id=data['id'], approval_url=url)
            store.save_change(change)
            store.event(change['id'], 'checkout', 'PayPal Sandbox order created; payment is not yet confirmed.')
            return {'approval_url': url, 'order_id': data['id']}

    async def reconcile(change, data):
        capture_id = verified_capture(data, change)
        if change['status'] != 'paid':
            change.update(status='paid', capture_id=capture_id, paid_at=now())
            store.save_change(change)
            store.event(change['id'], 'paid', 'Completed PayPal Sandbox capture verified against the locked quote and amount.')
        return change

    @app.post('/api/review/{token}/payment-status')
    async def payment_status(token: str):
        initial = change_by_token(token)
        async with lock(initial['id']):
            change = change_by_token(token)
            if change.get('payment_mode') != 'sandbox' or change['status'] not in ('accepted', 'paid'):
                raise HTTPException(409, 'Only an accepted Sandbox quote has a PayPal payment status.')
            if change['status'] == 'paid' or not change.get('order_id'):
                return public_record(change, store.events(change['id']))
            current = await paypal.get_order(change['order_id'])
            if current.get('status') == 'COMPLETED':
                change = await reconcile(change, current)
            return public_record(change, store.events(change['id']))

    @app.post('/api/review/{token}/capture')
    async def capture(token: str, body: CaptureInput):
        initial = change_by_token(token)
        async with lock(initial['id']):
            change = change_by_token(token)
            if change.get('order_id') != body.order_id or change.get('payment_mode') != 'sandbox':
                raise HTTPException(409, 'This order does not belong to the confirmed quote.')
            if change['status'] == 'paid':
                return public_record(change, store.events(change['id']))
            if change['status'] != 'accepted':
                raise HTTPException(409, 'This quote is not eligible for capture.')
            current = await paypal.get_order(body.order_id)
            if current.get('status') != 'COMPLETED':
                await paypal.capture(body.order_id, change)
                # The capture response may omit purchase-unit metadata; read the
                # authoritative order representation before validating the quote.
                current = await paypal.get_order(body.order_id)
            change = await reconcile(change, current)
            return public_record(change, store.events(change['id']))

    @app.post('/api/review/{token}/demo-payment')
    async def demo_payment(token: str):
        initial = change_by_token(token)
        async with lock(initial['id']):
            change = change_by_token(token)
            if change.get('payment_mode') != 'demo' or change['status'] not in ('accepted', 'demo_paid'):
                raise HTTPException(409, 'Only an accepted walkthrough quote can simulate payment.')
            if change['status'] != 'demo_paid':
                change.update(status='demo_paid', paid_at=now(), capture_id=f"DEMO-{change['id']}")
                store.save_change(change)
                store.event(change['id'], 'demo_paid', 'Simulated walkthrough payment. No PayPal API was called and no money moved.')
            return public_record(change, store.events(change['id']))

    @app.post('/api/paypal/webhook')
    async def webhook(request: Request):
        event = await request.json()
        if not isinstance(event, dict) or not isinstance(event.get('id'), str) or not 1 <= len(event['id']) <= 200:
            raise HTTPException(400, 'Invalid webhook event.')
        await paypal.verify_webhook(request.headers, event)
        with store.lock:
            if store.db.execute('SELECT 1 FROM webhook_events WHERE id=?', (event['id'],)).fetchone():
                return {'ok': True, 'duplicate': True}
        if event.get('event_type') == 'PAYMENT.CAPTURE.COMPLETED':
            order_id = event.get('resource', {}).get('supplementary_data', {}).get('related_ids', {}).get('order_id')
            change = next((c for c in store.changes() if c.get('order_id') == order_id and c.get('payment_mode') == 'sandbox'), None)
            if change:
                async with lock(change['id']):
                    change = change_by_id(change['id'])
                    if change['status'] not in ('accepted', 'paid'):
                        raise HTTPException(409, 'Payment arrived for a quote in an unexpected state.')
                    await reconcile(change, await paypal.get_order(order_id))
        with store.transaction() as db:
            db.execute('INSERT OR IGNORE INTO webhook_events VALUES (?)', (event['id'],))
        return {'ok': True}

    def export(change):
        record = public_record(change, store.events(change['id']))
        selected = [i for i in change['items'] if i['selected']]
        confirmed = change['status'] in ('accepted', 'accepted_no_payment', 'paid', 'demo_paid')
        lines = [f"# ScopePay change record — version {change['version']}", '', f"Project: {change['project']['title']}", f"Client: {change['project']['client_name']}", f"Status: {change['status']}", f"Payment environment: {change.get('payment_mode', 'not published')}", f"Analysis source: {change['provider']}", '', '## Original agreement', change['project']['scope'], '', '## Client request', change['message'], '', '## Confirmed changes' if confirmed else '## Proposed changes — not accepted']
        for item in selected:
            lines += [f"- {item['title']}: USD {item['amount_cents'] / 100:.2f}", f"  Request evidence: {item['request_quote']}", f"  Agreement evidence: {item['scope_quote'] or 'No cited clause'}", f"  Clarification: {item['resolution'] or 'None'}"]
        lines += ['', f"Total additional fee: USD {change['total_cents'] / 100:.2f}", f"Revised delivery: {change['due_date']}", f"Note: {change.get('note', '')}", f"Quote SHA-256: {change.get('quote_hash', 'unpublished')}", '', '## Client response']
        response = change.get('response')
        if response:
            lines += [f"Recorded name: {response['name']}", f"Recorded at: {response['at']}", f"Response status: {change['status']}", f"Version: {response['version']}", f"Accepted/answered quote fingerprint: {response['quote_hash']}", f"Client message: {response.get('note', '')}"]
        else:
            lines.append('No client response has been recorded. This is not an accepted agreement.')
        lines += ['', '## Payment', f"Mode: {change.get('payment_mode', 'not published')}", f"Capture: {change.get('capture_id', 'No completed capture')}", f"Recorded payment time: {change.get('paid_at', 'No payment recorded')}"]
        if change.get('payment_mode') == 'none':
            lines.append('No additional payment is due for this version. This is a scope confirmation, not a payment receipt.')
        lines += ['', '## Activity']
        lines += [f"- {event['created_at']}: {event['detail']}" for event in record['events']]
        comparison = record['revision']
        if comparison:
            lines += ['', f"## Changes since version {comparison['previous_version']}", f"Previous quote SHA-256: {comparison['previous_quote_hash']}", f"Previous fee: USD {comparison['previous_total_cents'] / 100:.2f}", f"Fee difference: USD {comparison['delta_cents'] / 100:+.2f}"]
            if comparison['response_note']:
                lines.append(f"Previous client feedback: {comparison['response_note']}")
            if comparison['baseline_changed']:
                lines.append('The agreed baseline changed; this revision was reanalyzed against the latest scope.')
            for item in comparison['items']:
                before, after = item['before'], item['after']
                lines.append(f"- {item['kind']}: {(after or before)['title']}")
                if before:
                    lines.append(f"  Before: {before['title']}; {before['kind']}; USD {before['amount_cents'] / 100:.2f}; {before['resolution']}")
                if after:
                    lines.append(f"  After: {after['title']}; {after['kind']}; USD {after['amount_cents'] / 100:.2f}; {after['resolution']}")
            lines += [f"- {meta['field']}: {meta['before']} → {meta['after']}" for meta in comparison['metadata']]
            if not comparison['has_changes']:
                lines.append('No selected scope, fee, delivery, note or payment-mode differences.')
        lines += ['', 'Typed confirmations are workflow records. This prototype does not provide escrow or a guarantee of dispute outcomes. Demo payments are simulated; Sandbox payments use test money.']
        entries = {'agreement.md': '\n'.join(lines).encode(), 'record.json': json.dumps(record, indent=2, ensure_ascii=False).encode()}
        return zip_response(entries, f'scopepay-{change["id"]}-v{change["version"]}.zip')

    @app.get('/api/changes/{id}/export', dependencies=[Depends(owner)])
    def owner_export(id: str):
        return export(change_by_id(id))

    @app.get('/api/review/{token}/export')
    def client_export(token: str):
        return export(change_by_token(token))

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path.startswith('api/'):
            raise HTTPException(404, 'Endpoint not found.')
        dist = ROOT / 'dist'
        file = (dist / path).resolve()
        if path and file.is_relative_to(dist.resolve()) and file.is_file():
            return FileResponse(file)
        if (dist / 'index.html').exists():
            return FileResponse(dist / 'index.html', headers={'Cache-Control': 'no-store'})
        return JSONResponse({'message': 'Build the frontend with npm run build, or use the Vite development server on port 5191.'})

    return app


app = create_app()
