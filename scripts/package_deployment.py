"""Build a source/runtime-only archive; never include local state or secrets."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'deployment-2026-10-30'
OUT.mkdir(parents=True, exist_ok=True)
archive = OUT / 'scopepay-runtime-2026-10-30.zip'
files = [ROOT / n for n in ('README.md', 'requirements.txt', 'LICENSE', '.env.example')]
files += sorted((ROOT / 'api').glob('*.py'))
files += sorted(p for p in (ROOT / 'dist').rglob('*') if p.is_file())
assert (ROOT / 'dist/index.html').is_file()
assert all(p.is_file() for p in files)
names = [p.relative_to(ROOT).as_posix() for p in files]
assert '.env' not in names and not any(n.startswith(('data/', 'output/')) for n in names)
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for p, name in zip(files, names):
        z.write(p, name)
manifest = {'archive': archive.name, 'bytes': archive.stat().st_size,
            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': names,
            'contains_credentials': False, 'contains_database': False}
(OUT / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2))
