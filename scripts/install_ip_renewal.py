"""Install only ScopePay's certificate timer, then exercise staging renewal."""
from pathlib import Path
import subprocess

B = Path('/www/wwwroot/scopepay-ai')
NG = '/www/server/nginx/sbin/nginx'
assert (B / 'acme-config/live/scopepay-ip/fullchain.pem').is_file()


def exact_file(path, content, mode):
    if path.exists() and path.read_text() != content:
        raise SystemExit('Refusing to replace a different file: ' + str(path))
    if not path.exists():
        path.write_text(content)
    path.chmod(mode)


hook = B / 'reload-scopepay-certificate.sh'
exact_file(hook, '#!/bin/sh\nset -e\n' + NG + ' -t\n' + NG + ' -s reload\n', 0o700)
command = [str(B / 'certbot-env/bin/certbot'), 'renew', '--quiet',
           '--config-dir', str(B / 'acme-config'), '--work-dir', str(B / 'acme-work'),
           '--logs-dir', str(B / 'acme-logs'), '--deploy-hook', str(hook)]
service = '''[Unit]
Description=Renew ScopePay IP certificate only
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
PrivateTmp=true
NoNewPrivileges=true
TimeoutStartSec=300
ExecStart=''' + ' '.join(command) + '\n'
timer = '''[Unit]
Description=Check ScopePay certificate every eight hours

[Timer]
OnCalendar=*-*-* 00,08,16:15:00
RandomizedDelaySec=600
Persistent=true
Unit=scopepay-cert-renew.service

[Install]
WantedBy=timers.target
'''
exact_file(Path('/etc/systemd/system/scopepay-cert-renew.service'), service, 0o644)
exact_file(Path('/etc/systemd/system/scopepay-cert-renew.timer'), timer, 0o644)
subprocess.run(['systemctl', 'daemon-reload'], check=True)
subprocess.run(['systemctl', 'enable', '--now', 'scopepay-cert-renew.timer'], check=True)
subprocess.run(command + ['--dry-run'], check=True)
subprocess.run(['systemctl', 'is-active', 'scopepay-cert-renew.timer'], check=True)
subprocess.run(['systemctl', 'list-timers', 'scopepay-cert-renew.timer', '--no-pager'], check=True)
print('IP_CERTIFICATE_RENEWAL_DRY_RUN_PASSED; APPLICATION_NOT_EXPOSED', flush=True)
