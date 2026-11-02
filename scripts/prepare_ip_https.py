"""Run as root on the approved host; do not load or print application secrets."""
import argparse
from pathlib import Path
import re
import subprocess
import urllib.request

BASE = Path('/www/wwwroot/scopepay-ai')
WEB = Path('/www/wwwroot/scopepay-acme')
CONF = Path('/www/server/panel/vhost/nginx/scopepay-ip-acme.conf')
NGINX = Path('/www/server/nginx/sbin/nginx')
IP = '47.79.243.86'


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--accept-le-terms', action='store_true')
    args = parser.parse_args()
    if not args.accept_le_terms:
        raise SystemExit('Explicit subscriber agreement approval required.')
    assert NGINX.is_file() and (BASE / '.venv/bin/python').is_file()
    for path in CONF.parent.glob('*.conf'):
        if path == CONF:
            continue
        for names in re.findall(r'\bserver_name\s+([^;]+);', path.read_text(errors='replace')):
            if IP in names.split():
                raise SystemExit('Existing explicit IP vhost found; inspect before changing routing.')
    challenge = WEB / '.well-known/acme-challenge'
    challenge.mkdir(parents=True, exist_ok=True)
    for directory in (WEB, WEB / '.well-known', challenge):
        directory.chmod(0o755)
    probe = challenge / 'scopepay-preflight'
    probe.write_text('scopepay-acme-ready\n')
    probe.chmod(0o644)
    config = f'''# ScopePay-only IP certificate validation; existing named sites unchanged.
server {{
    listen 80;
    server_name {IP};
    root {WEB};
    location ^~ /.well-known/acme-challenge/ {{ try_files $uri =404; }}
    location / {{ return 404; }}
}}
'''
    if CONF.exists() and CONF.read_text() != config:
        raise SystemExit('ScopePay validation config differs; refusing overwrite.')
    created = not CONF.exists()
    if created:
        CONF.write_text(config)
        CONF.chmod(0o644)
    try:
        run(NGINX, '-t')
    except subprocess.CalledProcessError:
        if created:
            CONF.unlink()  # Only the exact new file created by this invocation.
        raise
    run(NGINX, '-s', 'reload')
    request = urllib.request.Request('http://127.0.0.1/.well-known/acme-challenge/scopepay-preflight', headers={'Host': IP})
    with urllib.request.urlopen(request, timeout=15) as response:
        assert response.read() == b'scopepay-acme-ready\n'
    print('ACME_WEBROOT_VERIFIED', flush=True)
    certenv = BASE / 'certbot-env'
    if not certenv.exists():
        run(BASE / 'tools/uv', 'venv', '--python', BASE / '.venv/bin/python', certenv)
    run(BASE / 'tools/uv', '--no-cache', 'pip', 'install', '--python', certenv / 'bin/python', 'certbot>=5.4,<6')
    for name in ('acme-config', 'acme-work', 'acme-logs'):
        (BASE / name).mkdir(mode=0o700, exist_ok=True)
        (BASE / name).chmod(0o700)
    run(certenv / 'bin/certbot', 'certonly', '--webroot', '--webroot-path', WEB,
        '--ip-address', IP, '--preferred-profile', 'shortlived', '--cert-name', 'scopepay-ip',
        '--config-dir', BASE / 'acme-config', '--work-dir', BASE / 'acme-work',
        '--logs-dir', BASE / 'acme-logs', '--non-interactive', '--agree-tos',
        '--register-unsafely-without-email')
    certificate = BASE / 'acme-config/live/scopepay-ip/fullchain.pem'
    run('openssl', 'x509', '-in', certificate, '-noout', '-issuer', '-dates', '-ext', 'subjectAltName')
    print('IP_CERTIFICATE_READY; APPLICATION_NOT_EXPOSED', flush=True)


if __name__ == '__main__':
    main()
