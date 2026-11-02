import hashlib
import json
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    return f'{prefix}_{secrets.token_hex(6)}'


RATES = [
    {'id': 'language', 'name': 'Additional language', 'amount_cents': 12000, 'unit': 'per language'},
    {'id': 'booking', 'name': 'Embedded booking integration', 'amount_cents': 18000, 'unit': 'per integration'},
    {'id': 'page', 'name': 'Additional page', 'amount_cents': 8000, 'unit': 'per page'},
    {'id': 'revision', 'name': 'Additional revision round', 'amount_cents': 4000, 'unit': 'per round'},
    {'id': 'rush', 'name': 'Expedited delivery', 'amount_cents': 6000, 'unit': 'per project'},
]

SAMPLE_SCOPE = 'One responsive, single-page English website for Bloom Studio. Includes a hero section, services, testimonials, a contact form, and two revision rounds. Copy and images supplied by the client. Additional languages, appointment booking, and extra pages are outside the agreed scope.'
SAMPLE_MESSAGE = 'The page looks great! Could we also add a Chinese version and let visitors book a consultation directly on the site? A third round of revisions would help too. Happy to discuss the extra budget.'


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS changes (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, token TEXT UNIQUE, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, change_id TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS webhook_events (id TEXT PRIMARY KEY);
        ''')
        self.db.commit()

    @contextmanager
    def transaction(self):
        with self.lock, self.db:
            yield self.db

    def session(self):
        token = secrets.token_urlsafe(32)
        with self.transaction() as db:
            db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES (?, ?)', (hashlib.sha256(token.encode()).hexdigest(), time.time() + 86400 * 7))
        return token

    def authenticated(self, token):
        with self.lock:
            return self.db.execute('SELECT 1 FROM sessions WHERE digest=? AND expires>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone() is not None

    def projects(self):
        with self.lock:
            return [json.loads(r['data']) for r in self.db.execute('SELECT data FROM projects ORDER BY rowid DESC')]

    def project(self, id):
        with self.lock:
            row = self.db.execute('SELECT data FROM projects WHERE id=?', (id,)).fetchone()
            return json.loads(row['data']) if row else None

    def save_project(self, data):
        with self.transaction() as db:
            db.execute('INSERT INTO projects VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (data['id'], json.dumps(data)))

    def seed(self):
        if self.projects():
            return
        self.save_project({'id': uid('project'), 'title': 'Bloom Studio website', 'client_name': 'Alex Morgan', 'client_email': 'alex@example.com', 'scope': SAMPLE_SCOPE, 'base_cents': 50000, 'due_date': (datetime.now().date() + timedelta(days=14)).isoformat(), 'currency': 'USD', 'rates': RATES, 'created_at': now()})

    def changes(self, project_id=None):
        with self.lock:
            rows = self.db.execute('SELECT data FROM changes WHERE project_id=? ORDER BY rowid DESC', (project_id,)) if project_id else self.db.execute('SELECT data FROM changes ORDER BY rowid DESC')
            return [json.loads(r['data']) for r in rows]

    def change(self, id=None, token=None):
        with self.lock:
            row = self.db.execute('SELECT data FROM changes WHERE token=?', (token,)).fetchone() if token else self.db.execute('SELECT data FROM changes WHERE id=?', (id,)).fetchone()
            return json.loads(row['data']) if row else None

    def save_change(self, data):
        with self.transaction() as db:
            db.execute('INSERT INTO changes VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET token=excluded.token, data=excluded.data', (data['id'], data['project_id'], data.get('share_token'), json.dumps(data)))

    def event(self, change_id, kind, detail):
        with self.transaction() as db:
            db.execute('INSERT INTO events(change_id,kind,detail,created_at) VALUES (?,?,?,?)', (change_id, kind, detail, now()))

    def events(self, change_id):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT kind,detail,created_at FROM events WHERE change_id=? ORDER BY id', (change_id,))]
