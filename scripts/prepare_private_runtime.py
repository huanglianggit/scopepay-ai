"""Generate the explicitly approved private upload; never print its contents."""
import json
from pathlib import Path
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
values = dotenv_values(root / '.env')
names = ('AI_PROVIDER', 'AI_BASE_URL', 'AI_MODEL', 'AI_API_KEY', 'PAYPAL_CLIENT_ID', 'PAYPAL_CLIENT_SECRET', 'OWNER_ACCESS_CODE')
assert all(values.get(k) for k in names), 'Runtime configuration is incomplete.'
assert len(values['OWNER_ACCESS_CODE']) >= 24, 'Owner access code must have at least 24 characters.'
assert values['AI_PROVIDER'] == 'openai'
selected = {k: values[k] for k in names}
selected.update(PUBLIC_BASE_URL='https://47.79.243.86:18080', SCOPEPAY_DB='/www/wwwroot/scopepay-ai/data/judging.sqlite3')
assert all('\n' not in v and '\r' not in v for v in selected.values())
out = root / 'output/private-deployment-2026-11-02'
out.mkdir(parents=True, exist_ok=True)
path = out / 'scopepay-runtime.env'
path.write_text(''.join(k + '=' + json.dumps(v, ensure_ascii=True) + '\n' for k, v in selected.items()), encoding='utf-8')
print('PRIVATE_RUNTIME_READY; credentials not displayed; destination approved server only')
