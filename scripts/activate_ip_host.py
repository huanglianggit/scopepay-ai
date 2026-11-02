"""Activate the approved isolated IP judging app; never print credentials."""
from pathlib import Path
import grp
import json
import os
import pwd
import socket
import ssl
import subprocess
import time
import urllib.request
import urllib.error
from dotenv import dotenv_values

B = Path('/www/wwwroot/scopepay-ai')
NG = '/www/server/nginx/sbin/nginx'
ENV = B / 'scopepay-runtime.env'
CONF = Path('/www/server/panel/vhost/nginx/scopepay-judging.conf')
UNIT = Path('/etc/systemd/system/scopepay-ai.service')
values = dotenv_values(ENV)
assert values.get('PUBLIC_BASE_URL') == 'https://47.79.243.86:18080'
assert len(values.get('OWNER_ACCESS_CODE') or '') >= 24
assert all(values.get(k) for k in ('AI_API_KEY', 'AI_MODEL', 'PAYPAL_CLIENT_ID', 'PAYPAL_CLIENT_SECRET'))
assert (B / 'acme-config/live/scopepay-ip/fullchain.pem').is_file()
assert not CONF.exists() and not UNIT.exists(), 'Existing service/config: inspect before changing.'
for port in (8792, 18080):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


try:
    account = pwd.getpwnam('scopepay')
    assert account.pw_dir == str(B / 'data') and account.pw_shell.endswith('nologin')
except KeyError:
    run('useradd', '--system', '--no-create-home', '--home-dir', B / 'data', '--shell', '/sbin/nologin', 'scopepay')
    account = pwd.getpwnam('scopepay')
ENV.chmod(0o600)
os.chown(ENV, 0, 0)
os.chown(B, 0, account.pw_gid)
B.chmod(0o750)
for name in ('app', '.venv', 'python'):
    run('chgrp', '-R', 'scopepay', B / name)
data = B / 'data'
data.mkdir(mode=0o750, exist_ok=True)
os.chown(data, account.pw_uid, account.pw_gid)
service = f'''[Unit]
Description=ScopePay AI isolated Sandbox judging app
After=network-online.target
Wants=network-online.target
[Service]
User=scopepay
Group=scopepay
WorkingDirectory={B}/app
EnvironmentFile={ENV}
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart={B}/.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8792 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1 --limit-concurrency 12
Restart=on-failure
RestartSec=5
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths={data}
MemoryMax=256M
CPUQuota=75%
[Install]
WantedBy=multi-user.target
'''
UNIT.write_text(service)
UNIT.chmod(0o644)
nginx = f'''limit_req_zone $binary_remote_addr zone=scopepay_login:1m rate=5r/m;
server {{
    listen 18080 ssl;
    server_name 47.79.243.86;
    ssl_certificate {B}/acme-config/live/scopepay-ip/fullchain.pem;
    ssl_certificate_key {B}/acme-config/live/scopepay-ip/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 128k;
    location = /api/session {{
        limit_req zone=scopepay_login burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8792;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $remote_addr;
    }}
    location / {{
        proxy_pass http://127.0.0.1:8792;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_read_timeout 150s;
    }}
}}
'''
CONF.write_text(nginx)
CONF.chmod(0o644)
try:
    run(NG, '-t')
except subprocess.CalledProcessError:
    CONF.unlink()  # Only the new config created above, never an existing site.
    raise
run('systemctl', 'daemon-reload')
run('systemctl', 'enable', '--now', 'scopepay-ai.service')
for attempt in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8792/api/status', timeout=3) as response:
            status = json.load(response)
        assert status['ai_ready'] and status['paypal_ready'] and status['payment_environment'] == 'sandbox'
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit('Service health failed; public firewall remains unchanged.')
try:
    urllib.request.urlopen('http://127.0.0.1:8792/api/workspace')
    raise AssertionError('Anonymous workspace unexpectedly accessible.')
except urllib.error.HTTPError as error:
    assert error.code == 401
request = urllib.request.Request('http://127.0.0.1:8792/api/session', data=json.dumps({'code': values['OWNER_ACCESS_CODE']}).encode(), headers={'Content-Type': 'application/json', 'Origin': values['PUBLIC_BASE_URL']})
with urllib.request.urlopen(request, timeout=5) as response:
    cookie = response.headers['Set-Cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie
request = urllib.request.Request('http://127.0.0.1:8792/api/workspace', headers={'Cookie': cookie.split(';', 1)[0]})
with urllib.request.urlopen(request, timeout=5) as response:
    workspace = json.load(response)
assert workspace['projects'], 'Synthetic judging seed unavailable.'
run(NG, '-s', 'reload')
for attempt in range(20):
    try:
        with socket.create_connection(('127.0.0.1', 18080), timeout=5) as sock:
            with ssl.create_default_context().wrap_socket(sock, server_hostname='47.79.243.86') as tls:
                tls.sendall(b'GET /api/status HTTP/1.1\r\nHost: 47.79.243.86:18080\r\nConnection: close\r\n\r\n')
                assert b'200 OK' in tls.recv(8192)
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit('Verified TLS health failed; public firewall remains unchanged.')
run('firewall-cmd', '--add-port=18080/tcp')
run('firewall-cmd', '--permanent', '--add-port=18080/tcp')
run('systemctl', 'is-active', 'scopepay-ai.service', 'scopepay-cert-renew.timer')
print('TLS_AND_AUTH_VERIFIED; SERVICE_AND_FIREWALL_READY; EXTERNAL_ACCESS_NOT_YET_TESTED', flush=True)
