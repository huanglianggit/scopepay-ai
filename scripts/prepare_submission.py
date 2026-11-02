"""Build a local, allowlisted submission kit. Does not publish or make API calls."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'output' / 'submission-2026-10-29'
SOURCE = KIT / 'scopepay-ai-source.zip'
ARCHIVE = ROOT / 'output' / 'scopepay-ai-submission-kit-2026-10-29.zip'
TOP_FILES = ['.env.example', '.gitignore', 'LICENSE', 'README.md', 'package.json',
             'package-lock.json', 'requirements.txt', 'start.ps1', 'index.html',
             'tsconfig.json', 'vite.config.ts', 'pytest.ini']
FOLDERS = ['api', 'src', 'tests', 'docs', 'public', 'scripts']
DENIED = {'.env', '.venv', 'node_modules', 'data', 'dist', 'output',
          '.playwright-cli', '__pycache__', '.pytest_cache', '.git'}
TITLES = {
    '00-thumbnail.jpg': ('项目缩略图 / Thumbnail', 'Cedar v3 · awaiting review · not paid'),
    '01-live-model-scope-analysis.jpg': ('真实模型分析 / Source-backed analysis', 'Cedar · live model · human review required'),
    '02-client-review-before-acceptance.jpg': ('锁定版本审阅 / Client review', 'Cedar v1 · historical USD 200 proposal · later replaced'),
    '03-paypal-sandbox-verified.jpg': ('已核验测试付款 / Verified Sandbox capture', 'Northstar · USD 99 test funds · not production money'),
    '04-scope-and-fees.jpg': ('费用与范围 / Scope and fees', 'USD 639 agreed value ≠ revenue · Sandbox and demo separated'),
    '05-model-and-paypal-connections.jpg': ('服务配置 / Connections', 'Real model and PayPal configured · public webhook not configured'),
    '06-revision-comparison.jpg': ('版本对比 / Revision comparison', 'Cedar v3 · USD 120 · new delivery date · awaiting review'),
}


def secret_values() -> list[bytes]:
    values = []
    env = ROOT / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line or line.lstrip().startswith('#'):
                continue
            key, val = line.split('=', 1)
            if key.strip() in {'AI_API_KEY', 'PAYPAL_CLIENT_ID', 'PAYPAL_CLIENT_SECRET',
                              'PAYPAL_WEBHOOK_ID', 'OWNER_ACCESS_CODE'}:
                val = val.strip().strip('\"\'')
                if val:
                    values.append(val.encode())
    db = ROOT / 'data' / 'scopepay.sqlite3'
    if db.exists():
        with sqlite3.connect(f'{db.as_uri()}?mode=ro', uri=True) as connection:
            values.extend(token.encode() for (token,) in connection.execute(
                'SELECT token FROM changes WHERE token IS NOT NULL') if token)
    return values


def scan(data: bytes, label: str, secrets: list[bytes]) -> None:
    if any(secret in data for secret in secrets):
        raise RuntimeError(f'Private value detected in {label}; no secret is printed.')
    if re.search(rb'(?:sk-[a-zA-Z0-9]{24,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)', data):
        raise RuntimeError(f'Potential credential detected in {label}.')


def source_files() -> list[Path]:
    files = [ROOT / name for name in TOP_FILES]
    for folder in FOLDERS:
        if (ROOT / folder).is_dir():
            for path in (ROOT / folder).rglob('*'):
                rel = path.relative_to(ROOT)
                if (path.is_file() and not path.is_symlink()
                        and not DENIED.intersection(rel.parts)
                        and path.suffix not in {'.pyc', '.pyo', '.sqlite3', '.db', '.tsbuildinfo'}):
                    files.append(path)
    return sorted(files)


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if data[:2] != b'\xff\xd8' or data[-2:] != b'\xff\xd9':
        raise RuntimeError('Invalid JPEG framing')
    pos = 2
    while pos < len(data):
        if data[pos] != 255:
            pos += 1
            continue
        while data[pos] == 255:
            pos += 1
        marker = data[pos]
        pos += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        length = struct.unpack('>H', data[pos:pos + 2])[0]
        if marker in {0xC0, 0xC1, 0xC2}:
            height, width = struct.unpack('>HH', data[pos + 3:pos + 7])
            return width, height
        pos += length
    raise RuntimeError('JPEG dimensions missing')


def main() -> None:
    secrets = secret_values()
    files = source_files()
    for path in files:
        if not path.is_file():
            raise RuntimeError(f'Missing required source: {path.name}')
        scan(path.read_bytes(), str(path.relative_to(ROOT)), secrets)
    # Validate all input material before generating archive outputs.
    for path in KIT.glob('*.md'):
        scan(path.read_bytes(), path.name, secrets)
    with zipfile.ZipFile(SOURCE, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, 'scopepay-ai/' + path.relative_to(ROOT).as_posix())

    screenshots = []
    for name, (title, caption) in TITLES.items():
        path = KIT / 'screenshots' / name
        data = path.read_bytes()
        width, height = jpeg_dimensions(data)
        if len(data) > 5_000_000:
            raise RuntimeError(f'Screenshot too large: {name}')
        if name.startswith('00-') and width * 2 != height * 3:
            raise RuntimeError('Thumbnail is not 3:2')
        screenshots.append(dict(file='screenshots/' + name, title=title, caption=caption,
                                width=width, height=height, bytes=len(data),
                                sha256=hashlib.sha256(data).hexdigest()))
    (KIT / 'manifest.json').write_text(json.dumps({
        'date': '2026-10-29', 'source_files': len(files),
        'publication_status': 'local only; no final video or Devpost submission',
        'source_excludes': sorted(DENIED), 'screenshots': screenshots,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    docs = sorted(KIT.glob('*.md'))
    links = ''.join(f'<li><a href="{html.escape(p.name)}">{html.escape(p.stem)}</a></li>' for p in docs)
    cards = ''.join(
        f'<article><h2>{html.escape(s["title"])}</h2><p>{html.escape(s["caption"])}</p>'
        f'<a href="{s["file"]}"><img src="{s["file"]}" alt="{html.escape(s["title"])}" loading="lazy"></a>'
        f'<p>{s["width"]} × {s["height"]} · {s["bytes"]:,} bytes · <a href="{s["file"]}" download>下载原图</a></p></article>'
        for s in screenshots)
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ScopePay AI · 参赛材料包</title><style>
body{margin:0;background:#f5f6f1;color:#183b31;font:16px/1.7 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:40px 24px}h1{font-size:36px;margin-bottom:12px}
a{color:#135a49;text-underline-offset:4px}aside{border-left:4px solid #b59343;padding:12px 20px;background:#fff}
.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px;margin-top:28px}
article{background:#fff;border:1px solid #d9e1d7;border-radius:12px;padding:20px}h2{font-size:20px}
img{display:block;width:100%;height:330px;object-fit:contain;object-position:top;background:#f4f5ef}
li{margin:6px 0}small{color:#567166}</style><main>
<small>LOCAL SUBMISSION KIT · 2026-10-29</small><h1>ScopePay AI 参赛材料包</h1>
<aside>已经整理，不代表已经提交。包含英文文案、7张真实截图、评委指南、视频脚本和源码快照。<br>
仍需公开源码仓库、安排可用评委访问、录制并公开上传视频，最后确认Devpost提交。所有付款证据均为Sandbox测试资金。</aside>
<h2>文案与说明</h2><ul>''' + links + '''</ul><p><a href="scopepay-ai-source.zip" download>下载无密钥源码快照</a>
 · <a href="manifest.json">截图尺寸与文件清单</a> · <a href="checksums.sha256">SHA-256校验</a></p>
<h2>截图预览</h2><p>点击查看原图。Northstar已核验USD 99 Sandbox付款；Cedar展示模型和修订流程，尚未付款。详细英文说明见04文档。</p>
<section class="gallery">''' + cards + '</section></main></html>'
    scan(page.encode(), 'index.html', secrets)
    (KIT / 'index.html').write_text(page, encoding='utf-8')
    artifacts = sorted(p for p in KIT.rglob('*') if p.is_file() and p.name != 'checksums.sha256')
    checksums = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(KIT).as_posix()}\n' for p in artifacts)
    (KIT / 'checksums.sha256').write_text(checksums, encoding='utf-8')
    with zipfile.ZipFile(ARCHIVE, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(p for p in KIT.rglob('*') if p.is_file()):
            bundle.write(path, KIT.name + '/' + path.relative_to(KIT).as_posix())
    for archive in [SOURCE, ARCHIVE]:
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip() is not None:
                raise RuntimeError('Archive CRC check failed')
            for name in bundle.namelist():
                if Path(name).name != '.env.example' and DENIED.intersection(Path(name).parts):
                    raise RuntimeError(f'Prohibited path in archive: {name}')
                if not name.endswith(('.jpg', '.zip')):
                    scan(bundle.read(name), name, secrets)
    print(json.dumps({'source_files': len(files), 'screenshots': len(screenshots),
                      'secret_scan': 'passed', 'archives_crc': 'passed',
                      'source_zip_bytes': SOURCE.stat().st_size,
                      'kit_zip_bytes': ARCHIVE.stat().st_size}, indent=2))


if __name__ == '__main__':
    main()
