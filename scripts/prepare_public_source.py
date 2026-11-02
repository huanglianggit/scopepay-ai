"""Create a separate, scanned publication tree, never publish the dirty workspace."""
import hashlib
import json
from pathlib import Path
import shutil
from prepare_submission import ROOT, source_files, secret_values, scan

destination = ROOT / 'output/public-source-2026-11-02'
files = source_files() + [ROOT / 'JUDGING.md']
secrets = secret_values()
private_handoff = ROOT / 'output/regression-2026-11-02/private-payment-handoff.json'
if private_handoff.exists():
    handoff = json.loads(private_handoff.read_text())
    secrets.append(handoff['review_url'].rsplit('/', 1)[-1].encode())
for path in files:
    scan(path.read_bytes(), path.relative_to(ROOT).as_posix(), secrets)
assert not destination.exists(), 'Publication tree already exists; review instead of overwriting.'
destination.mkdir(parents=True)
for path in files:
    target = destination / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
evidence = destination / 'docs/evidence'
evidence.mkdir(exist_ok=True)
report = ROOT / 'output/regression-2026-11-02/api-regression.json'
scan(report.read_bytes(), 'hosted-regression-report', secrets)
shutil.copy2(report, evidence / 'hosted-api-regression-2026-11-02.json')
manifest = {'source_files': len(files), 'secret_scan': 'passed', 'destination': str(destination),
            'private_paths_excluded': ['.env', 'data', 'output', 'work', '.git', 'node_modules', '.venv'],
            'sha256': {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.rglob('*') if p.is_file()}}
(ROOT / 'output/regression-2026-11-02/public-source-manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({'source_files': len(files), 'secret_scan': 'passed', 'publication_tree_ready': True}))
